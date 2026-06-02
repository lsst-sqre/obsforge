"""Storage layer for visit enrichment jobs."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from safir.database import (
    datetime_from_db,
    datetime_to_db,
    retry_async_transaction,
)
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge.exceptions import (
    InvalidEnrichmentJobTransitionError,
    UnknownEnrichmentJobError,
)
from obsforge.models import (
    SerializedEnrichmentJob,
    StoredEnrichmentJob,
    VisitRegistration,
)
from obsforge.schema import EnrichmentJob as SQLEnrichmentJob
from obsforge.schema import EnrichmentJobPhase

__all__ = ["EnrichmentJobStore"]


class EnrichmentJobStore:
    """Stores and manipulates visit enrichment jobs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @retry_async_transaction
    async def add_or_get(
        self, registration: VisitRegistration
    ) -> SerializedEnrichmentJob:
        """Create a pending job or return the existing duplicate."""
        return self._to_public(await self.add_or_get_internal(registration))

    @retry_async_transaction
    async def add_or_get_internal(
        self, registration: VisitRegistration
    ) -> StoredEnrichmentJob:
        """Create a pending job or return the existing duplicate."""
        now = datetime.now(tz=UTC).replace(microsecond=0)
        db_now = datetime_to_db(now)
        payload = registration.model_dump(mode="json")
        stmt = (
            insert(SQLEnrichmentJob)
            .values(
                visit_id=registration.visit_id,
                instrument_name=registration.instrument_name,
                day_obs=registration.day_obs,
                phase=EnrichmentJobPhase.PENDING,
                registration_payload=payload,
                created_at=db_now,
                updated_at=db_now,
            )
            .on_conflict_do_nothing(constraint="enrichment_job_visit_id_key")
            .returning(SQLEnrichmentJob.id)
        )
        async with self._session.begin():
            job_id = (await self._session.execute(stmt)).scalar_one_or_none()
            if job_id is not None:
                job = await self._get_by_id(job_id)
            else:
                job = await self._get_by_visit_id(registration.visit_id)
                if job.phase == EnrichmentJobPhase.ERROR:
                    job.phase = EnrichmentJobPhase.QUEUED
                    job.error_code = None
                    job.error_message = None
                    job.arq_job_id = None
                    job.started_at = None
                    job.completed_at = None
                    job.updated_at = db_now
            return self._serialize_internal(job)

    async def get(self, job_id: int) -> SerializedEnrichmentJob:
        """Retrieve an enrichment job by ID."""
        async with self._session.begin():
            return self._serialize(await self._get_by_id(job_id))

    async def get_internal(self, job_id: int) -> StoredEnrichmentJob:
        """Retrieve an enrichment job by ID, including queue state."""
        async with self._session.begin():
            return self._serialize_internal(await self._get_by_id(job_id))

    async def get_by_visit_id(self, visit_id: str) -> SerializedEnrichmentJob:
        """Retrieve an enrichment job by visit ID."""
        async with self._session.begin():
            job = await self._get_by_visit_id(visit_id)
            return self._serialize(job)

    @retry_async_transaction
    async def set_arq_job_id_and_mark_queued(
        self, job_id: int, arq_job_id: str
    ) -> SerializedEnrichmentJob:
        """Record the arq job ID and mark the durable job as queued."""
        async with self._session.begin():
            return await self._transition(
                job_id,
                requested=EnrichmentJobPhase.QUEUED,
                allowed_current=(
                    EnrichmentJobPhase.PENDING,
                    EnrichmentJobPhase.QUEUED,
                ),
                idempotent_current=(
                    EnrichmentJobPhase.EXECUTING,
                    EnrichmentJobPhase.COMPLETED,
                    EnrichmentJobPhase.ERROR,
                ),
                values={
                    "phase": EnrichmentJobPhase.QUEUED,
                    "arq_job_id": arq_job_id,
                    "updated_at": self._now_for_db(),
                },
            )

    @retry_async_transaction
    async def mark_queued(self, job_id: int) -> SerializedEnrichmentJob:
        """Mark a pending job as queued."""
        async with self._session.begin():
            return await self._transition(
                job_id,
                requested=EnrichmentJobPhase.QUEUED,
                allowed_current=(EnrichmentJobPhase.PENDING,),
                idempotent_current=(
                    EnrichmentJobPhase.QUEUED,
                    EnrichmentJobPhase.EXECUTING,
                    EnrichmentJobPhase.COMPLETED,
                    EnrichmentJobPhase.ERROR,
                ),
                values={
                    "phase": EnrichmentJobPhase.QUEUED,
                    "updated_at": self._now_for_db(),
                },
            )

    @retry_async_transaction
    async def mark_executing(self, job_id: int) -> SerializedEnrichmentJob:
        """Mark a job as executing."""
        async with self._session.begin():
            now = self._now_for_db()
            return await self._transition(
                job_id,
                requested=EnrichmentJobPhase.EXECUTING,
                allowed_current=(
                    EnrichmentJobPhase.PENDING,
                    EnrichmentJobPhase.QUEUED,
                ),
                idempotent_current=(EnrichmentJobPhase.EXECUTING,),
                values={
                    "phase": EnrichmentJobPhase.EXECUTING,
                    "error_code": None,
                    "error_message": None,
                    "started_at": func.coalesce(
                        SQLEnrichmentJob.started_at, now
                    ),
                    "updated_at": now,
                },
            )

    @retry_async_transaction
    async def mark_completed(self, job_id: int) -> SerializedEnrichmentJob:
        """Mark a job as completed."""
        async with self._session.begin():
            now = self._now_for_db()
            return await self._transition(
                job_id,
                requested=EnrichmentJobPhase.COMPLETED,
                allowed_current=(EnrichmentJobPhase.EXECUTING,),
                idempotent_current=(EnrichmentJobPhase.COMPLETED,),
                values={
                    "phase": EnrichmentJobPhase.COMPLETED,
                    "started_at": func.coalesce(
                        SQLEnrichmentJob.started_at, now
                    ),
                    "completed_at": now,
                    "updated_at": now,
                },
            )

    @retry_async_transaction
    async def mark_failed(
        self, job_id: int, *, error_code: str, error_message: str
    ) -> SerializedEnrichmentJob:
        """Mark a job as failed with the latest error summary."""
        async with self._session.begin():
            now = self._now_for_db()
            return await self._transition(
                job_id,
                requested=EnrichmentJobPhase.ERROR,
                allowed_current=(
                    EnrichmentJobPhase.PENDING,
                    EnrichmentJobPhase.QUEUED,
                    EnrichmentJobPhase.EXECUTING,
                ),
                idempotent_current=(EnrichmentJobPhase.ERROR,),
                values={
                    "phase": EnrichmentJobPhase.ERROR,
                    "error_code": error_code,
                    "error_message": error_message,
                    "started_at": func.coalesce(
                        SQLEnrichmentJob.started_at, now
                    ),
                    "completed_at": now,
                    "updated_at": now,
                },
            )

    async def _get_by_id(self, job_id: int) -> SQLEnrichmentJob:
        stmt = select(SQLEnrichmentJob).where(SQLEnrichmentJob.id == job_id)
        job = (await self._session.execute(stmt)).scalar_one_or_none()
        if not job:
            raise UnknownEnrichmentJobError(job_id)
        return job

    async def _get_by_visit_id(self, visit_id: str) -> SQLEnrichmentJob:
        stmt = select(SQLEnrichmentJob).where(
            SQLEnrichmentJob.visit_id == visit_id
        )
        job = (await self._session.execute(stmt)).scalar_one_or_none()
        if not job:
            raise UnknownEnrichmentJobError(-1)
        return job

    def _serialize(self, job: SQLEnrichmentJob) -> SerializedEnrichmentJob:
        return self._to_public(self._serialize_internal(job))

    def _serialize_internal(
        self, job: SQLEnrichmentJob
    ) -> StoredEnrichmentJob:
        created_at = datetime_from_db(job.created_at)
        updated_at = datetime_from_db(job.updated_at)
        return StoredEnrichmentJob(
            id=job.id,
            visit_id=job.visit_id,
            instrument_name=job.instrument_name,
            day_obs=job.day_obs,
            phase=job.phase,
            error_code=job.error_code,
            error_message=job.error_message,
            arq_job_id=job.arq_job_id,
            registration_payload=job.registration_payload,
            created_at=created_at,
            updated_at=updated_at,
            started_at=datetime_from_db(job.started_at),
            completed_at=datetime_from_db(job.completed_at),
        )

    def _to_public(self, job: StoredEnrichmentJob) -> SerializedEnrichmentJob:
        return SerializedEnrichmentJob.model_validate(
            job.model_dump(exclude={"arq_job_id"})
        )

    async def _transition(
        self,
        job_id: int,
        *,
        requested: EnrichmentJobPhase,
        allowed_current: Sequence[EnrichmentJobPhase],
        idempotent_current: Sequence[EnrichmentJobPhase],
        values: Mapping[str, Any],
    ) -> SerializedEnrichmentJob:
        stmt = (
            update(SQLEnrichmentJob)
            .where(SQLEnrichmentJob.id == job_id)
            .where(SQLEnrichmentJob.phase.in_(allowed_current))
            .values(values)
            .returning(SQLEnrichmentJob)
        )
        job = (await self._session.execute(stmt)).scalar_one_or_none()
        if job:
            return self._serialize(job)

        current = await self._get_by_id(job_id)
        # Some transitions are safe to repeat after another worker already
        # reached the requested state, so treat those current phases as no-ops.
        if current.phase in idempotent_current:
            return self._serialize(current)
        raise InvalidEnrichmentJobTransitionError(
            job_id, current.phase, requested
        )

    def _now_for_db(self) -> datetime:
        now = datetime.now(tz=UTC).replace(microsecond=0)
        db_now = datetime_to_db(now)
        if db_now is None:
            raise RuntimeError("Current time unexpectedly converted to None")
        return db_now
