"""Tests for the ObsForge application lifecycle."""

from typing import Any

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge import main


@pytest.mark.asyncio
async def test_lifespan_initializes_database_session(app: FastAPI) -> None:
    session_generator = db_session_dependency()
    session = await anext(session_generator)
    try:
        assert isinstance(session, AsyncSession)
    finally:
        await session_generator.aclose()


@pytest.mark.asyncio
async def test_lifespan_rejects_outdated_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeEngine:
        async def dispose(self) -> None:
            pass

    def fake_create_database_engine(url: Any, password: Any) -> FakeEngine:
        return FakeEngine()

    async def fake_is_database_current(
        engine: FakeEngine, logger: Any = None, config_path: Any = None
    ) -> bool:
        return False

    monkeypatch.setattr(
        main, "create_database_engine", fake_create_database_engine
    )
    monkeypatch.setattr(main, "is_database_current", fake_is_database_current)

    with pytest.raises(RuntimeError, match="Database schema out of date"):
        async with LifespanManager(main.app):
            pass
