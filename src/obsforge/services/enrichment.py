"""Business logic for visit enrichment jobs."""

from typing import Protocol

from obsforge.models import SerializedEnrichmentJob, VisitRegistration

__all__ = ["EnrichmentJobService"]


class EnrichmentJobStoreProtocol(Protocol):
    """Storage operations required by `EnrichmentJobService`."""

    async def add_or_get(
        self, registration: VisitRegistration
    ) -> SerializedEnrichmentJob: ...

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
