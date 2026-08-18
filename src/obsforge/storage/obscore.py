"""Storage layer for ObsCore records."""

from collections.abc import Sequence
from typing import Any

from safir.database import retry_async_transaction
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge.exceptions import UnknownObsCoreRecordError
from obsforge.models import ObsCoreUpsert, SerializedObsCore
from obsforge.schema import ObsCore as SQLObsCore

__all__ = ["DuplicateObsCoreBatchError", "ObsCoreStore"]


class DuplicateObsCoreBatchError(ValueError):
    """Raised when an ObsCore batch contains duplicate observation IDs."""

    def __init__(self) -> None:
        super().__init__("ObsCore batch contains duplicate obs_id values")


class ObsCoreStore:
    """Stores and manipulates ObsCore records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @retry_async_transaction
    async def upsert(self, record: ObsCoreUpsert) -> SerializedObsCore:
        """Insert or update one ObsCore record by observation ID."""
        stmt = self._upsert_statement([record.model_dump()])
        async with self._session.begin():
            obscore = (await self._session.execute(stmt)).scalar_one()
            return self._serialize(obscore)

    @retry_async_transaction
    async def upsert_many(
        self, records: Sequence[ObsCoreUpsert]
    ) -> list[SerializedObsCore]:
        """Insert or update multiple ObsCore records in one transaction."""
        records = list(records)
        if not records:
            return []

        obs_ids = [record.obs_id for record in records]
        if len(set(obs_ids)) != len(obs_ids):
            raise DuplicateObsCoreBatchError

        stmt = self._upsert_statement(
            [record.model_dump() for record in records]
        )
        async with self._session.begin():
            rows = (await self._session.execute(stmt)).scalars().all()

        rows_by_obs_id = {row.obs_id: self._serialize(row) for row in rows}
        return [rows_by_obs_id[obs_id] for obs_id in obs_ids]

    async def get_by_obs_id(self, obs_id: str) -> SerializedObsCore:
        """Retrieve an ObsCore record by observation ID."""
        async with self._session.begin():
            obscore = await self._get_by_obs_id(obs_id)
            return self._serialize(obscore)

    async def _get_by_obs_id(self, obs_id: str) -> SQLObsCore:
        stmt = select(SQLObsCore).where(SQLObsCore.obs_id == obs_id)
        obscore = (await self._session.execute(stmt)).scalar_one_or_none()
        if not obscore:
            raise UnknownObsCoreRecordError(obs_id)
        return obscore

    def _serialize(self, obscore: SQLObsCore) -> SerializedObsCore:
        return SerializedObsCore.model_validate(obscore, from_attributes=True)

    def _upsert_statement(self, values: list[dict[str, object]]) -> Any:
        insert_stmt = insert(SQLObsCore).values(values)
        update_values = {
            key: getattr(insert_stmt.excluded, key)
            for key in values[0]
            if key != "obs_id"
        }
        return insert_stmt.on_conflict_do_update(
            index_elements=[SQLObsCore.obs_id],
            set_=update_values,
        ).returning(SQLObsCore)
