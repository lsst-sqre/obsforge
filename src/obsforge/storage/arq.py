"""Storage adapter for the arq enrichment queue."""

import structlog
from safir.arq import ArqQueue, JobNotFound, JobResultUnavailable
from structlog.stdlib import BoundLogger

from obsforge.config import config

__all__ = ["EnrichmentQueueStore"]


class EnrichmentQueueStore:
    """Translate enrichment queue operations to Safir arq calls."""

    task_name = "run_enrichment"

    def __init__(
        self, queue: ArqQueue, logger: BoundLogger | None = None
    ) -> None:
        self._queue = queue
        self._logger = logger or structlog.get_logger("obsforge")

    async def enqueue(self, job_id: int) -> str:
        """Enqueue an enrichment job and return the arq job ID."""
        logger = self._logger.bind(
            enrichment_job_id=job_id,
            arq_task_name=self.task_name,
            arq_queue_name=config.arq_queue_name,
        )
        logger.debug("Enqueueing enrichment job in arq")
        job = await self._queue.enqueue(
            self.task_name, job_id, _queue_name=config.arq_queue_name
        )
        logger.debug("Enqueued enrichment job in arq", arq_job_id=job.id)
        return job.id

    async def abort(self, arq_job_id: str) -> bool:
        """Abort an enrichment job in arq."""
        logger = self._logger.bind(
            arq_job_id=arq_job_id,
            arq_queue_name=config.arq_queue_name,
        )
        logger.debug("Aborting enrichment job in arq")
        try:
            aborted = await self._queue.abort_job(
                arq_job_id, queue_name=config.arq_queue_name, timeout=5
            )
        except TimeoutError:
            logger.debug("Timed out aborting enrichment job in arq")
            return False
        else:
            logger.debug("Aborted enrichment job in arq", arq_aborted=aborted)
            return aborted

    async def status(self, arq_job_id: str) -> str | None:
        """Return the arq job status, if the job is still known."""
        logger = self._logger.bind(
            arq_job_id=arq_job_id,
            arq_queue_name=config.arq_queue_name,
        )
        logger.debug("Checking enrichment job arq status")
        try:
            metadata = await self._queue.get_job_metadata(
                arq_job_id, queue_name=config.arq_queue_name
            )
        except JobNotFound:
            logger.debug("Enrichment job not found in arq")
            return None
        logger.debug(
            "Checked enrichment job arq status",
            arq_status=metadata.status.value,
        )
        return metadata.status.value

    async def succeeded(self, arq_job_id: str) -> bool | None:
        """Return completion success, if a result is available."""
        logger = self._logger.bind(
            arq_job_id=arq_job_id,
            arq_queue_name=config.arq_queue_name,
        )
        logger.debug("Checking enrichment job arq result")
        try:
            result = await self._queue.get_job_result(
                arq_job_id, queue_name=config.arq_queue_name
            )
        except JobNotFound, JobResultUnavailable:
            logger.debug("Enrichment job result unavailable in arq")
            return None
        logger.debug(
            "Checked enrichment job arq result", arq_success=result.success
        )
        return result.success
