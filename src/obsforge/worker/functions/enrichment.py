"""Worker functions for visit enrichment jobs."""

import asyncio
from collections.abc import Mapping
from typing import Any, cast

import structlog
from arq.worker import Retry
from lsst.daf.butler import LabeledButlerFactory
from lsst.dax.obscore import ExporterConfig
from pydantic import SecretStr
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge.adapters import (
    ButlerAdapter,
    ButlerVisitRecords,
    DaxObsCoreAdapter,
)
from obsforge.config import config
from obsforge.models import ObsCoreUpsert, VisitRegistration
from obsforge.services import (
    EnrichmentJobService,
    ObsCoreService,
    VisitDetectorService,
    VisitService,
)
from obsforge.storage import (
    EnrichmentJobStore,
    ObsCoreStore,
    VisitDetectorStore,
    VisitStore,
)

__all__ = [
    "EnrichmentRetriesExhaustedError",
    "MissingWorkerContextError",
    "enrich_visit",
    "run_enrichment",
]


class EnrichmentRetriesExhaustedError(RuntimeError):
    """Raised when an enrichment job exhausts all arq attempts."""

    def __init__(self) -> None:
        super().__init__("Enrichment retries exhausted")


class MissingWorkerContextError(RuntimeError):
    """Raised when required worker context is missing."""

    def __init__(self, key: str | None = None) -> None:
        self.key = key
        if key:
            msg = f"Worker context missing {key!r}"
        else:
            msg = "Worker context is required for visit enrichment"
        super().__init__(msg)


def _required_context_value(
    context: Mapping[str, Any] | None, key: str
) -> Any:
    if context is None:
        raise MissingWorkerContextError
    value = context.get(key)
    if value is None:
        raise MissingWorkerContextError(key)
    return value


async def enrich_visit(
    job_id: int,
    *,
    session: AsyncSession,
    context: Mapping[str, Any] | None = None,
) -> None:
    """Run the actual visit enrichment workflow.

    Retrieve ObsCore, Visit, and VisitDetector records for the registered
    visit and upsert them into ObsDB.
    """
    job = await EnrichmentJobStore(session).get(job_id)
    registration = VisitRegistration.model_validate(job.registration_payload)
    butler_access_token = cast(
        "SecretStr", _required_context_value(context, "butler_access_token")
    )
    butler_factory = cast(
        "LabeledButlerFactory",
        _required_context_value(context, "labeled_butler_factory"),
    )
    access_token = butler_access_token.get_secret_value()
    obscore_adapter = DaxObsCoreAdapter(
        butler_factory=butler_factory,
        butler_label=config.butler_label,
        config=cast(
            "ExporterConfig",
            _required_context_value(context, "obscore_config"),
        ),
        dataset_type=cast(
            "str",
            _required_context_value(context, "obscore_dataset_type"),
        ),
        access_token=access_token,
    )
    butler_adapter = ButlerAdapter(
        butler_factory=butler_factory,
        butler_label=config.butler_label,
        access_token=access_token,
    )

    def fetch_records() -> tuple[list[ObsCoreUpsert], ButlerVisitRecords]:
        obscore_records = list(
            obscore_adapter.iter_visit_records(registration)
        )
        visit_records = butler_adapter.fetch_visit_records(registration)
        return obscore_records, visit_records

    records, visit_records = await asyncio.to_thread(fetch_records)

    visit_service = VisitService(VisitStore(session))
    await visit_service.upsert(visit_records.visit)
    detector_service = VisitDetectorService(VisitDetectorStore(session))
    await detector_service.upsert_many(visit_records.detectors)
    obscore_service = ObsCoreService(ObsCoreStore(session))
    await obscore_service.upsert_many(records)


async def run_enrichment(ctx: dict[Any, Any], job_id: int) -> None:
    """Run one enrichment job from the arq worker."""
    job_try = int(ctx.get("job_try", 1))
    logger = ctx.get("logger", structlog.get_logger("obsforge.worker"))
    logger = logger.bind(
        enrichment_job_id=job_id,
        job_try=job_try,
        max_tries=config.enrichment_max_tries,
    )
    session_generator = db_session_dependency()
    session = await anext(session_generator)
    service = EnrichmentJobService(EnrichmentJobStore(session), logger=logger)
    try:
        await service.mark_executing(job_id)
        await enrich_visit(job_id, session=session, context=ctx)
        await service.mark_completed(job_id)
    except Retry as e:
        if job_try < config.enrichment_max_tries:
            logger.debug("Retrying enrichment job")
            raise
        logger.warning("Enrichment retries exhausted")
        await service.mark_failed(
            job_id,
            error_code="RetriesExhausted",
            error_message=(
                "Enrichment job exhausted "
                f"{config.enrichment_max_tries} arq attempts"
            ),
        )
        raise EnrichmentRetriesExhaustedError from e
    except asyncio.CancelledError:
        await service.mark_failed(
            job_id,
            error_code="JobAborted",
            error_message="Enrichment job aborted",
        )
        raise
    except Exception as e:
        logger.exception(
            "Enrichment job failed",
            error_code=type(e).__name__,
            error_message=str(e),
        )
        await service.mark_failed(
            job_id,
            error_code=type(e).__name__,
            error_message=str(e),
        )
        raise
    finally:
        await session_generator.aclose()
