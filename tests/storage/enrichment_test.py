"""Tests for enrichment job storage."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge.exceptions import UnknownEnrichmentJobError
from obsforge.models import VisitRegistration, VisitTimespan
from obsforge.schema import EnrichmentJobPhase
from obsforge.storage import EnrichmentJobStore


def make_registration(
    *,
    visit_id: str = "LSSTCam-20260327-123456",
    day_obs: int = 20260327,
) -> VisitRegistration:
    return VisitRegistration(
        instrument="LSSTCam",
        day_obs=day_obs,
        visit_id=visit_id,
        timespan=VisitTimespan(
            begin=datetime(2026, 3, 27, 8, 15, 10, tzinfo=UTC),
            end=datetime(2026, 3, 27, 8, 15, 45, tzinfo=UTC),
        ),
    )


@pytest.mark.asyncio
async def test_add_or_get_is_idempotent(db_session: AsyncSession) -> None:
    store = EnrichmentJobStore(db_session)
    registration = make_registration()
    duplicate = make_registration(day_obs=20260328)

    first = await store.add_or_get(registration)
    second = await store.add_or_get(duplicate)

    assert second == first
    assert first.visit_id == registration.visit_id
    assert first.day_obs == 20260327
    assert first.phase == EnrichmentJobPhase.PENDING
    assert first.registration_payload == registration.model_dump(mode="json")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phase",
    [
        EnrichmentJobPhase.QUEUED,
        EnrichmentJobPhase.EXECUTING,
        EnrichmentJobPhase.COMPLETED,
    ],
)
async def test_add_or_get_preserves_active_or_completed_duplicates(
    db_session: AsyncSession, phase: EnrichmentJobPhase
) -> None:
    store = EnrichmentJobStore(db_session)
    registration = make_registration()
    created = await store.add_or_get(registration)

    if phase == EnrichmentJobPhase.QUEUED:
        expected = await store.mark_queued(created.id)
    elif phase == EnrichmentJobPhase.EXECUTING:
        expected = await store.mark_executing(created.id)
    else:
        await store.mark_executing(created.id)
        expected = await store.mark_completed(created.id)

    duplicate = await store.add_or_get(registration)

    assert duplicate == expected


@pytest.mark.asyncio
async def test_add_or_get_requeues_error_duplicate(
    db_session: AsyncSession,
) -> None:
    store = EnrichmentJobStore(db_session)
    registration = make_registration()
    created = await store.add_or_get(registration)
    await store.mark_executing(created.id)
    failed = await store.mark_failed(
        created.id,
        error_code="ButlerError",
        error_message="metadata missing",
    )

    requeued = await store.add_or_get(registration)

    assert requeued.id == failed.id
    assert requeued.visit_id == failed.visit_id
    assert requeued.phase == EnrichmentJobPhase.QUEUED
    assert requeued.error_code is None
    assert requeued.error_message is None
    assert requeued.started_at is None
    assert requeued.completed_at is None
    assert requeued.updated_at >= failed.updated_at


@pytest.mark.asyncio
async def test_get_by_visit_id(db_session: AsyncSession) -> None:
    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration())

    seen = await store.get_by_visit_id(created.visit_id)

    assert seen == created


@pytest.mark.asyncio
async def test_phase_updates(db_session: AsyncSession) -> None:
    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration())

    queued = await store.mark_queued(created.id)
    executing = await store.mark_executing(created.id)
    completed = await store.mark_completed(created.id)

    assert queued.phase == EnrichmentJobPhase.QUEUED
    assert executing.phase == EnrichmentJobPhase.EXECUTING
    assert executing.started_at is not None
    assert completed.phase == EnrichmentJobPhase.COMPLETED
    assert completed.started_at == executing.started_at
    assert completed.completed_at is not None


@pytest.mark.asyncio
async def test_mark_failed_records_error_summary(
    db_session: AsyncSession,
) -> None:
    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration())
    await store.mark_executing(created.id)

    failed = await store.mark_failed(
        created.id,
        error_code="ButlerError",
        error_message="metadata missing",
    )

    assert failed.phase == EnrichmentJobPhase.ERROR
    assert failed.error_code == "ButlerError"
    assert failed.error_message == "metadata missing"
    assert failed.started_at is not None
    assert failed.completed_at is not None


@pytest.mark.asyncio
async def test_get_unknown_job_raises(db_session: AsyncSession) -> None:
    store = EnrichmentJobStore(db_session)

    with pytest.raises(UnknownEnrichmentJobError):
        await store.get(404)


@pytest.mark.asyncio
async def test_get_unknown_visit_raises(db_session: AsyncSession) -> None:
    store = EnrichmentJobStore(db_session)

    with pytest.raises(UnknownEnrichmentJobError):
        await store.get_by_visit_id("unknown-visit")
