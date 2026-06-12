"""Business logic for ObsCore records."""

from typing import Protocol

from obsforge.models import ObsCoreUpsert, SerializedObsCore

__all__ = ["ObsCoreService"]


class ObsCoreStoreProtocol(Protocol):
    """Storage operations required by `ObsCoreService`."""

    async def upsert(self, record: ObsCoreUpsert) -> SerializedObsCore: ...

    async def get_by_obs_id(self, obs_id: str) -> SerializedObsCore: ...


class ObsCoreService:
    """Apply ObsCore workflow rules around durable record state."""

    def __init__(self, store: ObsCoreStoreProtocol) -> None:
        self._store = store

    async def upsert(self, record: ObsCoreUpsert) -> SerializedObsCore:
        """Insert or update one ObsCore record."""
        return await self._store.upsert(record)

    async def get_by_obs_id(self, obs_id: str) -> SerializedObsCore:
        """Retrieve an ObsCore record by observation ID."""
        return await self._store.get_by_obs_id(obs_id)
