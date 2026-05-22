"""Business logic for visit enrichment jobs."""

from typing import Protocol

from obsforge.exceptions import InvalidEnrichmentJobTransitionError
from obsforge.models import SerializedEnrichmentJob, VisitRegistration
from obsforge.schema import EnrichmentJobPhase

__all__ = ["EnrichmentJobService"]


class EnrichmentJobStoreProtocol(Protocol):
    """Storage operations required by `EnrichmentJobService`."""

    async def add_or_get(
        self, registration: VisitRegistration
    ) -> SerializedEnrichmentJob: ...

    async def get(self, job_id: int) -> SerializedEnrichmentJob: ...

    async def mark_queued(self, job_id: int) -> SerializedEnrichmentJob: ...

    async def mark_executing(self, job_id: int) -> SerializedEnrichmentJob: ...

    async def mark_completed(self, job_id: int) -> SerializedEnrichmentJob: ...

    async def mark_failed(
        self, job_id: int, *, error_code: str, error_message: str
    ) -> SerializedEnrichmentJob: ...


class EnrichmentJobService:
    """Apply enrichment workflow rules around durable job state."""

    def __init__(self, store: EnrichmentJobStoreProtocol) -> None:
        self._store = store

    async def register_visit(
        self, registration: VisitRegistration
    ) -> SerializedEnrichmentJob:
        """Register one visit for enrichment.

        Duplicate registration is handled idempotently by storage, returning
        the existing job for the visit.
        """
        return await self._store.add_or_get(registration)

    async def mark_queued(self, job_id: int) -> SerializedEnrichmentJob:
        """Mark a registered job as queued without regressing active jobs."""
        job = await self._store.get(job_id)
        if job.phase == EnrichmentJobPhase.PENDING:
            return await self._store.mark_queued(job_id)
        return job

    async def mark_executing(self, job_id: int) -> SerializedEnrichmentJob:
        """Mark a queued job as executing and record one worker attempt."""
        job = await self._store.get(job_id)
        if job.phase in (
            EnrichmentJobPhase.PENDING,
            EnrichmentJobPhase.QUEUED,
        ):
            return await self._store.mark_executing(job_id)
        if job.phase == EnrichmentJobPhase.EXECUTING:
            return job
        raise InvalidEnrichmentJobTransitionError(
            job.id, job.phase, EnrichmentJobPhase.EXECUTING
        )

    async def mark_completed(self, job_id: int) -> SerializedEnrichmentJob:
        """Mark an executing job as completed."""
        job = await self._store.get(job_id)
        if job.phase == EnrichmentJobPhase.EXECUTING:
            return await self._store.mark_completed(job_id)
        if job.phase == EnrichmentJobPhase.COMPLETED:
            return job
        raise InvalidEnrichmentJobTransitionError(
            job.id, job.phase, EnrichmentJobPhase.COMPLETED
        )

    async def mark_failed(
        self, job_id: int, *, error_code: str, error_message: str
    ) -> SerializedEnrichmentJob:
        """Record a failed enrichment attempt."""
        job = await self._store.get(job_id)
        if job.phase in (
            EnrichmentJobPhase.PENDING,
            EnrichmentJobPhase.QUEUED,
            EnrichmentJobPhase.EXECUTING,
        ):
            return await self._store.mark_failed(
                job_id,
                error_code=error_code,
                error_message=error_message,
            )
        if job.phase == EnrichmentJobPhase.ERROR:
            return job
        raise InvalidEnrichmentJobTransitionError(
            job.id, job.phase, EnrichmentJobPhase.ERROR
        )
