"""The main application factory for the obsforge service.

Notes
-----
Be aware that, following the normal pattern for FastAPI services, the app is
constructed when this module is loaded and is not deferred until a function is
called.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib.metadata import metadata, version

import structlog
from fastapi import FastAPI
from safir.database import create_database_engine, is_database_current
from safir.dependencies.arq import arq_dependency
from safir.dependencies.db_session import db_session_dependency
from safir.dependencies.http_client import http_client_dependency
from safir.logging import configure_uvicorn_logging
from safir.middleware.x_forwarded import XForwardedMiddleware
from safir.slack.webhook import SlackRouteErrorHandler

from .config import config
from .handlers.external import external_router
from .handlers.internal import internal_router

__all__ = ["app"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Set up and tear down the application."""
    # Any code here will be run when the application starts up.
    logger = structlog.get_logger("obsforge")
    engine = create_database_engine(
        config.database_url, config.database_password
    )
    try:
        if not await is_database_current(engine, logger):
            raise RuntimeError("Database schema out of date")
    finally:
        await engine.dispose()

    await db_session_dependency.initialize(
        config.database_url,
        config.database_password,
        # Keep job-state reads stable during transactional phase updates.
        isolation_level="REPEATABLE READ",
    )
    await arq_dependency.initialize(
        mode=config.arq_mode, redis_settings=config.arq_redis_settings
    )

    yield

    # Any code here will be run when the application shuts down.
    await arq_dependency.aclose()
    await db_session_dependency.aclose()
    await http_client_dependency.aclose()


configure_uvicorn_logging(config.log_level)

app = FastAPI(
    title="obsforge",
    description=metadata("obsforge")["Summary"],
    version=version("obsforge"),
    openapi_url=f"{config.path_prefix}/openapi.json",
    docs_url=f"{config.path_prefix}/docs",
    redoc_url=f"{config.path_prefix}/redoc",
    lifespan=lifespan,
)
"""The main FastAPI application for obsforge."""

# Attach the routers.
app.include_router(internal_router)
app.include_router(external_router, prefix=f"{config.path_prefix}")

# Add middleware.
app.add_middleware(XForwardedMiddleware)

# Configure Slack alerts.
if config.slack_webhook:
    logger = structlog.get_logger("obsforge")
    SlackRouteErrorHandler.initialize(config.slack_webhook, "obsforge", logger)
    logger.debug("Initialized Slack webhook")
