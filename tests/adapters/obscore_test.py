"""Tests for the dax_obscore adapter."""

from collections.abc import Iterable, Iterator
from typing import Any, ClassVar, cast

import pytest
from lsst.daf.butler import LabeledButlerFactory
from lsst.dax.obscore import ExporterConfig

import obsforge.adapters.obscore as obscore_adapter
from obsforge.adapters import DaxObsCoreAdapter, MissingObsCoreDatasetError
from obsforge.models import ObsCoreUpsert
from tests.support.obscore import (
    DATASET_ID,
    SECOND_DATASET_ID,
    make_obscore_row,
)
from tests.support.registration import make_visit_registration


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
    registration = make_visit_registration(
        datasets=[
            {
                "dataset_type": "difference_image",
                "id": "019ba0a5-fe56-7fe8-b6c3-82991b2633c0",
            },
            {
                "dataset_type": "preliminary_visit_image",
                "id": DATASET_ID,
            },
            {
                "dataset_type": "preliminary_visit_image",
                "id": SECOND_DATASET_ID,
            },
        ]
    )

    records = list(adapter.iter_visit_records(registration))

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
    registration = make_visit_registration(
        datasets=[
            {
                "dataset_type": "difference_image",
                "id": "019ba0a5-fe56-7fe8-b6c3-82991b2633c0",
            }
        ]
    )

    with pytest.raises(
        MissingObsCoreDatasetError, match="preliminary_visit_image"
    ) as exc_info:
        list(adapter.iter_visit_records(registration))

    assert exc_info.value.dataset_type == "preliminary_visit_image"
    assert factory.labels == []
    assert factory.access_tokens == []
    assert config.copied_with_deep is None
    assert FakeObscoreExporter.instances == []
