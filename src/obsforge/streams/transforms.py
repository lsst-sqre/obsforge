"""Pure transformations used by ObsForge stream pipelines."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from math import isfinite
from typing import Any, assert_never, cast

from astropy.time import Time

from .models import (
    DropFieldsTransform,
    EpochSecondsToDatetimeTransform,
    StreamTransform,
)

__all__ = [
    "apply_transformations",
    "drop_fields",
    "epoch_seconds_to_datetime",
]


def drop_fields(
    value: Mapping[str, Any], transform: DropFieldsTransform
) -> dict[str, Any]:
    """Return a copy without explicitly named or prefix-matched fields."""
    fields = set(transform.fields)
    return {
        key: field_value
        for key, field_value in value.items()
        if key not in fields
        and not any(key.startswith(prefix) for prefix in transform.prefixes)
    }


def epoch_seconds_to_datetime(
    value: Mapping[str, Any], transform: EpochSecondsToDatetimeTransform
) -> dict[str, Any]:
    """Convert one TAI or UTC epoch-seconds field to a UTC datetime."""
    result = dict(value)
    try:
        timestamp = result[transform.field]
    except KeyError as exc:
        raise ValueError(
            f"epoch_seconds_to_datetime field {transform.field!r} is missing"
        ) from exc
    if (
        isinstance(timestamp, bool)
        or not isinstance(timestamp, (int, float))
        or not isfinite(timestamp)
    ):
        raise ValueError(
            "epoch_seconds_to_datetime field "
            f"{transform.field!r} must be a finite number"
        )
    input_format = "unix_tai" if transform.input_scale == "tai" else "unix"
    input_time = Time(
        timestamp,
        format=input_format,
        scale=transform.input_scale,
    )
    result[transform.field] = cast(
        "datetime", input_time.utc.to_datetime(timezone=UTC)
    )
    return result


def apply_transformations(
    value: Mapping[str, Any], transformations: Sequence[StreamTransform]
) -> dict[str, Any]:
    """Apply the configured transformations in declaration order."""
    result = dict(value)
    for transform in transformations:
        if isinstance(transform, DropFieldsTransform):
            result = drop_fields(result, transform)
        elif isinstance(transform, EpochSecondsToDatetimeTransform):
            result = epoch_seconds_to_datetime(result, transform)
        else:
            assert_never(transform)
    return result
