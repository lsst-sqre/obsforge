"""Models for the versioned stream pipeline configuration."""

from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "DropFieldsTransform",
    "EpochSecondsToDatetimeTransform",
    "StreamPipelineConfig",
    "StreamTransform",
    "load_stream_pipeline_config",
]


class SourceConfig(BaseModel):
    """Kafka source selection."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)


class SinkConfig(BaseModel):
    """ObsDB sink selection."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field("public", alias="schema", min_length=1)
    table_name: str = Field(alias="table", min_length=1)


class DropFieldsTransform(BaseModel):
    """Remove named fields or fields with configured prefixes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Literal["drop_fields"]
    fields: tuple[str, ...] = ()
    prefixes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_selectors(self) -> DropFieldsTransform:
        """Require the transform to select at least one field."""
        if not self.fields and not self.prefixes:
            raise ValueError("drop_fields requires fields or prefixes")
        if any(not prefix for prefix in self.prefixes):
            raise ValueError("drop_fields prefixes cannot be empty")
        return self


class EpochSecondsToDatetimeTransform(BaseModel):
    """Convert numeric epoch seconds to a timezone-aware UTC datetime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Literal["epoch_seconds_to_datetime"]
    field: str = Field(min_length=1)
    input_scale: Literal["tai", "utc"]


StreamTransform = Annotated[
    DropFieldsTransform | EpochSecondsToDatetimeTransform,
    Field(discriminator="operation"),
]


class StreamPipelineConfig(BaseModel):
    """One versioned Kafka-to-ObsDB stream pipeline."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    name: str = Field(min_length=1)
    consumer_group: str = Field(min_length=1)
    source: SourceConfig
    sink: SinkConfig
    transformations: list[StreamTransform] = Field(min_length=1)


def load_stream_pipeline_config(path: Path) -> StreamPipelineConfig:
    """Load and validate a stream pipeline YAML file."""
    with path.open() as config_file:
        raw_config: Any = yaml.safe_load(config_file)
    return StreamPipelineConfig.model_validate(raw_config)
