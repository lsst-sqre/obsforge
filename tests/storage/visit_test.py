"""Tests for Visit and VisitDetector storage."""

import math

import pytest
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge.exceptions import (
    UnknownVisitDetectorRecordError,
    UnknownVisitRecordError,
)
from obsforge.storage import (
    DuplicateVisitDetectorBatchError,
    VisitDetectorStore,
    VisitStore,
)
from tests.support.visit import (
    CCD_VISIT_ID,
    DETECTOR_ID,
    SECOND_DETECTOR_ID,
    VISIT_ID,
    make_visit_detector_upsert,
    make_visit_upsert,
)


def assert_records_match(actual: BaseModel, expected: BaseModel) -> None:
    """Assert records match while handling database floats and NaN."""
    for name, expected_value in expected.model_dump().items():
        actual_value = getattr(actual, name)
        if isinstance(expected_value, float):
            if math.isnan(expected_value):
                assert math.isnan(actual_value), name
            else:
                assert actual_value == pytest.approx(expected_value), name
        else:
            assert actual_value == expected_value, name


@pytest.mark.asyncio
async def test_visit_upsert_and_get(db_session: AsyncSession) -> None:
    store = VisitStore(db_session)
    record = make_visit_upsert()
    created = await store.upsert(record)
    updated_record = make_visit_upsert(skyRotation=204.0)
    updated = await store.upsert(updated_record)

    assert_records_match(created, record)
    assert created.visitId == VISIT_ID
    assert updated.visitId == created.visitId
    assert updated.skyRotation == pytest.approx(204.0)
    assert_records_match(updated, updated_record)
    assert await store.get_by_visit_id(created.visitId) == updated


@pytest.mark.asyncio
async def test_unknown_visit_raises(db_session: AsyncSession) -> None:
    with pytest.raises(UnknownVisitRecordError):
        await VisitStore(db_session).get_by_visit_id(123)


@pytest.mark.asyncio
async def test_detector_upsert_many_and_reads(
    db_session: AsyncSession,
) -> None:
    await VisitStore(db_session).upsert(make_visit_upsert())
    store = VisitDetectorStore(db_session)
    first = make_visit_detector_upsert()
    second = make_visit_detector_upsert(
        detectorId=SECOND_DETECTOR_ID,
        detector=SECOND_DETECTOR_ID,
        ccdVisitId=CCD_VISIT_ID + 1,
        ra=60.2,
    )

    created = await store.upsert_many([second, first])
    assert [record.detectorId for record in created] == [
        second.detectorId,
        first.detectorId,
    ]
    assert_records_match(created[0], second)
    assert_records_match(created[1], first)

    updated = await store.upsert(first.model_copy(update={"seeing": 1.9}))
    assert updated.seeing == pytest.approx(1.9)
    fetched = await store.get_by_detector_id(first.detectorId)
    assert_records_match(fetched, updated)
    by_visit = await store.get_by_visit_id(first.visitId)
    assert [record.detectorId for record in by_visit] == [
        first.detectorId,
        second.detectorId,
    ]


@pytest.mark.asyncio
async def test_detector_upsert_many_empty(db_session: AsyncSession) -> None:
    assert await VisitDetectorStore(db_session).upsert_many([]) == []


@pytest.mark.asyncio
async def test_detector_batch_rejects_duplicate_identities(
    db_session: AsyncSession,
) -> None:
    await VisitStore(db_session).upsert(make_visit_upsert())
    store = VisitDetectorStore(db_session)
    first = make_visit_detector_upsert()

    with pytest.raises(DuplicateVisitDetectorBatchError):
        await store.upsert_many(
            [first, first.model_copy(update={"detector": 2})]
        )

    with pytest.raises(DuplicateVisitDetectorBatchError):
        await store.upsert_many(
            [
                first,
                first.model_copy(update={"detectorId": first.detectorId + 1}),
            ]
        )
    assert await store.get_by_visit_id(first.visitId) == []


@pytest.mark.asyncio
async def test_detector_batch_rolls_back_on_database_error(
    db_session: AsyncSession,
) -> None:
    await VisitStore(db_session).upsert(make_visit_upsert())
    store = VisitDetectorStore(db_session)
    valid = make_visit_detector_upsert()
    invalid = make_visit_detector_upsert(
        detectorId=valid.detectorId + 1,
        detector=2,
        visitId=valid.visitId + 1,
    )

    with pytest.raises(IntegrityError):
        await store.upsert_many([valid, invalid])

    with pytest.raises(UnknownVisitDetectorRecordError):
        await store.get_by_detector_id(valid.detectorId)


@pytest.mark.asyncio
async def test_detector_foreign_key_is_enforced(
    db_session: AsyncSession,
) -> None:
    store = VisitDetectorStore(db_session)
    with pytest.raises(IntegrityError):
        await store.upsert(make_visit_detector_upsert())

    with pytest.raises(UnknownVisitDetectorRecordError):
        await store.get_by_detector_id(DETECTOR_ID)


@pytest.mark.asyncio
async def test_unknown_detector_and_empty_visit_reads(
    db_session: AsyncSession,
) -> None:
    store = VisitDetectorStore(db_session)
    with pytest.raises(UnknownVisitDetectorRecordError):
        await store.get_by_detector_id(123)
    assert await store.get_by_visit_id(123) == []


@pytest.mark.asyncio
async def test_nullable_visit_and_detector_fields_round_trip(
    db_session: AsyncSession,
) -> None:
    visit = make_visit_upsert(
        physical_filter=None,
        band=None,
        expMidpt=None,
        obsStart=None,
    )
    created_visit = await VisitStore(db_session).upsert(visit)
    detector = make_visit_detector_upsert(
        physical_filter=None,
        band=None,
        pixelScale=None,
        expMidpt=None,
        obsStart=None,
    )
    created_detector = await VisitDetectorStore(db_session).upsert(detector)

    assert created_visit.physical_filter is None
    assert created_visit.expMidpt is None
    assert created_detector.pixelScale is None
    assert created_detector.obsStart is None
