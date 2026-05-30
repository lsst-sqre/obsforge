"""Business logic for visit enrichment jobs."""

from typing import Protocol

from obsforge.models import (
    SerializedEnrichmentJob,
    StoredEnrichmentJob,
    VisitRegistration,
)
from obsforge.schema import EnrichmentJobPhase

__all__ = ["EnrichmentJobService"]


class EnrichmentJobStoreProtocol(Protocol):
    """Storage operations required by `EnrichmentJobService`."""

    async def add_or_get(
        self, registration: VisitRegistration
    ) -> SerializedEnrichmentJob: ...

    async def add_or_get_internal(
        self, registration: VisitRegistration
    ) -> StoredEnrichmentJob: ...

    async def set_arq_job_id_and_mark_queued(
        self, job_id: int, arq_job_id: str
    ) -> SerializedEnrichmentJob: ...

    async def mark_queued(self, job_id: int) -> SerializedEnrichmentJob: ...

    async def mark_executing(self, job_id: int) -> SerializedEnrichmentJob: ...

    async def mark_completed(self, job_id: int) -> SerializedEnrichmentJob: ...

    async def mark_failed(
        self, job_id: int, *, error_code: str, error_message: str
    ) -> SerializedEnrichmentJob: ...


class EnrichmentQueueStoreProtocol(Protocol):
    """Queue operations required by `EnrichmentJobService`."""

    async def enqueue(self, job_id: int) -> str: ...


class EnrichmentJobService:
    """Apply enrichment workflow rules around durable job state."""

    def __init__(
        self,
        store: EnrichmentJobStoreProtocol,
        queue: EnrichmentQueueStoreProtocol | None = None,
    ) -> None:
        self._store = store
        self._queue = queue

    async def register_visit(
        self, registration: VisitRegistration
    ) -> SerializedEnrichmentJob:
        """Register one visit for enrichment.

        Duplicate registration is handled idempotently by storage, returning
        the existing job for the visit.
        """
        if self._queue is None:
            return await self._store.add_or_get(registration)

        job = await self._store.add_or_get_internal(registration)
        if self._should_enqueue(job):
            arq_job_id = await self._queue.enqueue(job.id)
            return await self._store.set_arq_job_id_and_mark_queued(
                job.id, arq_job_id
            )
        return self._public(job)

    async def mark_queued(self, job_id: int) -> SerializedEnrichmentJob:
        """Mark a registered job as queued without regressing active jobs."""
        return await self._store.mark_queued(job_id)

    async def mark_executing(self, job_id: int) -> SerializedEnrichmentJob:
        """Mark a queued job as executing."""
        return await self._store.mark_executing(job_id)

    async def mark_completed(self, job_id: int) -> SerializedEnrichmentJob:
        """Mark an executing job as completed."""
        return await self._store.mark_completed(job_id)

    async def mark_failed(
        self, job_id: int, *, error_code: str, error_message: str
    ) -> SerializedEnrichmentJob:
        """Record a failed enrichment attempt."""
        return await self._store.mark_failed(
            job_id, error_code=error_code, error_message=error_message
        )

    def _should_enqueue(self, job: StoredEnrichmentJob) -> bool:
        return (
            job.phase
            in {
                EnrichmentJobPhase.PENDING,
                EnrichmentJobPhase.QUEUED,
            }
            and not job.arq_job_id
        )

    def _public(self, job: StoredEnrichmentJob) -> SerializedEnrichmentJob:
        return SerializedEnrichmentJob.model_validate(
            job.model_dump(exclude={"arq_job_id"})
        )
