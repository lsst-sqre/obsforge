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

from obsforge.adapters import (
    ButlerDatasetInstrumentError,
    ButlerVisitRecords,
    MissingObsCoreDatasetError,
    VisitNotFoundInDatasetError,
)
from obsforge.config import config
from obsforge.exceptions import (
    UnknownObsCoreRecordError,
    UnknownVisitRecordError,
)
from obsforge.models import ObsCoreUpsert, VisitRegistration
from obsforge.schema import EnrichmentJobPhase
from obsforge.services import ObsCoreService
from obsforge.storage import (
    DuplicateObsCoreBatchError,
    EnrichmentJobStore,
    ObsCoreStore,
    VisitDetectorStore,
    VisitStore,
)
from obsforge.worker import main as worker_main
from obsforge.worker.functions import enrichment
from obsforge.worker.main import WorkerSettings
from tests.support.butler import FakeButler, FakeButlerFactory
from tests.support.obscore import DATASET_ID, make_obscore_upsert
from tests.support.registration import make_visit_registration
from tests.support.visit import (
    CCD_VISIT_ID,
    DETECTOR_ID,
    INSTRUMENT,
    SECOND_DETECTOR_ID,
    SECOND_INSTRUMENT,
    VISIT_ID,
    make_visit_detector_table,
    make_visit_detector_upsert,
    make_visit_table,
    make_visit_upsert,
)


def make_enrichment_registration(
    visit: int, *, instrument: str = INSTRUMENT
) -> VisitRegistration:
    """Make a registration containing every required dataset type."""
    return make_visit_registration(
        instrument=instrument,
        visit=visit,
        datasets=[
            {
                "dataset_type": "preliminary_visit_image",
                "id": DATASET_ID,
            },
            {
                "dataset_type": "visit_table",
                "id": "01a1b340-154e-7fce-b26c-b671f660788f",
            },
            {
                "dataset_type": "visit_detector_table",
                "id": "01a1b340-154e-7fce-b26c-b671f6607890",
            },
        ],
    )


@pytest.mark.asyncio
async def test_run_enrichment_marks_completed(
    app: FastAPI, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test a successful worker job."""
    adapter_instances: list[Any] = []
    butler_adapter_instances: list[Any] = []
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
            yield make_obscore_upsert(
                obs_id=f"{dataset_id}-125",
                lsst_visit=registration.visit,
                lsst_detector=125,
            )
            yield make_obscore_upsert(
                obs_id=f"{dataset_id}-126",
                lsst_visit=registration.visit,
                lsst_detector=126,
            )

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

    class FakeButlerAdapter:
        def __init__(
            self,
            *,
            butler_factory: Any,
            butler_label: str,
            access_token: str,
        ) -> None:
            self.butler_factory = butler_factory
            self.butler_label = butler_label
            self.access_token = access_token
            self.registration: VisitRegistration | None = None
            butler_adapter_instances.append(self)

        def fetch_visit_records(
            self, registration: VisitRegistration
        ) -> ButlerVisitRecords:
            self.registration = registration
            visit = make_visit_upsert()
            detectors = [
                make_visit_detector_upsert(),
                make_visit_detector_upsert(
                    detectorId=SECOND_DETECTOR_ID,
                    detector=SECOND_DETECTOR_ID,
                    ccdVisitId=CCD_VISIT_ID + 1,
                ),
            ]
            return ButlerVisitRecords(visit=visit, detectors=detectors)

    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(
        make_enrichment_registration(visit=VISIT_ID)
    )
    await store.mark_queued(created.id)
    monkeypatch.setattr(enrichment, "DaxObsCoreAdapter", FakeDaxObsCoreAdapter)
    monkeypatch.setattr(enrichment, "ButlerAdapter", FakeButlerAdapter)
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
    assert adapter_instances[0].registration == make_enrichment_registration(
        visit=VISIT_ID
    )
    assert len(butler_adapter_instances) == 1
    assert butler_adapter_instances[0].butler_label == config.butler_label
    assert butler_adapter_instances[0].access_token == "worker-token"
    assert butler_adapter_instances[0].registration == (
        make_enrichment_registration(visit=VISIT_ID)
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
    visit = await VisitStore(db_session).get_by_visit_id(INSTRUMENT, VISIT_ID)
    assert visit.visit == VISIT_ID
    assert visit.physical_filter == "r_57"
    detectors = await VisitDetectorStore(db_session).get_by_visit_id(
        INSTRUMENT, VISIT_ID
    )
    assert [detector.detector for detector in detectors] == [
        DETECTOR_ID,
        SECOND_DETECTOR_ID,
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("second_instrument", "second_visit_id"),
    [(INSTRUMENT, VISIT_ID + 1), (SECOND_INSTRUMENT, VISIT_ID)],
)
async def test_enrich_visit_preserves_shared_detector_history(
    app: FastAPI,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    second_instrument: str,
    second_visit_id: int,
) -> None:
    """Test re-enrichment updates just one visit's detector records."""
    observations = {
        (INSTRUMENT, VISIT_ID): ("r", "r_57", 1.8),
        (second_instrument, second_visit_id): ("r", "r_57", 2.0),
    }

    class FakeDaxObsCoreAdapter:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def iter_visit_records(
            self, registration: VisitRegistration
        ) -> Iterator[ObsCoreUpsert]:
            instrument = registration.instrument
            visit_id = registration.visit
            band, physical_filter, _ = observations[instrument, visit_id]
            yield make_obscore_upsert(
                obs_id=f"obscore-{instrument}-{visit_id}",
                instrument_name=instrument,
                lsst_visit=visit_id,
                lsst_band=band,
                lsst_filter=physical_filter,
            )

    class FakeButlerAdapter:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def fetch_visit_records(
            self, registration: VisitRegistration
        ) -> ButlerVisitRecords:
            visit_id = registration.visit
            instrument = registration.instrument
            band, physical_filter, seeing = observations[instrument, visit_id]
            return ButlerVisitRecords(
                visit=make_visit_upsert(
                    instrument=instrument,
                    visitId=visit_id,
                    visit=visit_id,
                    physical_filter=physical_filter,
                    band=band,
                ),
                detectors=[
                    make_visit_detector_upsert(
                        instrument=instrument,
                        visitId=visit_id,
                        ccdVisitId=CCD_VISIT_ID + (visit_id - VISIT_ID),
                        physical_filter=physical_filter,
                        band=band,
                        seeing=seeing,
                    )
                ],
            )

    jobs = EnrichmentJobStore(db_session)
    first_job = await jobs.add_or_get(make_enrichment_registration(VISIT_ID))
    second_job = await jobs.add_or_get(
        make_enrichment_registration(
            second_visit_id, instrument=second_instrument
        )
    )
    monkeypatch.setattr(enrichment, "DaxObsCoreAdapter", FakeDaxObsCoreAdapter)
    monkeypatch.setattr(enrichment, "ButlerAdapter", FakeButlerAdapter)
    context = {
        "labeled_butler_factory": object(),
        "obscore_config": object(),
        "obscore_dataset_type": "preliminary_visit_image",
        "butler_access_token": SecretStr("worker-token"),
    }

    await enrichment.enrich_visit(
        first_job.id, session=db_session, context=context
    )
    await enrichment.enrich_visit(
        second_job.id, session=db_session, context=context
    )
    observations[INSTRUMENT, VISIT_ID] = ("i", "i_39", 1.9)
    await enrichment.enrich_visit(
        first_job.id, session=db_session, context=context
    )

    obscore = await ObsCoreStore(db_session).get_by_obs_id(
        f"obscore-{INSTRUMENT}-{VISIT_ID}"
    )
    assert obscore.lsst_band == "i"
    visit_store = VisitStore(db_session)
    first_visit = await visit_store.get_by_visit_id(INSTRUMENT, VISIT_ID)
    second_visit = await visit_store.get_by_visit_id(
        second_instrument, second_visit_id
    )
    assert first_visit.band == "i"
    assert second_visit.band == "r"
    detector_store = VisitDetectorStore(db_session)
    first = await detector_store.get_by_visit_id(INSTRUMENT, VISIT_ID)
    second = await detector_store.get_by_visit_id(
        second_instrument, second_visit_id
    )
    assert len(first) == len(second) == 1
    assert first[0].detectorId == second[0].detectorId == DETECTOR_ID
    assert first[0].seeing == pytest.approx(1.9)
    assert second[0].seeing == pytest.approx(2.0)

    observations[second_instrument, second_visit_id] = ("g", "g_01", 2.1)
    await enrichment.enrich_visit(
        second_job.id, session=db_session, context=context
    )
    first = await detector_store.get_by_visit_id(INSTRUMENT, VISIT_ID)
    second = await detector_store.get_by_visit_id(
        second_instrument, second_visit_id
    )
    assert len(first) == len(second) == 1
    assert first[0].seeing == pytest.approx(1.9)
    assert second[0].seeing == pytest.approx(2.1)


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
    created = await store.add_or_get(
        make_visit_registration(visit=20260327654321)
    )
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
    created = await store.add_or_get(
        make_visit_registration(visit=20260327654321)
    )
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
    created = await store.add_or_get(
        make_visit_registration(visit=20260327654321)
    )
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
@pytest.mark.parametrize(
    ("detector_visit_id", "detector_instrument", "error_type"),
    [
        (VISIT_ID + 1, INSTRUMENT, VisitNotFoundInDatasetError),
        (VISIT_ID, None, ButlerDatasetInstrumentError),
        (VISIT_ID, SECOND_INSTRUMENT, ButlerDatasetInstrumentError),
    ],
)
async def test_invalid_visit_dataset_fails_before_writes(
    app: FastAPI,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    *,
    detector_visit_id: int,
    detector_instrument: str | None,
    error_type: type[ValueError],
) -> None:
    """Test table validation completes before any database upsert."""

    class FakeDaxObsCoreAdapter:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def iter_visit_records(
            self, registration: VisitRegistration
        ) -> Iterator[ObsCoreUpsert]:
            yield make_obscore_upsert(
                obs_id=str(registration.datasets[0].id),
                lsst_visit=registration.visit,
            )

    registration = make_enrichment_registration(VISIT_ID)
    _, visit_dataset, detector_dataset = registration.datasets
    butler = FakeButler(
        {
            visit_dataset.id: ("visit_table", make_visit_table()),
            detector_dataset.id: (
                "visit_detector_table",
                make_visit_detector_table(
                    rows=[{"visitId": detector_visit_id}]
                ),
            ),
        },
        instruments={detector_dataset.id: detector_instrument},
    )
    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(registration)
    await store.mark_queued(created.id)
    monkeypatch.setattr(enrichment, "DaxObsCoreAdapter", FakeDaxObsCoreAdapter)
    with pytest.raises(error_type) as exc_info:
        await enrichment.run_enrichment(
            {
                "logger": structlog.get_logger("test"),
                "labeled_butler_factory": FakeButlerFactory(butler),
                "obscore_config": object(),
                "obscore_dataset_type": "preliminary_visit_image",
                "butler_access_token": SecretStr("worker-token"),
            },
            created.id,
        )

    seen = await store.get(created.id)
    assert seen.phase == EnrichmentJobPhase.ERROR
    assert seen.error_code == error_type.__name__
    assert seen.error_message == str(exc_info.value)
    with pytest.raises(UnknownVisitRecordError):
        await VisitStore(db_session).get_by_visit_id(INSTRUMENT, VISIT_ID)
    assert (
        await VisitDetectorStore(db_session).get_by_visit_id(
            INSTRUMENT, VISIT_ID
        )
        == []
    )
    with pytest.raises(UnknownObsCoreRecordError):
        await ObsCoreStore(db_session).get_by_obs_id(
            str(registration.datasets[0].id)
        )


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
            yield make_obscore_upsert(
                obs_id=dataset_id, lsst_visit=registration.visit
            )
            yield make_obscore_upsert(
                obs_id=dataset_id, lsst_visit=registration.visit
            )

    class FakeButlerAdapter:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def fetch_visit_records(
            self, registration: VisitRegistration
        ) -> ButlerVisitRecords:
            return ButlerVisitRecords(
                visit=make_visit_upsert(),
                detectors=[make_visit_detector_upsert()],
            )

    store = EnrichmentJobStore(db_session)
    created = await store.add_or_get(
        make_enrichment_registration(visit=VISIT_ID)
    )
    await store.mark_queued(created.id)
    monkeypatch.setattr(enrichment, "DaxObsCoreAdapter", FakeDaxObsCoreAdapter)
    monkeypatch.setattr(enrichment, "ButlerAdapter", FakeButlerAdapter)

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
    created = await store.add_or_get(
        make_visit_registration(visit=20260327123456)
    )
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
    created = await store.add_or_get(
        make_visit_registration(visit=20260327123456)
    )
    await store.mark_queued(created.id)
    monkeypatch.setattr(enrichment, "enrich_visit", retry)

    with capture_logs() as logs:
        with pytest.raises(
            enrichment.EnrichmentRetriesExhaustedError,
            match="retries exhausted",
        ):
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
