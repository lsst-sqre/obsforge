"""Configuration for the ObsForge arq worker."""

import uuid
from typing import Any, ClassVar

import structlog
from safir.dependencies.db_session import db_session_dependency
from safir.logging import configure_logging

from obsforge.config import config
from obsforge.worker.functions import run_enrichment

__all__ = ["WorkerSettings", "shutdown", "startup"]


async def startup(ctx: dict[Any, Any]) -> None:
    """Set up shared worker resources."""
    configure_logging(
        profile=config.log_profile,
        log_level=config.log_level,
        name="obsforge",
    )
    logger = structlog.get_logger("obsforge.worker").bind(
        worker_instance=uuid.uuid4().hex
    )
    ctx["logger"] = logger
    await db_session_dependency.initialize(
        config.database_url,
        config.database_password,
        isolation_level="REPEATABLE READ",
    )
    logger.info("Worker start up complete")


async def shutdown(ctx: dict[Any, Any]) -> None:
    """Clean up shared worker resources."""
    logger = ctx.get("logger", structlog.get_logger("obsforge.worker"))
    logger.info("Running worker shutdown")
    await db_session_dependency.aclose()
    logger.info("Worker shutdown complete")


class WorkerSettings:
    """Configuration for the arq worker."""

    functions: ClassVar = [run_enrichment]
    redis_settings: ClassVar = config.arq_redis_settings
    queue_name: ClassVar = config.arq_queue_name
    on_startup: ClassVar = startup
    on_shutdown: ClassVar = shutdown
    allow_abort_jobs: ClassVar = True
