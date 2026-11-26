"""Storage for the outputs of one visit enrichment."""

from collections.abc import Sequence

from safir.database import retry_async_transaction
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge.models import ObsCoreUpsert, VisitDetectorUpsert, VisitUpsert

from .obscore import ObsCoreStore
from .visit import VisitDetectorStore, VisitStore

__all__ = ["EnrichmentOutputStore"]


class EnrichmentOutputStore:
    """Write all outputs of a visit enrichment as one transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._visits = VisitStore(session)
        self._detectors = VisitDetectorStore(session)
        self._obscore = ObsCoreStore(session)

    @retry_async_transaction
    async def write(
        self,
        visit: VisitUpsert,
        detectors: Sequence[VisitDetectorUpsert],
        obscore: Sequence[ObsCoreUpsert],
    ) -> None:
        """Upsert the visit, its detectors, and its ObsCore records."""
        async with self._session.begin():
            await self._visits.upsert_in_transaction(visit)
            await self._detectors.upsert_many_in_transaction(detectors)
            await self._obscore.upsert_many_in_transaction(obscore)
