"""Exceptions raised by ObsForge."""

from obsforge.schema import EnrichmentJobPhase

__all__ = [
    "InvalidEnrichmentJobTransitionError",
    "UnknownEnrichmentJobError",
    "UnknownObsCoreRecordError",
]


class UnknownEnrichmentJobError(Exception):
    """Raised when an enrichment job cannot be found."""

    def __init__(self, job_id: int) -> None:
        super().__init__(f"Unknown enrichment job {job_id}")
        self.job_id = job_id


class UnknownObsCoreRecordError(Exception):
    """Raised when an ObsCore record cannot be found."""

    def __init__(self, visit_id: str) -> None:
        super().__init__(f"Unknown ObsCore record for visit {visit_id}")
        self.visit_id = visit_id


class InvalidEnrichmentJobTransitionError(Exception):
    """Raised when an enrichment job phase transition is invalid."""

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
