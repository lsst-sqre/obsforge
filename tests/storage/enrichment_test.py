"""Tests for enrichment job storage."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge.exceptions import (
    InvalidEnrichmentJobTransitionError,
    UnknownEnrichmentJobError,
    UnknownEnrichmentJobVisitError,
)
from obsforge.models import VisitDataset, VisitRegistration, VisitTimespan
from obsforge.schema import EnrichmentJobPhase
from obsforge.storage import EnrichmentJobStore


def make_registration(
    *,
    instrument: str = "LSSTCam",
    visit: int = 2026010800095,
    day_obs: int = 20260108,
) -> VisitRegistration:
    return VisitRegistration(
        instrument=instrument,
        day_obs=day_obs,
        visit=visit,
        datasets=[
            VisitDataset(
                dataset_type="preliminary_visit_image",
                id=UUID("019ba0a6-0173-765f-bf27-56884ff9342a"),
            )
        ],
        timespan=VisitTimespan(
            begin=datetime(2026, 1, 9, 2, 45, 51, tzinfo=UTC),
            end=datetime(2026, 1, 9, 2, 46, 26, tzinfo=UTC),
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
    assert first.visit == registration.visit
    assert first.day_obs == 20260108
    assert first.phase == EnrichmentJobPhase.PENDING
    assert first.registration_payload == registration.model_dump(mode="json")


@pytest.mark.asyncio
async def test_add_or_get_allows_same_visit_for_different_instruments(
    db_session: AsyncSession,
) -> None:
    store = EnrichmentJobStore(db_session)

    first = await store.add_or_get(make_registration(instrument="LSSTCam"))
    second = await store.add_or_get(make_registration(instrument="LATISS"))

    assert second.id != first.id
    assert second.visit == first.visit
    assert second.instrument == "LATISS"


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
    assert requeued.visit == failed.visit
    assert requeued.phase == EnrichmentJobPhase.QUEUED
    assert requeued.error_code is None
    assert requeued.error_message is None
    assert requeued.started_at is None
    assert requeued.completed_at is None
    assert requeued.updated_at >= failed.updated_at


@pytest.mark.asyncio
async def test_get_by_instrument_visit(db_session: AsyncSession) -> None:
    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration())

    seen = await store.get_by_instrument_visit(
        created.instrument, created.visit
    )

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
@pytest.mark.parametrize(
    "phase",
    [
        EnrichmentJobPhase.QUEUED,
        EnrichmentJobPhase.EXECUTING,
        EnrichmentJobPhase.COMPLETED,
        EnrichmentJobPhase.ERROR,
    ],
)
async def test_mark_queued_returns_non_pending_job(
    db_session: AsyncSession, phase: EnrichmentJobPhase
) -> None:
    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration())

    if phase == EnrichmentJobPhase.QUEUED:
        expected = await store.mark_queued(created.id)
    elif phase == EnrichmentJobPhase.EXECUTING:
        expected = await store.mark_executing(created.id)
    elif phase == EnrichmentJobPhase.COMPLETED:
        await store.mark_executing(created.id)
        expected = await store.mark_completed(created.id)
    else:
        expected = await store.mark_failed(
            created.id,
            error_code="ButlerError",
            error_message="metadata missing",
        )

    seen = await store.mark_queued(created.id)

    assert seen == expected


@pytest.mark.asyncio
async def test_mark_executing_returns_executing_job(
    db_session: AsyncSession,
) -> None:
    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration())
    executing = await store.mark_executing(created.id)

    seen = await store.mark_executing(created.id)

    assert seen == executing


@pytest.mark.asyncio
async def test_mark_completed_returns_completed_job(
    db_session: AsyncSession,
) -> None:
    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration())
    await store.mark_executing(created.id)
    completed = await store.mark_completed(created.id)

    seen = await store.mark_completed(created.id)

    assert seen == completed


@pytest.mark.asyncio
async def test_mark_failed_returns_error_job(
    db_session: AsyncSession,
) -> None:
    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration())
    failed = await store.mark_failed(
        created.id,
        error_code="ButlerError",
        error_message="metadata missing",
    )

    seen = await store.mark_failed(
        created.id,
        error_code="OtherError",
        error_message="new message",
    )

    assert seen == failed


@pytest.mark.asyncio
async def test_mark_completed_rejects_pending_job(
    db_session: AsyncSession,
) -> None:
    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration())

    with pytest.raises(InvalidEnrichmentJobTransitionError):
        await store.mark_completed(created.id)

    seen = await store.get(created.id)
    assert seen.phase == EnrichmentJobPhase.PENDING


@pytest.mark.asyncio
async def test_mark_executing_rejects_completed_job(
    db_session: AsyncSession,
) -> None:
    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration())
    await store.mark_executing(created.id)
    completed = await store.mark_completed(created.id)

    with pytest.raises(InvalidEnrichmentJobTransitionError):
        await store.mark_executing(created.id)

    seen = await store.get(created.id)
    assert seen == completed


@pytest.mark.asyncio
async def test_mark_failed_rejects_completed_job(
    db_session: AsyncSession,
) -> None:
    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration())
    await store.mark_executing(created.id)
    completed = await store.mark_completed(created.id)

    with pytest.raises(InvalidEnrichmentJobTransitionError):
        await store.mark_failed(
            created.id,
            error_code="ButlerError",
            error_message="metadata missing",
        )

    seen = await store.get(created.id)
    assert seen == completed


@pytest.mark.asyncio
async def test_mark_completed_does_not_overwrite_newer_error_phase(
    db_session: AsyncSession,
) -> None:
    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration())
    executing = await store.mark_executing(created.id)
    session_generator = db_session_dependency()
    other_session = await anext(session_generator)

    try:
        other_store = EnrichmentJobStore(other_session)
        failed = await other_store.mark_failed(
            executing.id,
            error_code="ButlerError",
            error_message="metadata missing",
        )

        with pytest.raises(InvalidEnrichmentJobTransitionError):
            await store.mark_completed(executing.id)

        seen = await store.get(executing.id)
        assert seen == failed
    finally:
        await session_generator.aclose()


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
async def test_get_unknown_instrument_visit_raises(
    db_session: AsyncSession,
) -> None:
    store = EnrichmentJobStore(db_session)

    with pytest.raises(
        UnknownEnrichmentJobVisitError,
        match="Unknown enrichment job for instrument 'LSSTCam' and visit 404",
    ) as exc_info:
        await store.get_by_instrument_visit("LSSTCam", 404)

    assert exc_info.value.instrument == "LSSTCam"
    assert exc_info.value.visit == 404
