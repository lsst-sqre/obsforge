"""Tests for stream transformations."""

from datetime import UTC, datetime

import pytest

from obsforge.streams.models import (
    DropFieldsTransform,
    EpochSecondsToDatetimeTransform,
)
from obsforge.streams.transforms import (
    apply_transformations,
    epoch_seconds_to_datetime,
)


def test_drop_fields_by_name_and_prefix() -> None:
    value = {
        "salIndex": 1,
        "private_sndStamp": 123.4,
        "private_futureField": "drop me too",
        "tracking": True,
        "explicit": "drop me",
    }
    transformations = [
        DropFieldsTransform(
            operation="drop_fields",
            fields=("salIndex", "explicit"),
            prefixes=("private_",),
        )
    ]

    result = apply_transformations(value, transformations)

    assert result == {"tracking": True}
    assert "salIndex" in value
    assert "private_sndStamp" in value
    assert "explicit" in value


def test_epoch_seconds_to_datetime_from_tai() -> None:
    value = {"timestamp": 1767225637.0, "tracking": True}

    result = epoch_seconds_to_datetime(
        value,
        EpochSecondsToDatetimeTransform(
            operation="epoch_seconds_to_datetime",
            field="timestamp",
            input_scale="tai",
        ),
    )

    assert result == {
        "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        "tracking": True,
    }
    assert value["timestamp"] == 1767225637.0


def test_epoch_seconds_to_datetime_from_utc() -> None:
    result = epoch_seconds_to_datetime(
        {"timestamp": 1767225600.0},
        EpochSecondsToDatetimeTransform(
            operation="epoch_seconds_to_datetime",
            field="timestamp",
            input_scale="utc",
        ),
    )

    assert result == {"timestamp": datetime(2026, 1, 1, tzinfo=UTC)}


@pytest.mark.parametrize("timestamp", [None, True, "1767225637", float("nan")])
def test_epoch_seconds_to_datetime_rejects_invalid_value(
    timestamp: object,
) -> None:
    transform = EpochSecondsToDatetimeTransform(
        operation="epoch_seconds_to_datetime",
        field="timestamp",
        input_scale="tai",
    )

    with pytest.raises(ValueError, match="must be a finite number"):
        epoch_seconds_to_datetime({"timestamp": timestamp}, transform)


def test_epoch_seconds_to_datetime_rejects_missing_field() -> None:
    transform = EpochSecondsToDatetimeTransform(
        operation="epoch_seconds_to_datetime",
        field="timestamp",
        input_scale="tai",
    )

    with pytest.raises(ValueError, match="field 'timestamp' is missing"):
        epoch_seconds_to_datetime({}, transform)
