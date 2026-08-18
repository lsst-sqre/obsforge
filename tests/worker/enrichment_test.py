"""Tests for enrichment worker functions."""

from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
import structlog
from arq.worker import Retry
from fastapi import FastAPI
from pydantic import SecretStr, ValidationError
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from obsforge.adapters import MissingObsCoreDatasetError
from obsforge.config import config
from obsforge.models import ObsCoreUpsert, VisitRegistration
from obsforge.schema import EnrichmentJobPhase
from obsforge.services import ObsCoreService
from obsforge.storage import (
    DuplicateObsCoreBatchError,
    EnrichmentJobStore,
    ObsCoreStore,
)
from obsforge.worker import main as worker_main
from obsforge.worker.functions import enrichment
from obsforge.worker.main import WorkerSettings


def make_registration(visit: int) -> VisitRegistration:
    return VisitRegistration.model_validate(
        {
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
    )


def make_obscore_upsert(
    obs_id: str, *, lsst_detector: int = 125
) -> ObsCoreUpsert:
    return ObsCoreUpsert(
        dataproduct_type="image",
        dataproduct_subtype="lsst.visit_image",
        facility_name="Rubin:Simonyi",
        calib_level=2,
        target_name="ddf_ecdfs, lowdust",
        obs_id=obs_id,
        obs_collection="LSST.Prompt",
        obs_publisher_did=f"D{obs_id}",
        access_url=f"https://example.com/api/datalink/links?ID=D{obs_id}",
        access_format="application/x-votable+xml;content=datalink",
        access_estsize=None,
        s_resolution=None,
        s_xel1=None,
        s_xel2=None,
        t_xel=None,
        t_min=61049.11561010359,
        t_max=61049.115968101854,
        t_exptime=30.0,
        t_resolution=None,
        em_xel=None,
        em_min=4.026e-07,
        em_max=5.483e-07,
        em_res_power=None,
        em_filter_name="g",
        o_ucd="phot.flux.density",
        pol_xel=None,
        instrument_name="LSSTCam",
        lsst_visit=2026010800095,
        lsst_detector=lsst_detector,
        lsst_tract=None,
        lsst_patch=None,
        lsst_band="g",
        lsst_filter="g_6",
        obs_title=(
            "visit_image - g - MC_O_20260108_000095-R30_S22 "
            "2026-01-09T02:45:51.712950Z"
        ),
        s_ra=54.00926387186998,
        s_dec=-27.174727694762304,
        s_fov=0.3572492942259721,
        s_region=(
            "POLYGON ICRS 53.891809 -27.319323 "
            "54.174563 -27.276221 54.126402 -27.030061 "
            "53.844298 -27.072994"
        ),
    )


@pytest.mark.asyncio
async def test_run_enrichment_marks_completed(
    app: FastAPI, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test a successful worker job."""
    adapter_instances: list[Any] = []
    batch_calls: list[list[str]] = []
    real_obscore_service = ObsCoreService

    class FakeDaxObsCoreAdapter:
        def __init__(
            self,
            *,
            butler_factory: Any,
            butler_label: str,
            config: Any,
            dataset_type: str,
            access_token: str | None = None,
        ) -> None:
            self.butler_factory = butler_factory
            self.butler_label = butler_label
            self.config = config
            self.dataset_type = dataset_type
            self.access_token = access_token
            self.registration: VisitRegistration | None = None
            adapter_instances.append(self)

        def iter_visit_records(
            self, registration: VisitRegistration
        ) -> Iterator[ObsCoreUpsert]:
            self.registration = registration
            dataset_id = str(registration.datasets[0].id)
            yield make_obscore_upsert(f"{dataset_id}-125", lsst_detector=125)
            yield make_obscore_upsert(f"{dataset_id}-126", lsst_detector=126)

    class SpyObsCoreService:
        def __init__(self, store: Any) -> None:
            self._delegate = real_obscore_service(store)

        async def upsert(self, record: ObsCoreUpsert) -> Any:
            raise AssertionError("worker should use upsert_many")

        async def upsert_many(
            self, records: Sequence[ObsCoreUpsert]
        ) -> list[Any]:
            records = list(records)
            batch_calls.append([record.obs_id for record in records])
            return await self._delegate.upsert_many(records)

    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration(20260327123456))
    await store.mark_queued(created.id)
    monkeypatch.setattr(enrichment, "DaxObsCoreAdapter", FakeDaxObsCoreAdapter)
    monkeypatch.setattr(enrichment, "ObsCoreService", SpyObsCoreService)

    await enrichment.run_enrichment(
        {
            "logger": structlog.get_logger("test"),
            "labeled_butler_factory": object(),
            "obscore_config": object(),
            "obscore_dataset_type": "preliminary_visit_image",
            "butler_access_token": SecretStr("worker-token"),
        },
        created.id,
    )

    seen = await store.get(created.id)
    assert seen.phase == EnrichmentJobPhase.COMPLETED
    assert seen.started_at is not None
    assert seen.completed_at is not None
    assert len(adapter_instances) == 1
    assert adapter_instances[0].butler_label == config.butler_label
    assert adapter_instances[0].dataset_type == "preliminary_visit_image"
    assert adapter_instances[0].access_token == "worker-token"
    assert adapter_instances[0].registration == make_registration(
        20260327123456
    )

    dataset_id = str(created.registration_payload["datasets"][0]["id"])
    obs_ids = [f"{dataset_id}-125", f"{dataset_id}-126"]
    assert batch_calls == [obs_ids]
    obscore_store = ObsCoreStore(db_session)
    first = await obscore_store.get_by_obs_id(obs_ids[0])
    second = await obscore_store.get_by_obs_id(obs_ids[1])
    assert first.obs_id == obs_ids[0]
    assert first.lsst_detector == 125
    assert second.obs_id == obs_ids[1]
    assert second.lsst_detector == 126


@pytest.mark.asyncio
async def test_run_enrichment_marks_failed(
    app: FastAPI,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a failing worker job."""

    async def fail(
        job_id: int,
        *,
        session: AsyncSession,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        raise RuntimeError("metadata missing")

    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration(20260327654321))
    await store.mark_queued(created.id)
    monkeypatch.setattr(enrichment, "enrich_visit", fail)

    with capture_logs() as logs:
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
    failure_log = next(
        log for log in logs if log["event"] == "Enrichment job failed"
    )
    assert failure_log["log_level"] == "error"
    assert failure_log["enrichment_job_id"] == created.id
    assert failure_log["job_try"] == 1
    assert failure_log["max_tries"] == config.enrichment_max_tries
    assert failure_log["error_code"] == "RuntimeError"
    assert failure_log["error_message"] == "metadata missing"


@pytest.mark.asyncio
async def test_run_enrichment_marks_failed_on_missing_worker_context(
    app: FastAPI, db_session: AsyncSession
) -> None:
    """Test missing worker context records a specific error code."""
    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration(20260327654321))
    await store.mark_queued(created.id)

    with pytest.raises(
        enrichment.MissingWorkerContextError,
        match="Worker context missing 'butler_access_token'",
    ):
        await enrichment.run_enrichment(
            {"logger": structlog.get_logger("test")}, created.id
        )

    seen = await store.get(created.id)
    assert seen.phase == EnrichmentJobPhase.ERROR
    assert seen.error_code == "MissingWorkerContextError"
    assert seen.error_message == "Worker context missing 'butler_access_token'"
    assert seen.started_at is not None
    assert seen.completed_at is not None


@pytest.mark.asyncio
async def test_run_enrichment_marks_failed_on_missing_obscore_dataset(
    app: FastAPI, db_session: AsyncSession
) -> None:
    """Test missing ObsCore datasets record a specific error code."""
    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration(20260327654321))
    await store.mark_queued(created.id)

    with pytest.raises(
        MissingObsCoreDatasetError,
        match="Registration payload does not include difference_image",
    ):
        await enrichment.run_enrichment(
            {
                "logger": structlog.get_logger("test"),
                "labeled_butler_factory": object(),
                "obscore_config": object(),
                "obscore_dataset_type": "difference_image",
                "butler_access_token": SecretStr("worker-token"),
            },
            created.id,
        )

    seen = await store.get(created.id)
    assert seen.phase == EnrichmentJobPhase.ERROR
    assert seen.error_code == "MissingObsCoreDatasetError"
    assert seen.error_message == (
        "Registration payload does not include difference_image datasets"
    )
    assert seen.started_at is not None
    assert seen.completed_at is not None


@pytest.mark.asyncio
async def test_run_enrichment_marks_failed_on_duplicate_obscore_batch(
    app: FastAPI, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test duplicate ObsCore batches record a specific error code."""

    class FakeDaxObsCoreAdapter:
        def __init__(
            self,
            *,
            butler_factory: Any,
            butler_label: str,
            config: Any,
            dataset_type: str,
            access_token: str | None = None,
        ) -> None:
            pass

        def iter_visit_records(
            self, registration: VisitRegistration
        ) -> Iterator[ObsCoreUpsert]:
            dataset_id = str(registration.datasets[0].id)
            yield make_obscore_upsert(dataset_id)
            yield make_obscore_upsert(dataset_id)

    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration(20260327654321))
    await store.mark_queued(created.id)
    monkeypatch.setattr(enrichment, "DaxObsCoreAdapter", FakeDaxObsCoreAdapter)

    with pytest.raises(DuplicateObsCoreBatchError, match="duplicate obs_id"):
        await enrichment.run_enrichment(
            {
                "logger": structlog.get_logger("test"),
                "labeled_butler_factory": object(),
                "obscore_config": object(),
                "obscore_dataset_type": "preliminary_visit_image",
                "butler_access_token": SecretStr("worker-token"),
            },
            created.id,
        )

    seen = await store.get(created.id)
    assert seen.phase == EnrichmentJobPhase.ERROR
    assert seen.error_code == "DuplicateObsCoreBatchError"
    assert seen.error_message == (
        "ObsCore batch contains duplicate obs_id values"
    )
    assert seen.started_at is not None
    assert seen.completed_at is not None


def test_worker_settings_uses_enrichment_max_tries() -> None:
    """Test arq and the worker function share the retry limit."""
    assert WorkerSettings.max_tries == config.enrichment_max_tries


@pytest.mark.asyncio
async def test_worker_startup_initializes_obscore_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test worker startup builds shared ObsCore enrichment resources."""
    seen: dict[str, Any] = {}

    class FakeButlerConfig:
        def __init__(self, path_or_url: str) -> None:
            seen["obscore_config_path"] = path_or_url

    class FakeExporterConfig:
        @classmethod
        def model_validate(cls, value: Any) -> str:
            seen["exporter_config_data"] = value
            return "exporter-config"

    class FakeLabeledButlerFactory:
        def __init__(self, repositories: dict[str, str]) -> None:
            seen["repositories"] = repositories

    async def initialize_db_session(*args: Any, **kwargs: Any) -> None:
        seen["db_session"] = (args, kwargs)

    monkeypatch.setattr(config, "butler_label", "prompt")
    monkeypatch.setattr(config, "butler_repository", Path("/repo/prompt"))
    monkeypatch.setattr(config, "butler_access_token", SecretStr("token"))
    monkeypatch.setattr(config, "obscore_config", Path("/configs/prompt.yaml"))
    monkeypatch.setattr(
        config,
        "obscore_dataset_type",
        "preliminary_visit_image",
    )
    monkeypatch.setattr(
        worker_main, "LabeledButlerFactory", FakeLabeledButlerFactory
    )
    monkeypatch.setattr(worker_main, "ButlerConfig", FakeButlerConfig)
    monkeypatch.setattr(worker_main, "ExporterConfig", FakeExporterConfig)
    monkeypatch.setattr(
        db_session_dependency, "initialize", initialize_db_session
    )

    ctx: dict[Any, Any] = {}
    await worker_main.startup(ctx)

    assert ctx["labeled_butler_factory"].__class__ is FakeLabeledButlerFactory
    assert ctx["obscore_config"] == "exporter-config"
    assert ctx["obscore_dataset_type"] == "preliminary_visit_image"
    assert ctx["butler_access_token"].get_secret_value() == "token"
    assert seen["repositories"] == {"prompt": "/repo/prompt"}
    assert seen["obscore_config_path"] == "/configs/prompt.yaml"
    assert seen["exporter_config_data"].__class__ is FakeButlerConfig
    assert seen["db_session"][1]["isolation_level"] == "REPEATABLE READ"


@pytest.mark.asyncio
async def test_worker_startup_requires_obscore_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test worker startup reports all missing ObsCore settings."""
    monkeypatch.setattr(config, "butler_repository", None)
    monkeypatch.setattr(config, "butler_access_token", None)
    monkeypatch.setattr(config, "obscore_config", None)

    with pytest.raises(ValidationError) as exc_info:
        await worker_main.startup({})

    error_fields = {
        error["loc"][0] for error in exc_info.value.errors(include_url=False)
    }
    assert error_fields == {
        "butler_repository",
        "butler_access_token",
        "obscore_config",
    }


@pytest.mark.asyncio
async def test_worker_shutdown_removes_obscore_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test worker shutdown clears shared ObsCore worker resources."""
    seen: dict[str, bool] = {}

    async def close_db_session() -> None:
        seen["db_session_closed"] = True

    monkeypatch.setattr(db_session_dependency, "aclose", close_db_session)
    ctx: dict[Any, Any] = {
        "logger": structlog.get_logger("test"),
        "labeled_butler_factory": object(),
        "obscore_config": object(),
        "obscore_dataset_type": "preliminary_visit_image",
        "butler_access_token": SecretStr("token"),
    }

    await worker_main.shutdown(ctx)

    assert "labeled_butler_factory" not in ctx
    assert "obscore_config" not in ctx
    assert "obscore_dataset_type" not in ctx
    assert "butler_access_token" not in ctx
    assert seen["db_session_closed"] is True


@pytest.mark.asyncio
async def test_run_enrichment_reraises_retry_before_final_attempt(
    app: FastAPI,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test arq Retry is preserved before retries are exhausted."""

    async def retry(
        job_id: int,
        *,
        session: AsyncSession,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        raise Retry

    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration(20260327123456))
    await store.mark_queued(created.id)
    monkeypatch.setattr(enrichment, "enrich_visit", retry)

    with capture_logs() as logs:
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
    retry_log = next(
        log for log in logs if log["event"] == "Retrying enrichment job"
    )
    assert retry_log["log_level"] == "debug"
    assert retry_log["enrichment_job_id"] == created.id
    assert retry_log["job_try"] == config.enrichment_max_tries - 1
    assert retry_log["max_tries"] == config.enrichment_max_tries


@pytest.mark.asyncio
async def test_run_enrichment_marks_failed_on_final_retry(
    app: FastAPI,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the final arq Retry records durable failure state."""

    async def retry(
        job_id: int,
        *,
        session: AsyncSession,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        raise Retry

    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(make_registration(20260327123456))
    await store.mark_queued(created.id)
    monkeypatch.setattr(enrichment, "enrich_visit", retry)

    with capture_logs() as logs:
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
    exhausted_log = next(
        log for log in logs if log["event"] == "Enrichment retries exhausted"
    )
    assert exhausted_log["log_level"] == "warning"
    assert exhausted_log["enrichment_job_id"] == created.id
    assert exhausted_log["job_try"] == config.enrichment_max_tries
    assert exhausted_log["max_tries"] == config.enrichment_max_tries
