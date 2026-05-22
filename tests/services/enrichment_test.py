"""Tests for enrichment job business logic."""

from datetime import UTC, datetime

import pytest

from obsforge.exceptions import InvalidEnrichmentJobTransitionError
from obsforge.models import (
    SerializedEnrichmentJob,
    VisitRegistration,
    VisitTimespan,
)
from obsforge.schema import EnrichmentJobPhase
from obsforge.services import EnrichmentJobService


def make_registration() -> VisitRegistration:
    return VisitRegistration(
        instrument="LSSTCam",
        day_obs=20260108,
        visit=2026010800095,
        timespan=VisitTimespan(
            begin=datetime(2026, 1, 9, 2, 45, 51, tzinfo=UTC),
            end=datetime(2026, 1, 9, 2, 46, 26, tzinfo=UTC),
        ),
    )


def make_job(
    phase: EnrichmentJobPhase = EnrichmentJobPhase.PENDING,
) -> SerializedEnrichmentJob:
    now = datetime(2026, 1, 9, 2, 45, 51, tzinfo=UTC)
    return SerializedEnrichmentJob(
        id=1,
        visit=2026010800095,
        instrument="LSSTCam",
        day_obs=20260108,
        phase=phase,
        attempt_count=0,
        error_code=None,
        error_message=None,
        registration_payload=make_registration().model_dump(mode="json"),
        created_at=now,
        updated_at=now,
        started_at=None,
        completed_at=None,
    )


class FakeEnrichmentJobStore:
    def __init__(self, job: SerializedEnrichmentJob | None = None) -> None:
        self.job = job or make_job()
        self.calls: list[str] = []

    async def add_or_get(
        self, registration: VisitRegistration
    ) -> SerializedEnrichmentJob:
        self.calls.append("add_or_get")
        return self.job

    async def get(self, job_id: int) -> SerializedEnrichmentJob:
        self.calls.append("get")
        return self.job

    async def mark_queued(self, job_id: int) -> SerializedEnrichmentJob:
        self.calls.append("mark_queued")
        self.job = self.job.model_copy(
            update={"phase": EnrichmentJobPhase.QUEUED}
        )
        return self.job

    async def mark_executing(self, job_id: int) -> SerializedEnrichmentJob:
        self.calls.append("mark_executing")
        self.job = self.job.model_copy(
            update={
                "phase": EnrichmentJobPhase.EXECUTING,
                "attempt_count": self.job.attempt_count + 1,
            }
        )
        return self.job

    async def mark_completed(self, job_id: int) -> SerializedEnrichmentJob:
        self.calls.append("mark_completed")
        self.job = self.job.model_copy(
            update={"phase": EnrichmentJobPhase.COMPLETED}
        )
        return self.job

    async def mark_failed(
        self, job_id: int, *, error_code: str, error_message: str
    ) -> SerializedEnrichmentJob:
        self.calls.append("mark_failed")
        self.job = self.job.model_copy(
            update={
                "phase": EnrichmentJobPhase.ERROR,
                "error_code": error_code,
                "error_message": error_message,
            }
        )
        return self.job


@pytest.mark.asyncio
async def test_register_visit_adds_or_gets_job() -> None:
    store = FakeEnrichmentJobStore()
    service = EnrichmentJobService(store)

    job = await service.register_visit(make_registration())

    assert job == store.job
    assert store.calls == ["add_or_get"]


@pytest.mark.asyncio
async def test_mark_queued_transitions_pending_job() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.PENDING))
    service = EnrichmentJobService(store)

    job = await service.mark_queued(1)

    assert job.phase == EnrichmentJobPhase.QUEUED
    assert store.calls == ["get", "mark_queued"]


@pytest.mark.asyncio
async def test_mark_queued_does_not_regress_executing_job() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.EXECUTING))
    service = EnrichmentJobService(store)

    job = await service.mark_queued(1)

    assert job.phase == EnrichmentJobPhase.EXECUTING
    assert store.calls == ["get"]


@pytest.mark.asyncio
async def test_mark_executing_records_attempt() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.QUEUED))
    service = EnrichmentJobService(store)

    job = await service.mark_executing(1)

    assert job.phase == EnrichmentJobPhase.EXECUTING
    assert job.attempt_count == 1
    assert store.calls == ["get", "mark_executing"]


@pytest.mark.asyncio
async def test_mark_completed_rejects_pending_job() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.PENDING))
    service = EnrichmentJobService(store)

    with pytest.raises(InvalidEnrichmentJobTransitionError):
        await service.mark_completed(1)

    assert store.calls == ["get"]


@pytest.mark.asyncio
async def test_mark_failed_records_error_summary() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.EXECUTING))
    service = EnrichmentJobService(store)

    job = await service.mark_failed(
        1, error_code="ButlerError", error_message="metadata missing"
    )

    assert job.phase == EnrichmentJobPhase.ERROR
    assert job.error_code == "ButlerError"
    assert job.error_message == "metadata missing"
    assert store.calls == ["get", "mark_failed"]
