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
    INSTRUMENT,
    SECOND_DETECTOR_ID,
    SECOND_INSTRUMENT,
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
    assert (
        await store.get_by_visit_id(created.instrument, created.visitId)
        == updated
    )


@pytest.mark.asyncio
async def test_unknown_visit_raises(db_session: AsyncSession) -> None:
    with pytest.raises(UnknownVisitRecordError):
        await VisitStore(db_session).get_by_visit_id(INSTRUMENT, 123)


@pytest.mark.asyncio
async def test_detector_upsert_many_and_reads(
    db_session: AsyncSession,
) -> None:
    await VisitStore(db_session).upsert(make_visit_upsert())
    store = VisitDetectorStore(db_session)
    first = make_visit_detector_upsert()
    second = make_visit_detector_upsert(
        detectorId=SECOND_DETECTOR_ID,
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

    updated = await store.upsert(
        first.model_copy(
            update={"detector": SECOND_DETECTOR_ID + 1, "seeing": 1.9}
        )
    )
    assert updated.seeing == pytest.approx(1.9)
    assert updated.detector == SECOND_DETECTOR_ID + 1
    fetched = await store.get_by_visit_and_detector_id(
        first.instrument, first.visitId, first.detectorId
    )
    assert_records_match(fetched, updated)
    by_visit = await store.get_by_visit_id(first.instrument, first.visitId)
    assert [record.detectorId for record in by_visit] == [
        first.detectorId,
        second.detectorId,
    ]


@pytest.mark.asyncio
async def test_detector_batch_keeps_shared_detector_in_both_visits(
    db_session: AsyncSession,
) -> None:
    visits = VisitStore(db_session)
    second_visit_id = VISIT_ID + 1
    await visits.upsert(make_visit_upsert())
    await visits.upsert(
        make_visit_upsert(visitId=second_visit_id, visit=second_visit_id)
    )
    first = make_visit_detector_upsert(seeing=1.8)
    second = make_visit_detector_upsert(
        visitId=second_visit_id, ccdVisitId=CCD_VISIT_ID + 1, seeing=2.0
    )
    store = VisitDetectorStore(db_session)

    created = await store.upsert_many([second, first])
    assert_records_match(created[0], second)
    assert_records_match(created[1], first)

    updated = first.model_copy(update={"seeing": 1.9})
    await store.upsert_many([updated])
    first_row = await store.get_by_visit_and_detector_id(
        first.instrument, first.visitId, first.detectorId
    )
    second_row = await store.get_by_visit_and_detector_id(
        second.instrument, second.visitId, second.detectorId
    )
    assert_records_match(first_row, updated)
    assert_records_match(second_row, second)


@pytest.mark.asyncio
async def test_same_visit_and_detector_ids_across_instruments(
    db_session: AsyncSession,
) -> None:
    visits = VisitStore(db_session)
    first_visit = make_visit_upsert(skyRotation=200.0)
    second_visit = make_visit_upsert(
        instrument=SECOND_INSTRUMENT, skyRotation=201.0
    )
    await visits.upsert(first_visit)
    await visits.upsert(second_visit)

    detectors = VisitDetectorStore(db_session)
    first = make_visit_detector_upsert(seeing=1.8)
    second = make_visit_detector_upsert(
        instrument=SECOND_INSTRUMENT, seeing=2.0
    )
    created = await detectors.upsert_many([second, first])
    assert_records_match(created[0], second)
    assert_records_match(created[1], first)
    updated = first.model_copy(update={"seeing": 1.9})
    await detectors.upsert_many([updated])

    assert_records_match(
        await visits.get_by_visit_id(INSTRUMENT, VISIT_ID), first_visit
    )
    assert_records_match(
        await visits.get_by_visit_id(SECOND_INSTRUMENT, VISIT_ID), second_visit
    )
    assert_records_match(
        await detectors.get_by_visit_and_detector_id(
            INSTRUMENT, VISIT_ID, DETECTOR_ID
        ),
        updated,
    )
    assert_records_match(
        await detectors.get_by_visit_and_detector_id(
            SECOND_INSTRUMENT, VISIT_ID, DETECTOR_ID
        ),
        second,
    )


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
            [
                first,
                first.model_copy(update={"detector": SECOND_DETECTOR_ID}),
            ]
        )
    assert await store.get_by_visit_id(first.instrument, first.visitId) == []


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
        await store.get_by_visit_and_detector_id(
            valid.instrument, valid.visitId, valid.detectorId
        )


@pytest.mark.asyncio
async def test_detector_requires_visit_for_same_instrument(
    db_session: AsyncSession,
) -> None:
    store = VisitDetectorStore(db_session)
    await VisitStore(db_session).upsert(
        make_visit_upsert(instrument=SECOND_INSTRUMENT)
    )
    with pytest.raises(IntegrityError):
        await store.upsert(make_visit_detector_upsert())

    with pytest.raises(UnknownVisitDetectorRecordError):
        await store.get_by_visit_and_detector_id(
            INSTRUMENT, VISIT_ID, DETECTOR_ID
        )


@pytest.mark.asyncio
async def test_unknown_detector_and_empty_visit_reads(
    db_session: AsyncSession,
) -> None:
    store = VisitDetectorStore(db_session)
    with pytest.raises(UnknownVisitDetectorRecordError):
        await store.get_by_visit_and_detector_id(INSTRUMENT, 123, DETECTOR_ID)
    assert await store.get_by_visit_id(INSTRUMENT, 123) == []


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
