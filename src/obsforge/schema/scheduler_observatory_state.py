"""SQLAlchemy schema for Scheduler observatory state telemetry."""

from datetime import datetime

from sqlalchemy import DDL, DateTime, Float, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from .base import SchemaBase

__all__ = ["SchedulerObservatoryState"]

_SCHEDULER_SCHEMA = "scheduler"

event.listen(
    SchemaBase.metadata,
    "before_create",
    DDL(f"CREATE SCHEMA IF NOT EXISTS {_SCHEDULER_SCHEMA}"),
)


def _info(unit: str, description: str) -> dict[str, str]:
    return {"unit": unit, "description": description}


class SchedulerObservatoryState(SchemaBase):
    """Current observatory state reported by the Scheduler CSC."""

    __tablename__ = "observatory_state"
    __table_args__ = ({"schema": _SCHEDULER_SCHEMA},)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        info=_info("", "Current timestamp at the observatory in UTC"),
    )
    ra: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        info=_info("deg", "Current pointing right ascension"),
    )
    declination: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        info=_info("deg", "Current pointing declination"),
    )
    position_angle: Mapped[float] = mapped_column(
        "positionAngle",
        Float,
        nullable=False,
        info=_info("deg", "Current sky position angle"),
    )
    parallactic_angle: Mapped[float] = mapped_column(
        "parallacticAngle",
        Float,
        nullable=False,
        info=_info("deg", "Current parallactic angle"),
    )
    tracking: Mapped[bool] = mapped_column(
        nullable=False,
        info=_info("", "Whether the telescope is tracking"),
    )
    telescope_altitude: Mapped[float] = mapped_column(
        "telescopeAltitude",
        Float,
        nullable=False,
        info=_info("deg", "Telescope altitude"),
    )
    telescope_azimuth: Mapped[float] = mapped_column(
        "telescopeAzimuth",
        Float,
        nullable=False,
        info=_info("deg", "Telescope azimuth"),
    )
    telescope_rotator: Mapped[float] = mapped_column(
        "telescopeRotator",
        Float,
        nullable=False,
        info=_info("deg", "Telescope rotator position"),
    )
    dome_altitude: Mapped[float] = mapped_column(
        "domeAltitude",
        Float,
        nullable=False,
        info=_info("deg", "Dome altitude position"),
    )
    dome_azimuth: Mapped[float] = mapped_column(
        "domeAzimuth",
        Float,
        nullable=False,
        info=_info("deg", "Dome azimuth position"),
    )
    filter_position: Mapped[str] = mapped_column(
        "filterPosition",
        Text,
        nullable=False,
        info=_info("", "Current filter"),
    )
    filter_mounted: Mapped[str] = mapped_column(
        "filterMounted",
        Text,
        nullable=False,
        info=_info("", "Current mounted and available filters"),
    )
    filter_unmounted: Mapped[str] = mapped_column(
        "filterUnmounted",
        Text,
        nullable=False,
        info=_info("", "Current unmounted and unavailable filters"),
    )
