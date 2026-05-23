"""Test fixtures for obsforge tests."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from obsforge import main


@pytest_asyncio.fixture
async def app(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[FastAPI]:
    """Return a configured test application.

    Wraps the application in a lifespan manager so that startup and shutdown
    events are sent during test execution.
    """

    class FakeEngine:
        async def dispose(self) -> None:
            pass

    def fake_create_database_engine(url: Any, password: Any) -> FakeEngine:
        return FakeEngine()

    async def fake_is_database_current(
        engine: FakeEngine, logger: Any = None, config_path: Any = None
    ) -> bool:
        return True

    monkeypatch.setattr(
        main, "create_database_engine", fake_create_database_engine
    )
    monkeypatch.setattr(main, "is_database_current", fake_is_database_current)

    async with LifespanManager(main.app):
        yield main.app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    """Return an ``httpx.AsyncClient`` configured to talk to the test app."""
    async with AsyncClient(
        base_url="https://example.com/", transport=ASGITransport(app=app)
    ) as client:
        yield client
