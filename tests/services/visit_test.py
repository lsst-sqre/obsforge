"""Tests for Visit and VisitDetector business logic."""

from collections.abc import Sequence

import pytest

from obsforge.models import (
    SerializedVisit,
    SerializedVisitDetector,
    VisitDetectorUpsert,
    VisitUpsert,
)
from obsforge.services import VisitDetectorService, VisitService
from tests.support.visit import (
    CCD_VISIT_ID,
    SECOND_DETECTOR_ID,
    make_visit_detector_upsert,
    make_visit_upsert,
)


class FakeVisitStore:
    """In-memory Visit store test double."""

    def __init__(self) -> None:
        self.records: dict[int, SerializedVisit] = {}

    async def upsert(self, record: VisitUpsert) -> SerializedVisit:
        serialized = SerializedVisit.model_validate(record.model_dump())
        self.records[record.visitId] = serialized
        return serialized

    async def get_by_visit_id(self, visit_id: int) -> SerializedVisit:
        return self.records[visit_id]


class FakeVisitDetectorStore:
    """In-memory VisitDetector store test double."""

    def __init__(self) -> None:
        self.records: dict[tuple[int, int], SerializedVisitDetector] = {}

    async def upsert(
        self, record: VisitDetectorUpsert
    ) -> SerializedVisitDetector:
        serialized = SerializedVisitDetector.model_validate(
            record.model_dump()
        )
        self.records[record.visitId, record.detectorId] = serialized
        return serialized

    async def upsert_many(
        self, records: Sequence[VisitDetectorUpsert]
    ) -> list[SerializedVisitDetector]:
        return [await self.upsert(record) for record in records]

    async def get_by_visit_and_detector_id(
        self, visit_id: int, detector_id: int
    ) -> SerializedVisitDetector:
        return self.records[visit_id, detector_id]

    async def get_by_visit_id(
        self, visit_id: int
    ) -> list[SerializedVisitDetector]:
        return [
            record
            for record in self.records.values()
            if record.visitId == visit_id
        ]


@pytest.mark.asyncio
async def test_visit_service_delegates() -> None:
    store = FakeVisitStore()
    service = VisitService(store)
    record = make_visit_upsert()

    created = await service.upsert(record)
    assert created == SerializedVisit.model_validate(record.model_dump())
    assert await service.get_by_visit_id(record.visitId) == created


@pytest.mark.asyncio
async def test_visit_detector_service_delegates() -> None:
    store = FakeVisitDetectorStore()
    service = VisitDetectorService(store)
    first = make_visit_detector_upsert()
    second = make_visit_detector_upsert(
        detectorId=SECOND_DETECTOR_ID,
        ccdVisitId=CCD_VISIT_ID + 1,
    )

    created = await service.upsert_many([first, second])
    assert [record.detectorId for record in created] == [
        first.detectorId,
        second.detectorId,
    ]
    fetched = await service.get_by_visit_and_detector_id(
        second.visitId, second.detectorId
    )
    assert fetched == created[1]
    assert await service.get_by_visit_id(first.visitId) == created

    updated = await service.upsert(first.model_copy(update={"seeing": 1.9}))
    assert updated.seeing == pytest.approx(1.9)
