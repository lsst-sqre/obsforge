"""Business logic for Visit and VisitDetector records."""

from collections.abc import Sequence
from typing import Protocol

from obsforge.models import (
    SerializedVisit,
    SerializedVisitDetector,
    VisitDetectorUpsert,
    VisitUpsert,
)

__all__ = ["VisitDetectorService", "VisitService"]


class VisitStoreProtocol(Protocol):
    """Storage operations required by `VisitService`."""

    async def upsert(self, record: VisitUpsert) -> SerializedVisit: ...

    async def get_by_visit_id(self, visit_id: int) -> SerializedVisit: ...


class VisitService:
    """Apply Visit workflow rules around durable record state."""

    def __init__(self, store: VisitStoreProtocol) -> None:
        self._store = store

    async def upsert(self, record: VisitUpsert) -> SerializedVisit:
        """Insert or update one Visit record."""
        return await self._store.upsert(record)

    async def get_by_visit_id(self, visit_id: int) -> SerializedVisit:
        """Retrieve one Visit record by visit ID."""
        return await self._store.get_by_visit_id(visit_id)


class VisitDetectorStoreProtocol(Protocol):
    """Storage operations required by `VisitDetectorService`."""

    async def upsert(
        self, record: VisitDetectorUpsert
    ) -> SerializedVisitDetector: ...

    async def upsert_many(
        self, records: Sequence[VisitDetectorUpsert]
    ) -> list[SerializedVisitDetector]: ...

    async def get_by_detector_id(
        self, detector_id: int
    ) -> SerializedVisitDetector: ...

    async def get_by_visit_id(
        self, visit_id: int
    ) -> list[SerializedVisitDetector]: ...


class VisitDetectorService:
    """Apply VisitDetector workflow rules around durable record state."""

    def __init__(self, store: VisitDetectorStoreProtocol) -> None:
        self._store = store

    async def upsert(
        self, record: VisitDetectorUpsert
    ) -> SerializedVisitDetector:
        """Insert or update one VisitDetector record."""
        return await self._store.upsert(record)

    async def upsert_many(
        self, records: Sequence[VisitDetectorUpsert]
    ) -> list[SerializedVisitDetector]:
        """Insert or update multiple VisitDetector records."""
        return await self._store.upsert_many(records)

    async def get_by_detector_id(
        self, detector_id: int
    ) -> SerializedVisitDetector:
        """Retrieve one VisitDetector record by detector ID."""
        return await self._store.get_by_detector_id(detector_id)

    async def get_by_visit_id(
        self, visit_id: int
    ) -> list[SerializedVisitDetector]:
        """Retrieve all VisitDetector records for a visit."""
        return await self._store.get_by_visit_id(visit_id)
