"""SQLAlchemy schema for ObsForge enrichment jobs."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import SchemaBase

__all__ = ["EnrichmentJob", "EnrichmentJobPhase"]


class EnrichmentJobPhase(StrEnum):
    """Durable execution phases for one visit enrichment workflow."""

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class EnrichmentJob(SchemaBase):
    """Durable state for one visit enrichment workflow."""

    __tablename__ = "enrichment_job"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    visit: Mapped[int] = mapped_column(BigInteger)
    instrument: Mapped[str]
    day_obs: Mapped[int]
    phase: Mapped[EnrichmentJobPhase]
    error_code: Mapped[str | None]
    error_message: Mapped[str | None]
    arq_job_id: Mapped[str | None]
    registration_payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]

    __table_args__ = (
        UniqueConstraint(
            "instrument", "visit", name="enrichment_job_instrument_visit_key"
        ),
        Index("enrichment_job_by_instrument_day_obs", "instrument", "day_obs"),
        Index("enrichment_job_by_phase_updated_at", "phase", "updated_at"),
    )
