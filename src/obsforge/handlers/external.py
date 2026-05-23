"""Handlers for the app's external root, ``/obsforge/``."""

from typing import Annotated

from fastapi import APIRouter, Depends
from safir.dependencies.db_session import db_session_dependency
from safir.dependencies.logger import logger_dependency
from safir.metadata import get_metadata
from safir.slack.webhook import SlackRouteErrorHandler
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.stdlib import BoundLogger

from ..config import config
from ..models import Index, SerializedEnrichmentJob, VisitRegistration
from ..services import EnrichmentJobService
from ..storage import EnrichmentJobStore

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

    # There is no need to log simple requests since uvicorn will do this
    # automatically, but this is included as an example of how to use the
    # logger for more complex logging.
    logger.info("Request for application metadata")

    metadata = get_metadata(
        package_name="obsforge",
        application_name=config.name,
    )
    return Index(metadata=metadata)


@external_router.post(
    "/register",
    response_model=SerializedEnrichmentJob,
    response_model_exclude_none=True,
    summary="Register a visit for enrichment",
)
async def register_visit(
    *,
    registration: VisitRegistration,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
) -> SerializedEnrichmentJob:
    store = EnrichmentJobStore(session)
    service = EnrichmentJobService(store)
    return await service.register_visit(registration)
