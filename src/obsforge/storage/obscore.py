"""Storage layer for ObsCore records."""

from safir.database import retry_async_transaction
from sqlalchemy import delete, select
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
        """Insert or update one ObsCore record by visit ID."""
        values = record.model_dump(mode="json")
        insert_stmt = insert(SQLObsCore).values(values)
        update_values = {
            key: getattr(insert_stmt.excluded, key)
            for key in values
            if key != "visit_id"
        }
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=[SQLObsCore.visit_id],
            set_=update_values,
        ).returning(SQLObsCore)
        async with self._session.begin():
            obscore = (await self._session.execute(stmt)).scalar_one()
            return self._serialize(obscore)

    async def get_by_visit_id(self, visit_id: str) -> SerializedObsCore:
        """Retrieve an ObsCore record by visit ID."""
        async with self._session.begin():
            obscore = await self._get_by_visit_id(visit_id)
            return self._serialize(obscore)

    @retry_async_transaction
    async def delete_by_visit_id(self, visit_id: str) -> None:
        """Delete an ObsCore record by visit ID."""
        stmt = (
            delete(SQLObsCore)
            .where(SQLObsCore.visit_id == visit_id)
            .returning(SQLObsCore.visit_id)
        )
        async with self._session.begin():
            deleted_visit_id = (
                await self._session.execute(stmt)
            ).scalar_one_or_none()
            if deleted_visit_id is None:
                raise UnknownObsCoreRecordError(visit_id)

    async def _get_by_visit_id(self, visit_id: str) -> SQLObsCore:
        stmt = select(SQLObsCore).where(SQLObsCore.visit_id == visit_id)
        obscore = (await self._session.execute(stmt)).scalar_one_or_none()
        if not obscore:
            raise UnknownObsCoreRecordError(visit_id)
        return obscore

    def _serialize(self, obscore: SQLObsCore) -> SerializedObsCore:
        return SerializedObsCore(
            dataproduct_type=obscore.dataproduct_type,
            dataproduct_subtype=obscore.dataproduct_subtype,
            calib_level=obscore.calib_level,
            target_name=obscore.target_name,
            obs_id=obscore.obs_id,
            obs_collection=obscore.obs_collection,
            obs_publisher_did=obscore.obs_publisher_did,
            access_url=obscore.access_url,
            access_format=obscore.access_format,
            access_estsize=obscore.access_estsize,
            s_ra=obscore.s_ra,
            s_dec=obscore.s_dec,
            s_fov=obscore.s_fov,
            s_region=obscore.s_region,
            s_resolution=obscore.s_resolution,
            s_xel1=obscore.s_xel1,
            s_xel2=obscore.s_xel2,
            t_xel=obscore.t_xel,
            t_min=obscore.t_min,
            t_max=obscore.t_max,
            t_exptime=obscore.t_exptime,
            t_resolution=obscore.t_resolution,
            em_xel=obscore.em_xel,
            em_min=obscore.em_min,
            em_max=obscore.em_max,
            em_res_power=obscore.em_res_power,
            o_ucd=obscore.o_ucd,
            pol_xel=obscore.pol_xel,
            instrument_name=obscore.instrument_name,
            facility_name=obscore.facility_name,
            visit_id=obscore.visit_id,
            band=obscore.band,
            physical_filter=obscore.physical_filter,
        )
