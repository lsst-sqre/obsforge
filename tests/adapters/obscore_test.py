"""Tests for the dax_obscore adapter."""

from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import Any, ClassVar, cast
from uuid import UUID

import pytest
from lsst.daf.butler import LabeledButlerFactory
from lsst.dax.obscore import ExporterConfig

import obsforge.adapters.obscore as obscore_adapter
from obsforge.adapters import DaxObsCoreAdapter
from obsforge.models import ObsCoreUpsert, VisitRegistration

DATASET_ID = UUID("019ba0a6-0173-765f-bf27-56884ff9342a")
SECOND_DATASET_ID = UUID("019ba0a5-fe48-7c7a-8c3f-540057f026c3")


class FakeDatasetTypeConfig:
    """Small stand-in for per-dataset ObsCore configuration."""

    def __init__(self, *, obs_id_fmt: str) -> None:
        self.obs_id_fmt = obs_id_fmt


class FakeExporterConfig:
    """Small stand-in for `ExporterConfig` query mutation behavior."""

    def __init__(self) -> None:
        self.copied_with_deep: bool | None = None
        self.copy: FakeExporterConfig | None = None
        self.selected_dataset_types: list[str] = []
        self.dataset_types = {
            "preliminary_visit_image": FakeDatasetTypeConfig(
                obs_id_fmt="{records[visit].name}"
            ),
            "difference_image": FakeDatasetTypeConfig(
                obs_id_fmt="{records[visit].name}"
            ),
        }
        self.dataset_type_constraints: dict[str, list[Any]] = {}

    def model_copy(self, *, deep: bool = False) -> FakeExporterConfig:
        self.copied_with_deep = deep
        self.copy = FakeExporterConfig()
        self.copy.dataset_types = {
            key: FakeDatasetTypeConfig(obs_id_fmt=value.obs_id_fmt)
            for key, value in self.dataset_types.items()
        }
        return self.copy

    def select_dataset_types(self, dataset_types: Iterable[str]) -> None:
        self.selected_dataset_types = list(dataset_types)
        dataset_type_set = set(dataset_types)
        self.dataset_types = {
            key: value
            for key, value in self.dataset_types.items()
            if key in dataset_type_set
        }


class FakeButlerFactory:
    """Small stand-in for `LabeledButlerFactory`."""

    def __init__(self) -> None:
        self.labels: list[str] = []
        self.access_tokens: list[str | None] = []

    def create_butler(
        self, *, label: str, access_token: str | None = None
    ) -> str:
        self.labels.append(label)
        self.access_tokens.append(access_token)
        return "butler"


class FakeObscoreExporter:
    """Small stand-in for `ObscoreExporter`."""

    rows: ClassVar[list[dict[str, Any]]] = []
    instances: ClassVar[list[FakeObscoreExporter]] = []

    def __init__(self, butler: Any, config: Any) -> None:
        self.butler = butler
        self.config = config
        self.instances.append(self)

    def iter_records(self) -> Iterator[dict[str, Any]]:
        yield from self.rows


def make_registration(
    *, include_matching_dataset: bool = True
) -> VisitRegistration:
    datasets = [
        {
            "dataset_type": "difference_image",
            "id": "019ba0a5-fe56-7fe8-b6c3-82991b2633c0",
        }
    ]
    if include_matching_dataset:
        datasets.extend(
            [
                {
                    "dataset_type": "preliminary_visit_image",
                    "id": str(DATASET_ID),
                },
                {
                    "dataset_type": "preliminary_visit_image",
                    "id": str(SECOND_DATASET_ID),
                },
            ]
        )
    return VisitRegistration.model_validate(
        {
            "instrument": "LSSTCam",
            "day_obs": 20260108,
            "visit": 2026010800095,
            "datasets": datasets,
            "timespan": {
                "begin": datetime(2026, 1, 9, 2, 45, 51, tzinfo=UTC),
                "end": datetime(2026, 1, 9, 2, 46, 26, tzinfo=UTC),
            },
        }
    )


def make_obscore_row() -> dict[str, Any]:
    return {
        "dataproduct_type": "image",
        "dataproduct_subtype": "lsst.preliminary_visit_image",
        "calib_level": 2,
        "target_name": None,
        "obs_id": str(DATASET_ID),
        "obs_collection": "LSST.Prompt",
        "obs_publisher_did": (
            f"ivo://org.rubinobs/usdac/lsst-prompt?repo=prompt&id={DATASET_ID}"
        ),
        "access_url": (
            "https://data.lsst.cloud/api/datalink/links?ID="
            "ivo%3A%2F%2Forg.rubinobs%2Flsst-prompt"
            f"%3Frepo%3Dprompt%26id%3D{DATASET_ID}"
        ),
        "access_format": "application/x-votable+xml;content=datalink",
        "s_ra": 12.34,
        "s_dec": -45.6,
        "s_fov": 0.1,
        "s_region": "POLYGON ICRS 1 2 3 4 5 6",
        "s_resolution": None,
        "s_xel1": 4072,
        "s_xel2": 4000,
        "t_xel": None,
        "t_min": 61048.115182,
        "t_max": 61048.115587,
        "t_exptime": 35.0,
        "t_resolution": None,
        "em_xel": None,
        "em_min": 402.6e-9,
        "em_max": 548.3e-9,
        "em_res_power": None,
        "o_ucd": "phot.flux.density",
        "pol_xel": None,
        "instrument_name": "LSSTCam",
        "facility_name": "Rubin:Simonyi",
        "obs_title": (
            "preliminary_visit_image - g - "
            "MC_O_20260108_000095-R30_S22 2026-01-09T02:45:51Z"
        ),
        "em_filter_name": "g",
        "lsst_visit": 2026010800095,
        "lsst_detector": 122,
        "lsst_filter": "g_6",
        "lsst_band": "g",
        "lsst_patch": None,
        "lsst_tract": None,
    }


def make_adapter(
    config: FakeExporterConfig,
    factory: FakeButlerFactory,
    *,
    access_token: str = "worker-token",
) -> DaxObsCoreAdapter:
    return DaxObsCoreAdapter(
        butler_factory=cast("LabeledButlerFactory", factory),
        butler_label="prompt",
        config=cast("ExporterConfig", config),
        dataset_type="preliminary_visit_image",
        access_token=access_token,
    )


def test_iter_visit_records_constrains_exporter_by_matching_dataset_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeObscoreExporter.rows = [make_obscore_row()]
    FakeObscoreExporter.instances = []
    monkeypatch.setattr(
        obscore_adapter, "ObscoreExporter", FakeObscoreExporter
    )
    config = FakeExporterConfig()
    factory = FakeButlerFactory()
    adapter = make_adapter(config, factory, access_token="worker-token")

    records = list(adapter.iter_visit_records(make_registration()))

    assert records == [ObsCoreUpsert.model_validate(make_obscore_row())]
    assert factory.labels == ["prompt"]
    assert factory.access_tokens == ["worker-token"]
    assert config.copied_with_deep is True
    assert config.dataset_type_constraints == {}
    assert (
        config.dataset_types["preliminary_visit_image"].obs_id_fmt
        == "{records[visit].name}"
    )
    assert config.copy is not None
    assert config.copy.selected_dataset_types == ["preliminary_visit_image"]
    assert config.copy.dataset_types["preliminary_visit_image"].obs_id_fmt == (
        "{id}"
    )
    assert "difference_image" not in config.copy.dataset_types
    where_bind = config.copy.dataset_type_constraints[
        "preliminary_visit_image"
    ][0]
    assert where_bind.where == "dataset_id IN (:dataset_ids)"
    assert where_bind.bind == {"dataset_ids": [DATASET_ID, SECOND_DATASET_ID]}
    exporter = FakeObscoreExporter.instances[0]
    assert exporter.butler == "butler"
    assert exporter.config is config.copy


def test_iter_visit_records_rejects_missing_matching_dataset_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeObscoreExporter.instances = []
    monkeypatch.setattr(
        obscore_adapter, "ObscoreExporter", FakeObscoreExporter
    )
    config = FakeExporterConfig()
    factory = FakeButlerFactory()
    adapter = make_adapter(config, factory)

    with pytest.raises(ValueError, match="preliminary_visit_image"):
        list(
            adapter.iter_visit_records(
                make_registration(include_matching_dataset=False)
            )
        )

    assert factory.labels == []
    assert factory.access_tokens == []
    assert config.copied_with_deep is None
    assert FakeObscoreExporter.instances == []
