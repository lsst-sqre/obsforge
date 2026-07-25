"""Storage adapters for ObsForge."""

from .enrichment import EnrichmentJobStore
from .obscore import ObsCoreStore

__all__ = ["EnrichmentJobStore", "ObsCoreStore"]
