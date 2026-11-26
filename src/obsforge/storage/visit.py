"""Storage layers for Visit and VisitDetector records."""

from collections.abc import Sequence
from typing import Any

from safir.database import retry_async_transaction
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge.exceptions import (
    UnknownVisitDetectorRecordError,
    UnknownVisitRecordError,
)
from obsforge.models import (
    SerializedVisit,
    SerializedVisitDetector,
    VisitDetectorUpsert,
    VisitUpsert,
)
from obsforge.schema import Visit as SQLVisit
from obsforge.schema import VisitDetector as SQLVisitDetector

__all__ = [
    "DuplicateVisitDetectorBatchError",
    "VisitDetectorStore",
    "VisitStore",
]


class DuplicateVisitDetectorBatchError(ValueError):
    """Raised when a detector batch contains duplicate identities."""

    def __init__(self) -> None:
        super().__init__(
            "VisitDetector batch contains duplicate "
            "(visitId, detectorId) values"
        )


class VisitStore:
    """Stores and manipulates Visit records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @retry_async_transaction
    async def upsert(self, record: VisitUpsert) -> SerializedVisit:
        """Insert or update one Visit record by visit ID."""
        values = record.model_dump()
        insert_stmt = insert(SQLVisit).values(values)
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=[SQLVisit.visitId],
            set_={
                key: getattr(insert_stmt.excluded, key)
                for key in values
                if key != "visitId"
            },
        ).returning(SQLVisit)
        async with self._session.begin():
            visit: SQLVisit = (await self._session.execute(stmt)).scalar_one()
            return self._serialize(visit)

    async def get_by_visit_id(self, visit_id: int) -> SerializedVisit:
        """Retrieve a Visit record by visit ID."""
        stmt = select(SQLVisit).where(SQLVisit.visitId == visit_id)
        async with self._session.begin():
            visit = (await self._session.execute(stmt)).scalar_one_or_none()
            if visit is None:
                raise UnknownVisitRecordError(visit_id)
            return self._serialize(visit)

    def _serialize(self, visit: SQLVisit) -> SerializedVisit:
        return SerializedVisit.model_validate(visit, from_attributes=True)


class VisitDetectorStore:
    """Stores and manipulates VisitDetector records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @retry_async_transaction
    async def upsert(
        self, record: VisitDetectorUpsert
    ) -> SerializedVisitDetector:
        """Insert or update a record by visit ID and detector ID."""
        stmt = self._upsert_statement([record.model_dump()])
        async with self._session.begin():
            detector: SQLVisitDetector = (
                await self._session.execute(stmt)
            ).scalar_one()
            return self._serialize(detector)

    @retry_async_transaction
    async def upsert_many(
        self, records: Sequence[VisitDetectorUpsert]
    ) -> list[SerializedVisitDetector]:
        """Insert or update detector records in one transaction."""
        records = list(records)
        if not records:
            return []
        self._validate_batch(records)

        stmt = self._upsert_statement(
            [record.model_dump() for record in records]
        )
        async with self._session.begin():
            rows: Sequence[SQLVisitDetector] = (
                (await self._session.execute(stmt)).scalars().all()
            )

            rows_by_key = {
                (row.visitId, row.detectorId): self._serialize(row)
                for row in rows
            }
        return [
            rows_by_key[record.visitId, record.detectorId]
            for record in records
        ]

    async def get_by_visit_and_detector_id(
        self, visit_id: int, detector_id: int
    ) -> SerializedVisitDetector:
        """Retrieve a VisitDetector record by visit ID and detector ID."""
        stmt = select(SQLVisitDetector).where(
            SQLVisitDetector.visitId == visit_id,
            SQLVisitDetector.detectorId == detector_id,
        )
        async with self._session.begin():
            row = (await self._session.execute(stmt)).scalar_one_or_none()
            if row is None:
                raise UnknownVisitDetectorRecordError(visit_id, detector_id)
            return self._serialize(row)

    async def get_by_visit_id(
        self, visit_id: int
    ) -> list[SerializedVisitDetector]:
        """Retrieve all detector records for a visit."""
        stmt = (
            select(SQLVisitDetector)
            .where(SQLVisitDetector.visitId == visit_id)
            .order_by(SQLVisitDetector.detectorId)
        )
        async with self._session.begin():
            detectors = (await self._session.execute(stmt)).scalars().all()
            return [self._serialize(detector) for detector in detectors]

    def _serialize(
        self, detector: SQLVisitDetector
    ) -> SerializedVisitDetector:
        return SerializedVisitDetector.model_validate(
            detector, from_attributes=True
        )

    def _upsert_statement(self, values: list[dict[str, object]]) -> Any:
        insert_stmt = insert(SQLVisitDetector).values(values)
        update_values = {
            key: getattr(insert_stmt.excluded, key)
            for key in values[0]
            if key not in {"visitId", "detectorId"}
        }
        return insert_stmt.on_conflict_do_update(
            index_elements=[
                SQLVisitDetector.visitId,
                SQLVisitDetector.detectorId,
            ],
            set_=update_values,
        ).returning(SQLVisitDetector)

    def _validate_batch(self, records: Sequence[VisitDetectorUpsert]) -> None:
        keys = {(record.visitId, record.detectorId) for record in records}
        if len(keys) != len(records):
            raise DuplicateVisitDetectorBatchError
