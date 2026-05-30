"""Storage adapter for the arq enrichment queue."""

from safir.arq import ArqQueue

from obsforge.config import config

__all__ = ["EnrichmentQueueStore"]


class EnrichmentQueueStore:
    """Translate enrichment queue operations to Safir arq calls."""

    task_name = "run_enrichment"

    def __init__(self, queue: ArqQueue) -> None:
        self._queue = queue

    async def enqueue(self, job_id: int) -> str:
        """Enqueue an enrichment job and return the arq job ID."""
        job = await self._queue.enqueue(
            self.task_name, job_id, _queue_name=config.arq_queue_name
        )
        return job.id
