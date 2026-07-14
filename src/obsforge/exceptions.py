"""Exceptions raised by ObsForge."""

from fastapi import status
from safir.fastapi import ClientRequestError

from obsforge.schema import EnrichmentJobPhase

__all__ = [
    "InvalidEnrichmentJobTransitionError",
    "UnknownEnrichmentJobError",
    "UnknownEnrichmentJobVisitError",
    "UnknownObsCoreRecordError",
]


class UnknownEnrichmentJobError(ClientRequestError):
    """Raised when an enrichment job cannot be found."""

    error = "unknown_enrichment_job"
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, job_id: int) -> None:
        super().__init__(f"Unknown enrichment job {job_id}")
        self.job_id = job_id


class UnknownObsCoreRecordError(ClientRequestError):
    """Raised when an ObsCore record cannot be found."""

    error = "unknown_obscore_record"
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, obs_id: str) -> None:
        super().__init__(f"Unknown ObsCore record {obs_id}")
        self.obs_id = obs_id


class UnknownEnrichmentJobVisitError(ClientRequestError):
    """Raised when an enrichment job cannot be found by visit identity."""

    error = "unknown_enrichment_job_visit"
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, instrument: str, visit: int) -> None:
        msg = (
            "Unknown enrichment job for "
            f"instrument {instrument!r} and visit {visit}"
        )
        super().__init__(msg)
        self.instrument = instrument
        self.visit = visit


class InvalidEnrichmentJobTransitionError(ClientRequestError):
    """Raised when an enrichment job phase transition is invalid."""

    error = "invalid_enrichment_job_transition"
    status_code = status.HTTP_409_CONFLICT

    def __init__(
        self,
        job_id: int,
        current: EnrichmentJobPhase,
        requested: EnrichmentJobPhase,
    ) -> None:
        msg = (
            f"Cannot transition enrichment job {job_id} from "
            f"{current.value} to {requested.value}"
        )
        super().__init__(msg)
        self.job_id = job_id
        self.current = current
        self.requested = requested
