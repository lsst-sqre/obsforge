"""Tests for enrichment worker functions."""

from collections.abc import Mapping
from typing import Any

import pytest
import structlog
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge.models import VisitRegistration
from obsforge.schema import EnrichmentJobPhase
from obsforge.storage import EnrichmentJobStore
from obsforge.worker.functions import enrichment


def make_registration(visit_id: str) -> VisitRegistration:
    return VisitRegistration.model_validate(
        {
            "instrument": "LSSTCam",
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
