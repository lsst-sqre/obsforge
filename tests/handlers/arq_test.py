"""Tests for mocked arq queue integration."""

import pytest
from httpx import AsyncClient
from safir.arq import ArqMode, MockArqQueue
from safir.dependencies.arq import arq_dependency
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge.config import config
from obsforge.storage import EnrichmentJobStore

pytestmark = pytest.mark.skipif(
    config.arq_mode != ArqMode.test, reason="requires mocked arq mode"
)


def make_payload(visit: int) -> dict[str, object]:
    return {
        "instrument": "LSSTCam",
        "day_obs": 20260327,
        "visit": visit,
        "datasets": [
            {
                "dataset_type": "preliminary_visit_image",
                "id": "019ba0a6-0173-765f-bf27-56884ff9342a",
            }
        ],
        "timespan": {
            "begin": "2026-03-27T08:15:10Z",
            "end": "2026-03-27T08:15:45Z",
        },
    }


@pytest.mark.asyncio
async def test_mock_arq_queue_status_overlay(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test mocked arq state is reflected in job status responses."""
    arq_queue = await arq_dependency()
    assert isinstance(arq_queue, MockArqQueue)
    response = await client.post(
        "/obsforge/register", json=make_payload(20260327123456)
    )
    job_id = response.json()["id"]
    store = EnrichmentJobStore(db_session)
    job = await store.get_internal(job_id)
    assert job.arq_job_id is not None

    await arq_queue.set_in_progress(job.arq_job_id)
    response = await client.get(f"/obsforge/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["phase"] == "EXECUTING"

    await arq_queue.set_complete(job.arq_job_id, result={"ok": True})
    response = await client.get(f"/obsforge/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["phase"] == "COMPLETED"


@pytest.mark.asyncio
async def test_mock_arq_queue_abort(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test aborting a mocked arq job."""
    response = await client.post(
        "/obsforge/register", json=make_payload(20260327654321)
    )
    job_id = response.json()["id"]
    store = EnrichmentJobStore(db_session)
    job = await store.get_internal(job_id)
    assert job.arq_job_id is not None

    response = await client.delete(f"/obsforge/jobs/{job_id}")

    assert response.status_code == 204
    seen = await store.get(job_id)
    assert seen.phase.value == "ERROR"
    assert seen.error_code == "JobAborted"
