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

    async def get(self, job_id: int) -> SerializedEnrichmentJob: ...

    async def get_internal(self, job_id: int) -> StoredEnrichmentJob: ...

    async def mark_queued(self, job_id: int) -> SerializedEnrichmentJob: ...

    async def mark_executing(self, job_id: int) -> SerializedEnrichmentJob: ...

    async def mark_completed(self, job_id: int) -> SerializedEnrichmentJob: ...

    async def mark_failed(
        self, job_id: int, *, error_code: str, error_message: str
    ) -> SerializedEnrichmentJob: ...


class EnrichmentQueueStoreProtocol(Protocol):
    """Queue operations required by `EnrichmentJobService`."""

    async def enqueue(self, job_id: int) -> str: ...

    async def abort(self, arq_job_id: str) -> bool: ...

    async def status(self, arq_job_id: str) -> str | None: ...

    async def succeeded(self, arq_job_id: str) -> bool | None: ...


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

    async def get(self, job_id: int) -> SerializedEnrichmentJob:
        """Retrieve an enrichment job with live queue status overlay."""
        if self._queue is None:
            return await self._store.get(job_id)

        job = await self._store.get_internal(job_id)
        if not job.arq_job_id:
            return self._public(job)

        status = await self._queue.status(job.arq_job_id)
        if status == "in_progress" and job.phase == EnrichmentJobPhase.QUEUED:
            return self._public(
                job.model_copy(update={"phase": EnrichmentJobPhase.EXECUTING})
            )
        if status == "complete" and job.phase in (
            EnrichmentJobPhase.PENDING,
            EnrichmentJobPhase.QUEUED,
            EnrichmentJobPhase.EXECUTING,
        ):
            success = await self._queue.succeeded(job.arq_job_id)
            if success is False:
                return self._public(
                    job.model_copy(
                        update={
                            "phase": EnrichmentJobPhase.ERROR,
                            "error_code": "WorkerError",
                            "error_message": "Enrichment worker failed",
                        }
                    )
                )
            if success is True:
                return self._public(
                    job.model_copy(
                        update={"phase": EnrichmentJobPhase.COMPLETED}
                    )
                )
        return self._public(job)

    async def abort(self, job_id: int) -> bool:
        """Abort an enqueued enrichment job."""
        if self._queue is None:
            raise RuntimeError("Enrichment queue is not configured")

        job = await self._store.get_internal(job_id)
        if not job.arq_job_id or not await self._queue.abort(job.arq_job_id):
            return False
        await self._store.mark_failed(
            job_id,
            error_code="JobAborted",
            error_message="Enrichment job aborted",
        )
        return True

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
