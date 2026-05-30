"""Worker functions for visit enrichment jobs."""

import asyncio
from collections.abc import Mapping
from typing import Any

import structlog
from arq.worker import Retry
from safir.dependencies.db_session import db_session_dependency

from obsforge.services import EnrichmentJobService
from obsforge.storage import EnrichmentJobStore

__all__ = ["enrich_visit", "run_enrichment"]


async def enrich_visit(
    job_id: int, *, context: Mapping[str, Any] | None = None
) -> None:
    """Run the actual visit enrichment workflow.

    This hook is intentionally empty until the ObsCore enrichment orchestration
    is wired in.
    """


async def run_enrichment(ctx: dict[Any, Any], job_id: int) -> None:
    """Run one enrichment job from the arq worker."""
    logger = ctx.get("logger", structlog.get_logger("obsforge.worker"))
    logger = logger.bind(enrichment_job_id=job_id)
    session_generator = db_session_dependency()
    session = await anext(session_generator)
    service = EnrichmentJobService(EnrichmentJobStore(session))
    try:
        await service.mark_executing(job_id)
        await enrich_visit(job_id, context=ctx)
        await service.mark_completed(job_id)
    except Retry:
        raise
    except asyncio.CancelledError:
        await service.mark_failed(
            job_id,
            error_code="JobAborted",
            error_message="Enrichment job aborted",
        )
        raise
    except Exception as e:
        logger.exception("Enrichment job failed")
        await service.mark_failed(
            job_id,
            error_code=type(e).__name__,
            error_message=str(e),
        )
        raise
    finally:
        await session_generator.aclose()
