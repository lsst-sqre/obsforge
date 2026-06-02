"""Tests for enrichment worker functions."""

from collections.abc import Mapping
from typing import Any

import pytest
import structlog
from arq.worker import Retry
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge.config import config
from obsforge.models import VisitRegistration
from obsforge.schema import EnrichmentJobPhase
from obsforge.storage import EnrichmentJobStore
from obsforge.worker.functions import enrichment
from obsforge.worker.main import WorkerSettings


def make_registration(visit_id: str) -> VisitRegistration:
    return VisitRegistration.model_validate(
        {
            "instrument_name": "LSSTCam",
            "day_obs": 20260327,
            "visit_id": visit_id,
            "timespan": {
                "begin": "2026-03-27T08:15:10Z",
                "end": "2026-03-27T08:15:45Z",
            },
        }
    )


@pytest.mark.asyncio
async def test_run_enrichment_marks_completed(
    app: FastAPI, db_session: AsyncSession
) -> None:
    """Test a successful worker job."""
    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(
        make_registration("LSSTCam-20260327-123456")
    )
    await store.mark_queued(created.id)

    await enrichment.run_enrichment(
        {"logger": structlog.get_logger("test")}, created.id
    )

    seen = await store.get(created.id)
    assert seen.phase == EnrichmentJobPhase.COMPLETED
    assert seen.started_at is not None
    assert seen.completed_at is not None


@pytest.mark.asyncio
async def test_run_enrichment_marks_failed(
    app: FastAPI,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a failing worker job."""

    async def fail(
        job_id: int, *, context: Mapping[str, Any] | None = None
    ) -> None:
        raise RuntimeError("metadata missing")

    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(
        make_registration("LSSTCam-20260327-654321")
    )
    await store.mark_queued(created.id)
    monkeypatch.setattr(enrichment, "enrich_visit", fail)

    with pytest.raises(RuntimeError, match="metadata missing"):
        await enrichment.run_enrichment(
            {"logger": structlog.get_logger("test")}, created.id
        )

    seen = await store.get(created.id)
    assert seen.phase == EnrichmentJobPhase.ERROR
    assert seen.error_code == "RuntimeError"
    assert seen.error_message == "metadata missing"
    assert seen.started_at is not None
    assert seen.completed_at is not None


def test_worker_settings_uses_enrichment_max_tries() -> None:
    """Test arq and the worker function share the retry limit."""
    assert WorkerSettings.max_tries == config.enrichment_max_tries


@pytest.mark.asyncio
async def test_run_enrichment_reraises_retry_before_final_attempt(
    app: FastAPI,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test arq Retry is preserved before retries are exhausted."""

    async def retry(
        job_id: int, *, context: Mapping[str, Any] | None = None
    ) -> None:
        raise Retry

    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(
        make_registration("LSSTCam-20260327-retry1")
    )
    await store.mark_queued(created.id)
    monkeypatch.setattr(enrichment, "enrich_visit", retry)

    with pytest.raises(Retry):
        await enrichment.run_enrichment(
            {
                "logger": structlog.get_logger("test"),
                "job_try": config.enrichment_max_tries - 1,
            },
            created.id,
        )

    seen = await store.get(created.id)
    assert seen.phase == EnrichmentJobPhase.EXECUTING
    assert seen.error_code is None
    assert seen.error_message is None
    assert seen.started_at is not None
    assert seen.completed_at is None


@pytest.mark.asyncio
async def test_run_enrichment_marks_failed_on_final_retry(
    app: FastAPI,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the final arq Retry records durable failure state."""

    async def retry(
        job_id: int, *, context: Mapping[str, Any] | None = None
    ) -> None:
        raise Retry

    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(
        make_registration("LSSTCam-20260327-retry2")
    )
    await store.mark_queued(created.id)
    monkeypatch.setattr(enrichment, "enrich_visit", retry)

    with pytest.raises(RuntimeError, match="retries exhausted"):
        await enrichment.run_enrichment(
            {
                "logger": structlog.get_logger("test"),
                "job_try": config.enrichment_max_tries,
            },
            created.id,
        )

    seen = await store.get(created.id)
    assert seen.phase == EnrichmentJobPhase.ERROR
    assert seen.error_code == "RetriesExhausted"
    assert seen.error_message == (
        f"Enrichment job exhausted {config.enrichment_max_tries} arq attempts"
    )
    assert seen.started_at is not None
    assert seen.completed_at is not None
