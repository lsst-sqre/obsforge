"""Storage layer for ObsCore records."""

from safir.database import retry_async_transaction
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge.exceptions import UnknownObsCoreRecordError
from obsforge.models import ObsCoreUpsert, SerializedObsCore
from obsforge.schema import ObsCore as SQLObsCore

__all__ = ["ObsCoreStore"]


class ObsCoreStore:
    """Stores and manipulates ObsCore records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @retry_async_transaction
    async def upsert(self, record: ObsCoreUpsert) -> SerializedObsCore:
        """Insert or update one ObsCore record by observation ID."""
        values = record.model_dump(mode="json")
        insert_stmt = insert(SQLObsCore).values(values)
        update_values = {
            key: getattr(insert_stmt.excluded, key)
            for key in values
            if key != "obs_id"
        }
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=[SQLObsCore.obs_id],
            set_=update_values,
        ).returning(SQLObsCore)
        async with self._session.begin():
            obscore = (await self._session.execute(stmt)).scalar_one()
            return self._serialize(obscore)

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
        return SerializedObsCore(
            **{
                column.name: getattr(obscore, column.name)
                for column in SQLObsCore.__table__.columns
            }
        )
