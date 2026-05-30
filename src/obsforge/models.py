"""Models for obsforge."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from safir.metadata import Metadata as SafirMetadata

from .schema import EnrichmentJobPhase

__all__ = [
    "Index",
    "ObsCoreUpsert",
    "SerializedEnrichmentJob",
    "SerializedObsCore",
    "StoredEnrichmentJob",
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

    error_code: str | None

    error_message: str | None

    registration_payload: dict[str, Any]

    created_at: datetime

    updated_at: datetime

    started_at: datetime | None

    completed_at: datetime | None


class StoredEnrichmentJob(SerializedEnrichmentJob):
    """Internal enrichment job representation with queue transport state."""

    arq_job_id: str | None


class ObsCoreUpsert(BaseModel):
    """ObsCore fields supplied by ObsForge enrichment."""

    visit_id: str

    dataproduct_subtype: str

    obs_id: str

    obs_publisher_did: str

    access_url: str

    s_ra: float

    s_dec: float

    s_region: str

    s_resolution: float

    t_min: float

    t_max: float

    t_exptime: float

    em_min: float

    em_max: float

    band: str

    physical_filter: str


class SerializedObsCore(BaseModel):
    """Serializable representation of one ObsCore row."""

    dataproduct_type: str

    dataproduct_subtype: str

    calib_level: int

    target_name: str | None

    obs_id: str

    obs_collection: str

    obs_publisher_did: str

    access_url: str

    access_format: str

    access_estsize: int | None

    s_ra: float

    s_dec: float

    s_fov: float

    s_region: str

    s_resolution: float

    s_xel1: int | None

    s_xel2: int | None

    t_xel: int | None

    t_min: float

    t_max: float

    t_exptime: float

    t_resolution: float | None

    em_xel: int | None

    em_min: float

    em_max: float

    em_res_power: float | None

    o_ucd: str

    pol_xel: int | None

    instrument_name: str

    facility_name: str

    visit_id: str

    band: str

    physical_filter: str
