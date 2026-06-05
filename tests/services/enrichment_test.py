"""Tests for enrichment job business logic."""

from datetime import UTC, datetime

import pytest
from structlog.testing import capture_logs

from obsforge.exceptions import InvalidEnrichmentJobTransitionError
from obsforge.models import (
    SerializedEnrichmentJob,
    StoredEnrichmentJob,
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
        error_code=None,
        error_message=None,
        registration_payload=make_registration().model_dump(mode="json"),
        created_at=now,
        updated_at=now,
        started_at=None,
        completed_at=None,
    )


class FakeEnrichmentJobStore:
    def __init__(
        self,
        job: SerializedEnrichmentJob | None = None,
        *,
        arq_job_id: str | None = None,
    ) -> None:
        self.job = job or make_job()
        self.arq_job_id = arq_job_id
        self.calls: list[str] = []

    async def add_or_get(
        self, registration: VisitRegistration
    ) -> SerializedEnrichmentJob:
        self.calls.append("add_or_get")
        return self.job

    async def add_or_get_internal(
        self, registration: VisitRegistration
    ) -> StoredEnrichmentJob:
        self.calls.append("add_or_get_internal")
        return StoredEnrichmentJob.model_validate(
            self.job.model_dump() | {"arq_job_id": self.arq_job_id}
        )

    async def set_arq_job_id_and_mark_queued(
        self, job_id: int, arq_job_id: str
    ) -> SerializedEnrichmentJob:
        self.calls.append("set_arq_job_id_and_mark_queued")
        self.arq_job_id = arq_job_id
        self.job = self.job.model_copy(
            update={"phase": EnrichmentJobPhase.QUEUED}
        )
        return self.job

    async def get(self, job_id: int) -> SerializedEnrichmentJob:
        self.calls.append("get")
        return self.job

    async def get_internal(self, job_id: int) -> StoredEnrichmentJob:
        self.calls.append("get_internal")
        return StoredEnrichmentJob.model_validate(
            self.job.model_dump() | {"arq_job_id": self.arq_job_id}
        )

    async def mark_queued(self, job_id: int) -> SerializedEnrichmentJob:
        self.calls.append("mark_queued")
        if self.job.phase == EnrichmentJobPhase.PENDING:
            self.job = self.job.model_copy(
                update={"phase": EnrichmentJobPhase.QUEUED}
            )
        return self.job

    async def mark_executing(self, job_id: int) -> SerializedEnrichmentJob:
        self.calls.append("mark_executing")
        if self.job.phase in (
            EnrichmentJobPhase.PENDING,
            EnrichmentJobPhase.QUEUED,
        ):
            self.job = self.job.model_copy(
                update={"phase": EnrichmentJobPhase.EXECUTING}
            )
        elif self.job.phase != EnrichmentJobPhase.EXECUTING:
            raise InvalidEnrichmentJobTransitionError(
                self.job.id,
                self.job.phase,
                EnrichmentJobPhase.EXECUTING,
            )
        return self.job

    async def mark_completed(self, job_id: int) -> SerializedEnrichmentJob:
        self.calls.append("mark_completed")
        if self.job.phase == EnrichmentJobPhase.EXECUTING:
            self.job = self.job.model_copy(
                update={"phase": EnrichmentJobPhase.COMPLETED}
            )
        elif self.job.phase != EnrichmentJobPhase.COMPLETED:
            raise InvalidEnrichmentJobTransitionError(
                self.job.id,
                self.job.phase,
                EnrichmentJobPhase.COMPLETED,
            )
        return self.job

    async def mark_failed(
        self, job_id: int, *, error_code: str, error_message: str
    ) -> SerializedEnrichmentJob:
        self.calls.append("mark_failed")
        if self.job.phase in (
            EnrichmentJobPhase.PENDING,
            EnrichmentJobPhase.QUEUED,
            EnrichmentJobPhase.EXECUTING,
        ):
            self.job = self.job.model_copy(
                update={
                    "phase": EnrichmentJobPhase.ERROR,
                    "error_code": error_code,
                    "error_message": error_message,
                }
            )
        elif self.job.phase != EnrichmentJobPhase.ERROR:
            raise InvalidEnrichmentJobTransitionError(
                self.job.id,
                self.job.phase,
                EnrichmentJobPhase.ERROR,
            )
        return self.job


class FakeEnrichmentQueueStore:
    def __init__(self) -> None:
        self.calls: list[int] = []
        self.abort_calls: list[str] = []
        self.job_status: str | None = None
        self.job_success: bool | None = None
        self.abort_result = True

    async def enqueue(self, job_id: int) -> str:
        self.calls.append(job_id)
        return f"arq-{job_id}"

    async def abort(self, arq_job_id: str) -> bool:
        self.abort_calls.append(arq_job_id)
        return self.abort_result

    async def status(self, arq_job_id: str) -> str | None:
        return self.job_status

    async def succeeded(self, arq_job_id: str) -> bool | None:
        return self.job_success


@pytest.mark.asyncio
async def test_register_visit_adds_or_gets_job() -> None:
    store = FakeEnrichmentJobStore()
    service = EnrichmentJobService(store)

    job = await service.register_visit(make_registration())

    assert job == store.job
    assert store.calls == ["add_or_get"]


@pytest.mark.asyncio
async def test_register_visit_enqueues_pending_job() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.PENDING))
    queue = FakeEnrichmentQueueStore()
    service = EnrichmentJobService(store, queue)

    job = await service.register_visit(make_registration())

    assert job.phase == EnrichmentJobPhase.QUEUED
    assert store.arq_job_id == "arq-1"
    assert queue.calls == [1]
    assert store.calls == [
        "add_or_get_internal",
        "set_arq_job_id_and_mark_queued",
    ]


@pytest.mark.asyncio
async def test_register_visit_logs_enqueued_job() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.PENDING))
    queue = FakeEnrichmentQueueStore()
    service = EnrichmentJobService(store, queue)

    with capture_logs() as logs:
        await service.register_visit(make_registration())

    assert [log["event"] for log in logs] == [
        "Registered enrichment job",
        "Queued enrichment job",
    ]
    assert logs[0] == {
        "event": "Registered enrichment job",
        "log_level": "info",
        "enrichment_job_id": 1,
        "visit": 2026010800095,
        "instrument": "LSSTCam",
        "day_obs": 20260108,
        "phase": "PENDING",
    }
    assert logs[1] == {
        "event": "Queued enrichment job",
        "log_level": "info",
        "enrichment_job_id": 1,
        "visit": 2026010800095,
        "instrument": "LSSTCam",
        "day_obs": 20260108,
        "phase": "QUEUED",
    }


@pytest.mark.asyncio
async def test_register_visit_does_not_info_log_duplicate_queue_job() -> None:
    store = FakeEnrichmentJobStore(
        make_job(EnrichmentJobPhase.QUEUED), arq_job_id="arq-1"
    )
    queue = FakeEnrichmentQueueStore()
    service = EnrichmentJobService(store, queue)

    with capture_logs() as logs:
        await service.register_visit(make_registration())

    assert logs == [
        {
            "event": "Enrichment job already registered",
            "log_level": "debug",
            "enrichment_job_id": 1,
            "visit": 2026010800095,
            "instrument": "LSSTCam",
            "day_obs": 20260108,
            "phase": "QUEUED",
            "arq_job_id": "arq-1",
        }
    ]


@pytest.mark.asyncio
async def test_register_visit_does_not_reenqueue_queued_job() -> None:
    store = FakeEnrichmentJobStore(
        make_job(EnrichmentJobPhase.QUEUED), arq_job_id="arq-1"
    )
    queue = FakeEnrichmentQueueStore()
    service = EnrichmentJobService(store, queue)

    job = await service.register_visit(make_registration())

    assert job.phase == EnrichmentJobPhase.QUEUED
    assert queue.calls == []
    assert store.calls == ["add_or_get_internal"]


@pytest.mark.asyncio
async def test_get_overlays_in_progress_queue_state() -> None:
    store = FakeEnrichmentJobStore(
        make_job(EnrichmentJobPhase.QUEUED), arq_job_id="arq-1"
    )
    queue = FakeEnrichmentQueueStore()
    queue.job_status = "in_progress"
    service = EnrichmentJobService(store, queue)

    job = await service.get(1)

    assert job.phase == EnrichmentJobPhase.EXECUTING
    assert store.calls == ["get_internal"]


@pytest.mark.asyncio
async def test_get_debug_logs_in_progress_queue_overlay() -> None:
    store = FakeEnrichmentJobStore(
        make_job(EnrichmentJobPhase.QUEUED), arq_job_id="arq-1"
    )
    queue = FakeEnrichmentQueueStore()
    queue.job_status = "in_progress"
    service = EnrichmentJobService(store, queue)

    with capture_logs() as logs:
        await service.get(1)

    assert logs == [
        {
            "event": "Overlaying enrichment job queue status",
            "log_level": "debug",
            "enrichment_job_id": 1,
            "visit": 2026010800095,
            "instrument": "LSSTCam",
            "day_obs": 20260108,
            "phase": "QUEUED",
            "arq_job_id": "arq-1",
            "arq_status": "in_progress",
            "overlay_phase": "EXECUTING",
        }
    ]


@pytest.mark.asyncio
async def test_get_overlays_successful_complete_queue_state() -> None:
    store = FakeEnrichmentJobStore(
        make_job(EnrichmentJobPhase.EXECUTING), arq_job_id="arq-1"
    )
    queue = FakeEnrichmentQueueStore()
    queue.job_status = "complete"
    queue.job_success = True
    service = EnrichmentJobService(store, queue)

    job = await service.get(1)

    assert job.phase == EnrichmentJobPhase.COMPLETED
    assert store.calls == ["get_internal"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("success_flag", "overlay_phase"),
    [(1, "COMPLETED"), (0, "ERROR")],
)
async def test_get_debug_logs_complete_queue_overlay(
    success_flag: int, overlay_phase: str
) -> None:
    success = bool(success_flag)
    store = FakeEnrichmentJobStore(
        make_job(EnrichmentJobPhase.EXECUTING), arq_job_id="arq-1"
    )
    queue = FakeEnrichmentQueueStore()
    queue.job_status = "complete"
    queue.job_success = success
    service = EnrichmentJobService(store, queue)

    with capture_logs() as logs:
        await service.get(1)

    assert logs == [
        {
            "event": "Overlaying enrichment job queue status",
            "log_level": "debug",
            "enrichment_job_id": 1,
            "visit": 2026010800095,
            "instrument": "LSSTCam",
            "day_obs": 20260108,
            "phase": "EXECUTING",
            "arq_job_id": "arq-1",
            "arq_status": "complete",
            "arq_success": success,
            "overlay_phase": overlay_phase,
        }
    ]


@pytest.mark.asyncio
async def test_abort_marks_job_failed() -> None:
    store = FakeEnrichmentJobStore(
        make_job(EnrichmentJobPhase.QUEUED), arq_job_id="arq-1"
    )
    queue = FakeEnrichmentQueueStore()
    service = EnrichmentJobService(store, queue)

    aborted = await service.abort(1)

    assert aborted is True
    assert queue.abort_calls == ["arq-1"]
    assert store.job.phase == EnrichmentJobPhase.ERROR
    assert store.job.error_code == "JobAborted"
    assert store.calls == ["get_internal", "mark_failed"]


@pytest.mark.asyncio
async def test_abort_logs_failed_job() -> None:
    store = FakeEnrichmentJobStore(
        make_job(EnrichmentJobPhase.QUEUED), arq_job_id="arq-1"
    )
    queue = FakeEnrichmentQueueStore()
    service = EnrichmentJobService(store, queue)

    with capture_logs() as logs:
        aborted = await service.abort(1)

    assert aborted is True
    assert logs == [
        {
            "event": "Aborted enrichment job",
            "log_level": "info",
            "enrichment_job_id": 1,
            "visit": 2026010800095,
            "instrument": "LSSTCam",
            "day_obs": 20260108,
            "phase": "ERROR",
            "error_code": "JobAborted",
            "error_message": "Enrichment job aborted",
        }
    ]


@pytest.mark.asyncio
async def test_mark_queued_transitions_pending_job() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.PENDING))
    service = EnrichmentJobService(store)

    job = await service.mark_queued(1)

    assert job.phase == EnrichmentJobPhase.QUEUED
    assert store.calls == ["mark_queued"]


@pytest.mark.asyncio
async def test_phase_updates_log_lifecycle_events() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.PENDING))
    service = EnrichmentJobService(store)

    with capture_logs() as logs:
        await service.mark_queued(1)
        await service.mark_executing(1)
        await service.mark_completed(1)

    assert [log["event"] for log in logs] == [
        "Marked enrichment job queued",
        "Marked enrichment job executing",
        "Completed enrichment job",
    ]
    assert [log["phase"] for log in logs] == [
        "QUEUED",
        "EXECUTING",
        "COMPLETED",
    ]
    for log in logs:
        assert log["log_level"] == "info"
        assert log["enrichment_job_id"] == 1
        assert log["visit"] == 2026010800095
        assert log["instrument"] == "LSSTCam"
        assert log["day_obs"] == 20260108


@pytest.mark.asyncio
async def test_mark_queued_does_not_regress_executing_job() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.EXECUTING))
    service = EnrichmentJobService(store)

    job = await service.mark_queued(1)

    assert job.phase == EnrichmentJobPhase.EXECUTING
    assert store.calls == ["mark_queued"]


@pytest.mark.asyncio
async def test_mark_executing_transitions_queued_job() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.QUEUED))
    service = EnrichmentJobService(store)

    job = await service.mark_executing(1)

    assert job.phase == EnrichmentJobPhase.EXECUTING
    assert store.calls == ["mark_executing"]


@pytest.mark.asyncio
async def test_mark_executing_returns_executing_job() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.EXECUTING))
    service = EnrichmentJobService(store)

    job = await service.mark_executing(1)

    assert job.phase == EnrichmentJobPhase.EXECUTING
    assert store.calls == ["mark_executing"]


@pytest.mark.asyncio
async def test_mark_executing_rejects_completed_job() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.COMPLETED))
    service = EnrichmentJobService(store)

    with pytest.raises(InvalidEnrichmentJobTransitionError):
        await service.mark_executing(1)

    assert store.calls == ["mark_executing"]


@pytest.mark.asyncio
async def test_mark_completed_transitions_executing_job() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.EXECUTING))
    service = EnrichmentJobService(store)

    job = await service.mark_completed(1)

    assert job.phase == EnrichmentJobPhase.COMPLETED
    assert store.calls == ["mark_completed"]


@pytest.mark.asyncio
async def test_mark_completed_returns_completed_job() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.COMPLETED))
    service = EnrichmentJobService(store)

    job = await service.mark_completed(1)

    assert job.phase == EnrichmentJobPhase.COMPLETED
    assert store.calls == ["mark_completed"]


@pytest.mark.asyncio
async def test_mark_completed_rejects_pending_job() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.PENDING))
    service = EnrichmentJobService(store)

    with pytest.raises(InvalidEnrichmentJobTransitionError):
        await service.mark_completed(1)

    assert store.calls == ["mark_completed"]


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
    assert store.calls == ["mark_failed"]


@pytest.mark.asyncio
async def test_mark_failed_logs_error_summary() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.EXECUTING))
    service = EnrichmentJobService(store)

    with capture_logs() as logs:
        await service.mark_failed(
            1, error_code="ButlerError", error_message="metadata missing"
        )

    assert logs == [
        {
            "event": "Failed enrichment job",
            "log_level": "info",
            "enrichment_job_id": 1,
            "visit": 2026010800095,
            "instrument": "LSSTCam",
            "day_obs": 20260108,
            "phase": "ERROR",
            "error_code": "ButlerError",
            "error_message": "metadata missing",
        }
    ]


@pytest.mark.asyncio
async def test_mark_failed_returns_failed_job() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.ERROR))
    service = EnrichmentJobService(store)

    job = await service.mark_failed(
        1, error_code="ButlerError", error_message="metadata missing"
    )

    assert job.phase == EnrichmentJobPhase.ERROR
    assert store.calls == ["mark_failed"]


@pytest.mark.asyncio
async def test_mark_failed_rejects_completed_job() -> None:
    store = FakeEnrichmentJobStore(make_job(EnrichmentJobPhase.COMPLETED))
    service = EnrichmentJobService(store)

    with pytest.raises(InvalidEnrichmentJobTransitionError):
        await service.mark_failed(
            1, error_code="ButlerError", error_message="metadata missing"
        )

    assert store.calls == ["mark_failed"]
