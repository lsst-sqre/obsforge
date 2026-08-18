"""Handlers for the app's external root, ``/obsforge/``."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from safir.arq import ArqQueue
from safir.dependencies.arq import arq_dependency
from safir.dependencies.db_session import db_session_dependency
from safir.dependencies.logger import logger_dependency
from safir.metadata import get_metadata
from safir.slack.webhook import SlackRouteErrorHandler
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.stdlib import BoundLogger

from ..config import config
from ..models import Index, SerializedEnrichmentJob, VisitRegistration
from ..services import EnrichmentJobService
from ..storage import EnrichmentJobStore, EnrichmentQueueStore

__all__ = ["external_router"]

external_router = APIRouter(route_class=SlackRouteErrorHandler)
"""FastAPI router for all external handlers."""


@external_router.get(
    "/",
    description=(
        "Document the top-level API here. By default it only returns metadata"
        " about the application."
    ),
    response_model_exclude_none=True,
    summary="Application metadata",
)
async def get_index(
    logger: Annotated[BoundLogger, Depends(logger_dependency)],
) -> Index:
    # Customize this handler to return whatever the top-level resource of your
    # application should return. For example, consider listing key API URLs.
    # When doing so, also change or customize the response model in
    # obsforge.models.Index.
    #
    # By convention, the root of the external API includes a field called
    # metadata that provides the same Safir-generated metadata as the internal
    # root endpoint.

    logger.debug("Request for application metadata")

    metadata = get_metadata(
        package_name="obsforge",
        application_name=config.name,
    )
    return Index(metadata=metadata)


@external_router.post(
    "/register",
    response_model=SerializedEnrichmentJob,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Register a visit for enrichment",
)
async def register_visit(
    *,
    registration: VisitRegistration,
    response: Response,
    arq_queue: Annotated[ArqQueue, Depends(arq_dependency)],
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    logger: Annotated[BoundLogger, Depends(logger_dependency)],
) -> SerializedEnrichmentJob:
    store = EnrichmentJobStore(session)
    queue = EnrichmentQueueStore(arq_queue, logger)
    service = EnrichmentJobService(store, queue, logger=logger)
    job = await service.register_visit(registration)
    response.headers["Location"] = f"{config.path_prefix}/jobs/{job.id}"
    return job


@external_router.get(
    "/jobs/{job_id}",
    response_model=SerializedEnrichmentJob,
    summary="Get an enrichment job",
)
async def get_job(
    *,
    job_id: int,
    arq_queue: Annotated[ArqQueue, Depends(arq_dependency)],
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    logger: Annotated[BoundLogger, Depends(logger_dependency)],
) -> SerializedEnrichmentJob:
    store = EnrichmentJobStore(session)
    queue = EnrichmentQueueStore(arq_queue, logger)
    service = EnrichmentJobService(store, queue, logger=logger)
    return await service.get(job_id)


@external_router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Abort an enrichment job",
)
async def delete_job(
    *,
    job_id: int,
    arq_queue: Annotated[ArqQueue, Depends(arq_dependency)],
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    logger: Annotated[BoundLogger, Depends(logger_dependency)],
) -> None:
    store = EnrichmentJobStore(session)
    queue = EnrichmentQueueStore(arq_queue, logger)
    service = EnrichmentJobService(store, queue, logger=logger)
    aborted = await service.abort(job_id)
    if not aborted:
        raise HTTPException(status_code=404, detail="Queued job not found")
