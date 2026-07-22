"""Configuration for the ObsForge arq worker."""

import uuid
from pathlib import Path
from typing import Any, ClassVar

import structlog
from lsst.daf.butler import ButlerConfig, LabeledButlerFactory
from lsst.dax.obscore import ExporterConfig
from pydantic import HttpUrl
from safir.dependencies.db_session import db_session_dependency
from safir.logging import configure_logging
from structlog.stdlib import BoundLogger

from obsforge.config import config
from obsforge.worker.functions import run_enrichment

__all__ = ["WorkerSettings", "shutdown", "startup"]


def _required_worker_setting(value: HttpUrl | Path | None, name: str) -> str:
    if value is None:
        raise RuntimeError(f"{name} must be set for worker enrichment")
    return str(value)


def _initialize_obscore_context(
    ctx: dict[Any, Any], logger: BoundLogger
) -> None:
    butler_repository_setting = config.butler_repository
    if butler_repository_setting is None:
        raise RuntimeError(
            "OBSFORGE_BUTLER_REPOSITORY must be set for worker enrichment"
        )
    if config.butler_access_token is None:
        raise RuntimeError(
            "OBSFORGE_BUTLER_ACCESS_TOKEN must be set for Butler enrichment"
        )
    butler_repository = _required_worker_setting(
        butler_repository_setting, "OBSFORGE_BUTLER_REPOSITORY"
    )
    obscore_config = _required_worker_setting(
        config.obscore_config, "OBSFORGE_OBSCORE_CONFIG"
    )
    ctx["labeled_butler_factory"] = LabeledButlerFactory(
        repositories={config.butler_label: butler_repository}
    )
    ctx["obscore_config"] = ExporterConfig.model_validate(
        ButlerConfig(obscore_config)
    )
    ctx["obscore_dataset_type"] = config.obscore_dataset_type
    ctx["butler_access_token"] = config.butler_access_token
    logger.info(
        "Initialized ObsCore enrichment resources",
        butler_label=config.butler_label,
        obscore_dataset_type=config.obscore_dataset_type,
    )


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
    _initialize_obscore_context(ctx, logger)
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
    ctx.pop("labeled_butler_factory", None)
    ctx.pop("obscore_config", None)
    ctx.pop("obscore_dataset_type", None)
    ctx.pop("butler_access_token", None)
    await db_session_dependency.aclose()
    logger.info("Worker shutdown complete")


class WorkerSettings:
    """Configuration for the arq worker."""

    functions: ClassVar = [run_enrichment]
    redis_settings: ClassVar = config.arq_redis_settings
    queue_name: ClassVar = config.arq_queue_name
    max_tries: ClassVar = config.enrichment_max_tries
    on_startup: ClassVar = startup
    on_shutdown: ClassVar = shutdown
    allow_abort_jobs: ClassVar = True
