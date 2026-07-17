"""Test fixtures for obsforge tests."""

from collections.abc import AsyncGenerator

import pytest_asyncio
import structlog
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from safir.database import (
    create_database_engine,
    initialize_database,
    stamp_database_async,
)
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge import main
from obsforge.config import config
from obsforge.schema import SchemaBase


@pytest_asyncio.fixture
async def app() -> AsyncGenerator[FastAPI]:
    """Return a configured test application.

    Wraps the application in a lifespan manager so that startup and shutdown
    events are sent during test execution.
    """
    logger = structlog.get_logger(__name__)
    engine = create_database_engine(
        config.database_url, config.database_password
    )
    await initialize_database(
        engine, logger, schema=SchemaBase.metadata, reset=True
    )
    await stamp_database_async(engine)
    await engine.dispose()

    async with LifespanManager(main.app):
        yield main.app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    """Return an ``httpx.AsyncClient`` configured to talk to the test app."""
    async with AsyncClient(
        base_url="https://example.com/", transport=ASGITransport(app=app)
    ) as client:
        yield client


@pytest_asyncio.fixture
async def db_session(app: FastAPI) -> AsyncGenerator[AsyncSession]:
    """Return an initialized database session."""
    session_generator = db_session_dependency()
    session = await anext(session_generator)
    try:
        yield session
    finally:
        await session_generator.aclose()
