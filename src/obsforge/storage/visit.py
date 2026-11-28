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
            "(instrument, visitId, detectorId) values"
        )


class VisitStore:
    """Stores and manipulates Visit records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @retry_async_transaction
    async def upsert(self, record: VisitUpsert) -> SerializedVisit:
        """Insert or update a Visit record for an instrument and visit ID."""
        async with self._session.begin():
            return await self.upsert_in_transaction(record)

    async def upsert_in_transaction(
        self, record: VisitUpsert
    ) -> SerializedVisit:
        """Upsert a Visit record within a transaction opened by the caller."""
        values = record.model_dump()
        insert_stmt = insert(SQLVisit).values(values)
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=[SQLVisit.instrument, SQLVisit.visitId],
            set_={
                key: getattr(insert_stmt.excluded, key)
                for key in values
                if key not in {"instrument", "visitId"}
            },
        ).returning(SQLVisit)
        visit: SQLVisit = (await self._session.execute(stmt)).scalar_one()
        return self._serialize(visit)

    async def get_by_visit_id(
        self, instrument: str, visit_id: int
    ) -> SerializedVisit:
        """Retrieve a Visit record for an instrument and visit ID."""
        stmt = select(SQLVisit).where(
            SQLVisit.instrument == instrument, SQLVisit.visitId == visit_id
        )
        async with self._session.begin():
            visit = (await self._session.execute(stmt)).scalar_one_or_none()
            if visit is None:
                raise UnknownVisitRecordError(instrument, visit_id)
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
        """Upsert a record by instrument, visit ID, and detector ID."""
        async with self._session.begin():
            detectors = await self.upsert_many_in_transaction([record])
            return detectors[0]

    @retry_async_transaction
    async def upsert_many(
        self, records: Sequence[VisitDetectorUpsert]
    ) -> list[SerializedVisitDetector]:
        """Insert or update detector records in one transaction."""
        if not records:
            return []
        async with self._session.begin():
            return await self.upsert_many_in_transaction(records)

    async def upsert_many_in_transaction(
        self, records: Sequence[VisitDetectorUpsert]
    ) -> list[SerializedVisitDetector]:
        """Upsert detector records using the caller's transaction."""
        records = list(records)
        if not records:
            return []
        self._validate_batch(records)

        stmt = self._upsert_statement(
            [record.model_dump() for record in records]
        )
        rows: Sequence[SQLVisitDetector] = (
            (await self._session.execute(stmt)).scalars().all()
        )

        rows_by_key = {
            (row.instrument, row.visitId, row.detectorId): self._serialize(row)
            for row in rows
        }
        return [
            rows_by_key[record.instrument, record.visitId, record.detectorId]
            for record in records
        ]

    async def get_by_visit_and_detector_id(
        self, instrument: str, visit_id: int, detector_id: int
    ) -> SerializedVisitDetector:
        """Retrieve a record by instrument, visit ID, and detector ID."""
        stmt = select(SQLVisitDetector).where(
            SQLVisitDetector.instrument == instrument,
            SQLVisitDetector.visitId == visit_id,
            SQLVisitDetector.detectorId == detector_id,
        )
        async with self._session.begin():
            row = (await self._session.execute(stmt)).scalar_one_or_none()
            if row is None:
                raise UnknownVisitDetectorRecordError(
                    instrument, visit_id, detector_id
                )
            return self._serialize(row)

    async def get_by_visit_id(
        self, instrument: str, visit_id: int
    ) -> list[SerializedVisitDetector]:
        """Retrieve all detector records for an instrument and visit."""
        stmt = (
            select(SQLVisitDetector)
            .where(
                SQLVisitDetector.instrument == instrument,
                SQLVisitDetector.visitId == visit_id,
            )
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
            if key not in {"instrument", "visitId", "detectorId"}
        }
        return insert_stmt.on_conflict_do_update(
            index_elements=[
                SQLVisitDetector.instrument,
                SQLVisitDetector.visitId,
                SQLVisitDetector.detectorId,
            ],
            set_=update_values,
        ).returning(SQLVisitDetector)

    def _validate_batch(self, records: Sequence[VisitDetectorUpsert]) -> None:
        keys = {
            (record.instrument, record.visitId, record.detectorId)
            for record in records
        }
        if len(keys) != len(records):
            raise DuplicateVisitDetectorBatchError
