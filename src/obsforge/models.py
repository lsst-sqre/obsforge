"""Models for obsforge."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from safir.metadata import Metadata as SafirMetadata

from .schema import EnrichmentJobPhase

__all__ = [
    "Index",
    "SerializedEnrichmentJob",
    "VisitRegistration",
    "VisitTimespan",
]


class Index(BaseModel):
    """Metadata returned by the external root URL of the application.

    Notes
    -----
    As written, this is not very useful. Add additional metadata that will be
    helpful for a user exploring the application, or replace this model with
    some other model that makes more sense to return from the application API
    root.
    """

    metadata: SafirMetadata = Field(..., title="Package metadata")


class VisitTimespan(BaseModel):
    """Visit time range from the registration payload."""

    begin: datetime = Field(..., title="Visit start time")

    end: datetime = Field(..., title="Visit end time")


class VisitRegistration(BaseModel):
    """Prompt Publication payload registering one visit."""

    instrument: str = Field(..., title="Instrument name")

    day_obs: int = Field(..., title="Visit day")

    visit_id: str = Field(..., title="Unique visit identifier")

    timespan: VisitTimespan = Field(..., title="Visit timespan")


class SerializedEnrichmentJob(BaseModel):
    """Serializable representation of an enrichment job."""

    id: int

    visit_id: str

    instrument: str

    day_obs: int

    phase: EnrichmentJobPhase

    attempt_count: int

    error_code: str | None

    error_message: str | None

    registration_payload: dict[str, Any]

    created_at: datetime

    updated_at: datetime

    started_at: datetime | None

    completed_at: datetime | None
