"""Tests for stream pipeline configuration."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from obsforge.schema import SchemaBase
from obsforge.streams.models import (
    DropFieldsTransform,
    EpochSecondsToDatetimeTransform,
    load_stream_pipeline_config,
)


def test_load_pipeline_config(tmp_path: Path) -> None:
    path = tmp_path / "streams.yaml"
    path.write_text(
        """
version: 1
name: test-stream
consumer_group: obsforge-test-stream-v1
source:
  topic: input-topic
sink:
  schema: public
  table: output_table
transformations:
  - operation: drop_fields
    fields: [secret]
    prefixes: [private_]
"""
    )

    pipeline = load_stream_pipeline_config(path)

    assert pipeline.consumer_group == "obsforge-test-stream-v1"
    assert pipeline.source.topic == "input-topic"
    assert pipeline.sink.schema_name == "public"
    assert pipeline.sink.table_name == "output_table"
    transform = pipeline.transformations[0]
    assert isinstance(transform, DropFieldsTransform)
    assert transform.fields == ("secret",)
    assert transform.prefixes == ("private_",)


def test_repository_pipeline_targets_managed_table() -> None:
    path = (
        Path(__file__).parents[2]
        / "config"
        / "streams"
        / "scheduler-observatory-state.yaml"
    )

    pipeline = load_stream_pipeline_config(path)

    assert pipeline.consumer_group == "obsforge-scheduler-observatory-state-v1"
    table_key = f"{pipeline.sink.schema_name}.{pipeline.sink.table_name}"
    assert table_key == "scheduler.observatory_state"
    assert table_key in SchemaBase.metadata.tables
    timestamp_transform = pipeline.transformations[1]
    assert isinstance(timestamp_transform, EpochSecondsToDatetimeTransform)
    assert timestamp_transform.field == "timestamp"
    assert timestamp_transform.input_scale == "tai"


@pytest.mark.parametrize(
    "transformation",
    [
        "{operation: rename_fields, fields: [old]}",
        "{operation: drop_fields}",
        "{operation: drop_fields, prefixes: ['']}",
        "{operation: epoch_seconds_to_datetime, field: '', input_scale: tai}",
        "{operation: epoch_seconds_to_datetime, field: timestamp}",
        (
            "{operation: epoch_seconds_to_datetime, field: timestamp, "
            "input_scale: gps}"
        ),
    ],
)
def test_reject_invalid_transform(tmp_path: Path, transformation: str) -> None:
    path = tmp_path / "streams.yaml"
    path.write_text(
        f"""
version: 1
name: test-stream
consumer_group: obsforge-test-stream-v1
source: {{topic: input-topic}}
sink: {{schema: public, table: output_table}}
transformations:
  - {transformation}
"""
    )

    with pytest.raises(ValidationError):
        load_stream_pipeline_config(path)
