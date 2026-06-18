"""Models for obsforge."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from safir.metadata import Metadata as SafirMetadata

from .schema import EnrichmentJobPhase

__all__ = [
    "Index",
    "ObsCoreUpsert",
    "SerializedEnrichmentJob",
    "SerializedObsCore",
    "StoredEnrichmentJob",
    "VisitDataset",
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


class VisitDataset(BaseModel):
    """Dataset published for the registered visit."""

    dataset_type: str = Field(..., title="Dataset type")

    id: UUID = Field(..., title="Dataset UUID")


class VisitRegistration(BaseModel):
    """Prompt Publication payload registering one visit."""

    instrument: str = Field(..., title="Instrument name")

    day_obs: int = Field(..., title="Visit day")

    visit: int = Field(..., title="Unique visit identifier")

    datasets: list[VisitDataset] = Field(..., title="Published datasets")

    timespan: VisitTimespan = Field(..., title="Visit timespan")


class SerializedEnrichmentJob(BaseModel):
    """Serializable representation of an enrichment job."""

    id: int

    visit: int

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


class ObsCoreRecord(BaseModel):
    """Complete ObsCore record."""

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

    s_resolution: float | None

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

    obs_title: str

    em_filter_name: str

    lsst_visit: int

    lsst_detector: int

    lsst_filter: str

    lsst_band: str

    lsst_patch: int | None

    lsst_tract: int | None


class ObsCoreUpsert(ObsCoreRecord):
    """ObsCore record supplied for database upsert."""


class SerializedObsCore(ObsCoreRecord):
    """Serializable representation of one ObsCore row."""
