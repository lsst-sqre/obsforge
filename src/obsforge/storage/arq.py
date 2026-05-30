"""Storage adapter for the arq enrichment queue."""

from safir.arq import ArqQueue, JobNotFound, JobResultUnavailable

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

    async def abort(self, arq_job_id: str) -> bool:
        """Abort an enrichment job in arq."""
        try:
            return await self._queue.abort_job(
                arq_job_id, queue_name=config.arq_queue_name, timeout=5
            )
        except TimeoutError:
            return False

    async def status(self, arq_job_id: str) -> str | None:
        """Return the arq job status, if the job is still known."""
        try:
            metadata = await self._queue.get_job_metadata(
                arq_job_id, queue_name=config.arq_queue_name
            )
        except JobNotFound:
            return None
        return metadata.status.value

    async def succeeded(self, arq_job_id: str) -> bool | None:
        """Return completion success, if a result is available."""
        try:
            result = await self._queue.get_job_result(
                arq_job_id, queue_name=config.arq_queue_name
            )
        except JobNotFound, JobResultUnavailable:
            return None
        return result.success
