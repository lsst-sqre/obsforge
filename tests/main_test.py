"""Tests for the ObsForge application lifecycle."""

import pytest
from fastapi import FastAPI
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_lifespan_initializes_database_session(app: FastAPI) -> None:
    session_generator = db_session_dependency()
    session = await anext(session_generator)
    try:
        assert isinstance(session, AsyncSession)
    finally:
        await session_generator.aclose()
