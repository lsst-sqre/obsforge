"""Tests for the obsforge.handlers.external module and routes."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
import structlog
from httpx import AsyncClient
from lsst.dax.obscore import ExporterConfig
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

import obsforge.adapters.obscore as obscore_adapter
from obsforge.adapters import (
    ButlerDatasetCardinalityError,
    MissingObsCoreDatasetError,
)
from obsforge.config import config
from obsforge.handlers import external
from obsforge.models import SerializedEnrichmentJob, VisitRegistration
from obsforge.schema import EnrichmentJobPhase
from obsforge.storage import (
    EnrichmentJobStore,
    ObsCoreStore,
    VisitDetectorStore,
    VisitStore,
)
from obsforge.worker.functions.enrichment import run_enrichment
from tests.support.butler import FakeButler, FakeButlerFactory
from tests.support.obscore import (
    DATASET_ID,
    SECOND_DATASET_ID,
    make_obscore_row,
)
from tests.support.registration import make_visit_registration
from tests.support.visit import (
    DETECTOR_ID,
    INSTRUMENT,
    VISIT_ID,
    make_visit_detector_table,
    make_visit_table,
)


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
async def test_get_index_logs_at_debug() -> None:
    """Test ``GET /obsforge/`` emits only a debug application log."""
    with capture_logs() as logs:
        await external.get_index(logger=structlog.get_logger("test"))

    assert logs == [
        {"event": "Request for application metadata", "log_level": "debug"}
    ]


@pytest.mark.asyncio
async def test_register_visit(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test ``POST /obsforge/register``."""
    loggers: list[Any] = []

    class MockEnrichmentJobService:
        def __init__(
            self, store: Any, queue: Any, logger: Any | None = None
        ) -> None:
            self.store = store
            self.queue = queue
            loggers.append(logger)

        async def register_visit(
            self, registration: VisitRegistration
        ) -> SerializedEnrichmentJob:
            now = datetime(2026, 1, 9, 2, 45, 51, tzinfo=UTC)
            return SerializedEnrichmentJob(
                id=42,
                visit=registration.visit,
                instrument=registration.instrument,
                day_obs=registration.day_obs,
                phase=EnrichmentJobPhase.QUEUED,
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
        "datasets": [
            {
                "dataset_type": "preliminary_visit_image",
                "id": "019ba0a6-0173-765f-bf27-56884ff9342a",
            }
        ],
        "timespan": {
            "begin": "2026-01-09T02:45:51Z",
            "end": "2026-01-09T02:46:26Z",
        },
    }

    response = await client.post("/obsforge/register", json=payload)

    assert response.status_code == 202
    assert response.headers["Location"] == "/obsforge/jobs/42"
    assert len(loggers) == 1
    assert loggers[0] is not None
    assert response.json() == {
        "id": 42,
        "visit": 2026010800095,
        "instrument": "LSSTCam",
        "day_obs": 20260108,
        "phase": "QUEUED",
        "error_code": None,
        "error_message": None,
        "registration_payload": payload,
        "created_at": "2026-01-09T02:45:51Z",
        "updated_at": "2026-01-09T02:45:51Z",
        "started_at": None,
        "completed_at": None,
    }


@pytest.mark.asyncio
async def test_register_visit_persists_job(client: AsyncClient) -> None:
    """Test ``POST /obsforge/register`` against the database."""
    payload = {
        "instrument": "LSSTCam",
        "day_obs": 20260108,
        "visit": 2026010800095,
        "datasets": [
            {
                "dataset_type": "preliminary_visit_image",
                "id": "019ba0a6-0173-765f-bf27-56884ff9342a",
            }
        ],
        "timespan": {
            "begin": "2026-01-09T02:45:51Z",
            "end": "2026-01-09T02:46:26Z",
        },
    }

    first_response = await client.post("/obsforge/register", json=payload)
    second_response = await client.post("/obsforge/register", json=payload)

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    first = first_response.json()
    second = second_response.json()
    assert second == first
    expected_location = f"/obsforge/jobs/{first['id']}"
    assert first_response.headers["Location"] == expected_location
    assert first["id"] > 0
    assert first["visit"] == 2026010800095
    assert first["instrument"] == "LSSTCam"
    assert first["day_obs"] == 20260108
    assert first["phase"] == "QUEUED"
    assert first["registration_payload"] == payload
    assert first["created_at"].endswith("Z")
    assert first["updated_at"].endswith("Z")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    [ButlerDatasetCardinalityError, MissingObsCoreDatasetError],
)
async def test_corrected_registration_recovers_failed_job(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[ValueError],
) -> None:
    dataset_type = "preliminary_visit_image"
    visit_table_id = UUID("01a1b340-154e-7fce-b26c-b671f660788f")
    detector_table_id = UUID("01a1b340-154e-7fce-b26c-b671f6607890")
    corrected = make_visit_registration(
        visit=VISIT_ID,
        datasets=[
            {"dataset_type": dataset_type, "id": SECOND_DATASET_ID},
            {"dataset_type": "visit_table", "id": visit_table_id},
            {"dataset_type": "visit_detector_table", "id": detector_table_id},
        ],
    )
    if error_type is ButlerDatasetCardinalityError:
        initial = make_visit_registration(visit=VISIT_ID)
    else:
        initial = corrected.model_copy(
            update={"datasets": corrected.datasets[1:]}
        )

    butler = FakeButler(
        {
            visit_table_id: ("visit_table", make_visit_table()),
            detector_table_id: (
                "visit_detector_table",
                make_visit_detector_table(),
            ),
        }
    )
    requested_images: list[UUID] = []

    class FakeObsCoreExporter:
        def __init__(self, butler: FakeButler, config: ExporterConfig) -> None:
            constraint = config.dataset_type_constraints[dataset_type][0]
            self.dataset_ids: list[UUID] = constraint.bind["dataset_ids"]
            requested_images.extend(self.dataset_ids)

        def iter_records(self) -> Iterator[dict[str, Any]]:
            for dataset_id in self.dataset_ids:
                yield make_obscore_row(
                    obs_id=str(dataset_id), lsst_visit=VISIT_ID
                )

    monkeypatch.setattr(
        obscore_adapter, "ObscoreExporter", FakeObsCoreExporter
    )
    context = {
        "labeled_butler_factory": FakeButlerFactory(butler),
        "obscore_config": ExporterConfig.model_validate(
            {
                "facility_name": "Rubin:Simonyi",
                "dataset_types": {
                    dataset_type: {
                        "dataproduct_type": "image",
                        "calib_level": 2,
                    }
                },
            }
        ),
        "obscore_dataset_type": dataset_type,
        "butler_access_token": SecretStr("worker-token"),
    }
    jobs = EnrichmentJobStore(db_session)
    response = await client.post(
        "/obsforge/register", json=initial.model_dump(mode="json")
    )
    assert response.status_code == 202
    job_id = response.json()["id"]
    first_attempt = await jobs.get_internal(job_id)
    assert first_attempt.arq_job_id is not None

    with pytest.raises(error_type) as exc_info:
        await run_enrichment(context, job_id)
    failed = await jobs.get(job_id)
    assert failed.phase == EnrichmentJobPhase.ERROR
    assert failed.error_code == error_type.__name__
    assert failed.error_message == str(exc_info.value)
    assert butler.requested_ids == []

    payload = corrected.model_dump(mode="json")
    response = await client.post("/obsforge/register", json=payload)
    assert response.status_code == 202
    assert response.headers["Location"] == f"/obsforge/jobs/{job_id}"
    retry = await jobs.get_internal(job_id)
    assert retry.phase == EnrichmentJobPhase.QUEUED
    assert retry.registration_payload == payload
    assert retry.arq_job_id is not None
    assert retry.arq_job_id != first_attempt.arq_job_id

    await run_enrichment(context, job_id)

    completed = await jobs.get(job_id)
    assert completed.phase == EnrichmentJobPhase.COMPLETED
    assert completed.registration_payload == payload
    assert butler.requested_ids == [visit_table_id, detector_table_id]
    expected_images = [SECOND_DATASET_ID]
    if error_type is ButlerDatasetCardinalityError:
        expected_images.insert(0, DATASET_ID)
    assert requested_images == expected_images

    visit = await VisitStore(db_session).get_by_visit_id(INSTRUMENT, VISIT_ID)
    detectors = await VisitDetectorStore(db_session).get_by_visit_id(
        INSTRUMENT, VISIT_ID
    )
    obs = await ObsCoreStore(db_session).get_by_obs_id(str(SECOND_DATASET_ID))
    assert visit.visitId == obs.lsst_visit == VISIT_ID
    assert [record.detectorId for record in detectors] == [DETECTOR_ID]


@pytest.mark.asyncio
async def test_register_visit_rejects_malformed_dataset_id(
    client: AsyncClient,
) -> None:
    """Test dataset IDs must be UUIDs."""
    payload = {
        "instrument": "LSSTCam",
        "day_obs": 20260108,
        "visit": 2026010800095,
        "datasets": [
            {
                "dataset_type": "preliminary_visit_image",
                "id": "not-a-uuid",
            }
        ],
        "timespan": {
            "begin": "2026-01-09T02:45:51Z",
            "end": "2026-01-09T02:46:26Z",
        },
    }

    response = await client.post("/obsforge/register", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == [
        "body",
        "datasets",
        0,
        "id",
    ]


@pytest.mark.asyncio
async def test_get_job(client: AsyncClient) -> None:
    """Test ``GET /obsforge/jobs/{job_id}``."""
    payload = {
        "instrument": "LSSTCam",
        "day_obs": 20260327,
        "visit": "20260327123456",
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
    created_response = await client.post("/obsforge/register", json=payload)
    job_id = created_response.json()["id"]

    response = await client.get(f"/obsforge/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["id"] == job_id
    assert response.json()["phase"] == "QUEUED"
    assert response.json()["error_code"] is None
    assert response.json()["error_message"] is None
    assert response.json()["started_at"] is None
    assert response.json()["completed_at"] is None


@pytest.mark.asyncio
async def test_get_unknown_job_returns_404(client: AsyncClient) -> None:
    """Test missing job status responses."""
    response = await client.get("/obsforge/jobs/404")

    assert response.status_code == 404
    assert response.json() == {
        "detail": [
            {
                "msg": "Unknown enrichment job 404",
                "type": "unknown_enrichment_job",
            }
        ]
    }
