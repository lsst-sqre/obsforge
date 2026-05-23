"""Storage layer for visit enrichment jobs."""

from datetime import UTC, datetime

from safir.database import (
    datetime_from_db,
    datetime_to_db,
    retry_async_transaction,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge.exceptions import UnknownEnrichmentJobError
from obsforge.models import SerializedEnrichmentJob, VisitRegistration
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
        now = datetime.now(tz=UTC).replace(microsecond=0)
        db_now = datetime_to_db(now)
        payload = registration.model_dump(mode="json")
        stmt = (
            insert(SQLEnrichmentJob)
            .values(
                visit=registration.visit,
                instrument=registration.instrument,
                day_obs=registration.day_obs,
                phase=EnrichmentJobPhase.PENDING,
                registration_payload=payload,
                created_at=db_now,
                updated_at=db_now,
            )
            .on_conflict_do_nothing(
                constraint="enrichment_job_instrument_visit_key"
            )
            .returning(SQLEnrichmentJob.id)
        )
        async with self._session.begin():
            job_id = (await self._session.execute(stmt)).scalar_one_or_none()
            if job_id is not None:
                job = await self._get_by_id(job_id)
            else:
                job = await self._get_by_instrument_visit(
                    registration.instrument, registration.visit
                )
                if job.phase == EnrichmentJobPhase.ERROR:
                    job.phase = EnrichmentJobPhase.QUEUED
                    job.error_code = None
                    job.error_message = None
                    job.started_at = None
                    job.completed_at = None
                    job.updated_at = db_now
            return self._serialize(job)

    async def get(self, job_id: int) -> SerializedEnrichmentJob:
        """Retrieve an enrichment job by ID."""
        async with self._session.begin():
            return self._serialize(await self._get_by_id(job_id))

    async def get_by_instrument_visit(
        self, instrument: str, visit: int
    ) -> SerializedEnrichmentJob:
        """Retrieve an enrichment job by instrument and visit."""
        async with self._session.begin():
            job = await self._get_by_instrument_visit(instrument, visit)
            return self._serialize(job)

    @retry_async_transaction
    async def mark_queued(self, job_id: int) -> SerializedEnrichmentJob:
        """Mark a pending job as queued."""
        async with self._session.begin():
            job = await self._get_by_id(job_id)
            job.phase = EnrichmentJobPhase.QUEUED
            job.updated_at = self._now_for_db()
            return self._serialize(job)

    @retry_async_transaction
    async def mark_executing(self, job_id: int) -> SerializedEnrichmentJob:
        """Mark a job as executing."""
        async with self._session.begin():
            job = await self._get_by_id(job_id)
            now = self._now_for_db()
            job.phase = EnrichmentJobPhase.EXECUTING
            job.error_code = None
            job.error_message = None
            job.started_at = job.started_at or now
            job.updated_at = now
            return self._serialize(job)

    @retry_async_transaction
    async def mark_completed(self, job_id: int) -> SerializedEnrichmentJob:
        """Mark a job as completed."""
        async with self._session.begin():
            job = await self._get_by_id(job_id)
            now = self._now_for_db()
            job.phase = EnrichmentJobPhase.COMPLETED
            job.started_at = job.started_at or now
            job.completed_at = now
            job.updated_at = now
            return self._serialize(job)

    @retry_async_transaction
    async def mark_failed(
        self, job_id: int, *, error_code: str, error_message: str
    ) -> SerializedEnrichmentJob:
        """Mark a job as failed with the latest error summary."""
        async with self._session.begin():
            job = await self._get_by_id(job_id)
            now = self._now_for_db()
            job.phase = EnrichmentJobPhase.ERROR
            job.error_code = error_code
            job.error_message = error_message
            job.started_at = job.started_at or now
            job.completed_at = now
            job.updated_at = now
            return self._serialize(job)

    async def _get_by_id(self, job_id: int) -> SQLEnrichmentJob:
        stmt = select(SQLEnrichmentJob).where(SQLEnrichmentJob.id == job_id)
        job = (await self._session.execute(stmt)).scalar_one_or_none()
        if not job:
            raise UnknownEnrichmentJobError(job_id)
        return job

    async def _get_by_instrument_visit(
        self, instrument: str, visit: int
    ) -> SQLEnrichmentJob:
        stmt = select(SQLEnrichmentJob).where(
            SQLEnrichmentJob.instrument == instrument,
            SQLEnrichmentJob.visit == visit,
        )
        job = (await self._session.execute(stmt)).scalar_one_or_none()
        if not job:
            raise UnknownEnrichmentJobError(-1)
        return job

    def _serialize(self, job: SQLEnrichmentJob) -> SerializedEnrichmentJob:
        created_at = datetime_from_db(job.created_at)
        updated_at = datetime_from_db(job.updated_at)
        return SerializedEnrichmentJob(
            id=job.id,
            visit=job.visit,
            instrument=job.instrument,
            day_obs=job.day_obs,
            phase=job.phase,
            error_code=job.error_code,
            error_message=job.error_message,
            registration_payload=job.registration_payload,
            created_at=created_at,
            updated_at=updated_at,
            started_at=datetime_from_db(job.started_at),
            completed_at=datetime_from_db(job.completed_at),
        )

    def _now_for_db(self) -> datetime:
        now = datetime.now(tz=UTC).replace(microsecond=0)
        db_now = datetime_to_db(now)
        if db_now is None:
            raise RuntimeError("Current time unexpectedly converted to None")
        return db_now
