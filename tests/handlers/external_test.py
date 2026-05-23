"""Tests for the obsforge.handlers.external module and routes."""

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient

from obsforge.config import config
from obsforge.models import SerializedEnrichmentJob, VisitRegistration
from obsforge.schema import EnrichmentJobPhase


@pytest.mark.asyncio
async def test_get_index(client: AsyncClient) -> None:
    """Test ``GET /obsforge/``."""
    response = await client.get("/obsforge/")
    assert response.status_code == 200
    data = response.json()
    metadata = data["metadata"]
    assert metadata["name"] == config.name
    assert isinstance(metadata["version"], str)
    assert isinstance(metadata["description"], str)
    assert isinstance(metadata["repository_url"], str)
    assert isinstance(metadata["documentation_url"], str)


@pytest.mark.asyncio
async def test_register_visit(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test ``POST /obsforge/register``."""

    class MockEnrichmentJobService:
        def __init__(self, store: Any) -> None:
            self.store = store

        async def register_visit(
            self, registration: VisitRegistration
        ) -> SerializedEnrichmentJob:
            now = datetime(2026, 1, 9, 2, 45, 51, tzinfo=UTC)
            return SerializedEnrichmentJob(
                id=42,
                visit=registration.visit,
                instrument=registration.instrument,
                day_obs=registration.day_obs,
                phase=EnrichmentJobPhase.PENDING,
                attempt_count=0,
                error_code=None,
                error_message=None,
                registration_payload=registration.model_dump(mode="json"),
                created_at=now,
                updated_at=now,
                started_at=None,
                completed_at=None,
            )

    monkeypatch.setattr(
        "obsforge.handlers.external.EnrichmentJobService",
        MockEnrichmentJobService,
    )
    payload = {
        "instrument": "LSSTCam",
        "day_obs": 20260108,
        "visit": 2026010800095,
        "timespan": {
            "begin": "2026-01-09T02:45:51Z",
            "end": "2026-01-09T02:46:26Z",
        },
    }

    response = await client.post("/obsforge/register", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "id": 42,
        "visit": 2026010800095,
        "instrument": "LSSTCam",
        "day_obs": 20260108,
        "phase": "PENDING",
        "attempt_count": 0,
        "registration_payload": payload,
        "created_at": "2026-01-09T02:45:51Z",
        "updated_at": "2026-01-09T02:45:51Z",
    }


@pytest.mark.asyncio
async def test_register_visit_persists_job(client: AsyncClient) -> None:
    """Test ``POST /obsforge/register`` against the database."""
    payload = {
        "instrument": "LSSTCam",
        "day_obs": 20260108,
        "visit": 2026010800095,
        "timespan": {
            "begin": "2026-01-09T02:45:51Z",
            "end": "2026-01-09T02:46:26Z",
        },
    }

    first_response = await client.post("/obsforge/register", json=payload)
    second_response = await client.post("/obsforge/register", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first = first_response.json()
    second = second_response.json()
    assert second == first
    assert first["id"] > 0
    assert first["visit"] == 2026010800095
    assert first["instrument"] == "LSSTCam"
    assert first["day_obs"] == 20260108
    assert first["phase"] == "PENDING"
    assert first["registration_payload"] == payload
    assert first["created_at"].endswith("Z")
    assert first["updated_at"].endswith("Z")
