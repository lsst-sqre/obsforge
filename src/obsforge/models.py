"""Models for obsforge."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from safir.metadata import Metadata as SafirMetadata

from .schema import EnrichmentJobPhase

__all__ = [
    "Index",
    "ObsCoreRecord",
    "ObsCoreUpsert",
    "SerializedEnrichmentJob",
    "SerializedObsCore",
    "SerializedVisit",
    "SerializedVisitDetector",
    "StoredEnrichmentJob",
    "VisitDataset",
    "VisitDetectorRecord",
    "VisitDetectorUpsert",
    "VisitRecord",
    "VisitRegistration",
    "VisitTimespan",
    "VisitUpsert",
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

    # This field is part of the ObsCore schema, but it is not returned by
    # Rubin ObsCoreExporter.
    access_estsize: int | None = None

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


class VisitRecord(BaseModel):
    """Complete Visit record."""

    visitId: int
    visit: int
    physical_filter: str | None = Field(None, max_length=4)
    band: str | None = Field(None, max_length=1)
    ra: float | None = None
    dec: float | None = None
    decl: float | None = None
    skyRotation: float | None = None
    azimuth: float | None = None
    altitude: float | None = None
    zenithDistance: float | None = None
    airmass: float | None = None
    expTime: float | None = None
    expMidpt: datetime | None = None
    expMidptMJD: float | None = None
    obsStart: datetime | None = None
    obsStartMJD: float | None = None


class VisitUpsert(VisitRecord):
    """Visit record supplied for database upsert."""


class SerializedVisit(VisitRecord):
    """Serializable representation of one Visit row."""


class VisitDetectorRecord(BaseModel):
    """Complete VisitDetector record."""

    detectorId: int
    visitId: int
    physical_filter: str | None = Field(None, max_length=32)
    band: str | None = Field(None, max_length=32)
    ra: float | None = None
    dec: float | None = None
    pixelScale: float | None = None
    zenithDistance: float | None = None
    expTime: float | None = None
    zeroPoint: float | None = None
    psfSigma: float | None = None
    psfArea: float | None = None
    psfIxx: float | None = None
    psfIyy: float | None = None
    psfIxy: float | None = None
    skyBg: float | None = None
    skyNoise: float | None = None
    psfAdaptiveThresholdValue: float | None = None
    psfAdaptiveIncludeThresholdMultiplier: float | None = None
    nShapeletsStar: int | None = None
    shapeletsOnlyIqScore: float | None = None
    shapeletsIqScore: float | None = None
    centroidDiffShapeletsVsSlotMedian: float | None = None
    shapeletsStarEMedian: float | None = None
    shapeletsStarUnNormalizedEMedian: float | None = None
    refCatSourceDensity: float | None = None
    astromOffsetMean: float | None = None
    astromOffsetStd: float | None = None
    nPsfStar: int | None = None
    psfStarDeltaE1Median: float | None = None
    psfStarDeltaE2Median: float | None = None
    psfStarDeltaE1Scatter: float | None = None
    psfStarDeltaE2Scatter: float | None = None
    psfStarDeltaSizeMedian: float | None = None
    psfStarDeltaSizeScatter: float | None = None
    psfStarScaledDeltaSizeScatter: float | None = None
    psfTraceRadiusDelta: float | None = None
    psfApFluxDelta: float | None = None
    psfApCorrSigmaScaledDelta: float | None = None
    maxDistToNearestPsf: float | None = None
    starEMedian: float | None = None
    starUnNormalizedEMedian: float | None = None
    starComa1Median: float | None = None
    starComa2Median: float | None = None
    starTrefoil1Median: float | None = None
    starTrefoil2Median: float | None = None
    starKurtosisMedian: float | None = None
    starE41Median: float | None = None
    starE42Median: float | None = None
    effTime: float | None = None
    effTimePsfSigmaScale: float | None = None
    effTimeSkyBgScale: float | None = None
    effTimeZeroPointScale: float | None = None
    magLim: float | None = None
    decl: float | None = None
    ccdVisitId: int | None = None
    detector: int
    seeing: float | None = None
    skyRotation: float | None = None
    expMidpt: datetime | None = None
    expMidptMJD: float | None = None
    obsStart: datetime | None = None
    obsStartMJD: float | None = None
    darkTime: float | None = None
    xSize: int | None = None
    ySize: int | None = None
    llcra: float | None = None
    llcdec: float | None = None
    ulcra: float | None = None
    ulcdec: float | None = None
    urcra: float | None = None
    urcdec: float | None = None
    lrcra: float | None = None
    lrcdec: float | None = None
    wcsPreliminaryDetectorPointingResidual: float | None = None
    wcsPreliminaryVisitPointingResidual: float | None = None


class VisitDetectorUpsert(VisitDetectorRecord):
    """VisitDetector record supplied for database upsert."""


class SerializedVisitDetector(VisitDetectorRecord):
    """Serializable representation of one VisitDetector row."""
