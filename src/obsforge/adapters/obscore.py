"""Adapter for retrieving ObsCore records from `lsst.dax.obscore`."""

from collections.abc import Iterator
from typing import Any, Protocol, cast

from lsst.daf.butler import LabeledButlerFactory
from lsst.dax.obscore import ExporterConfig, ObscoreExporter
from lsst.dax.obscore.config import WhereBind

from obsforge.models import ObsCoreUpsert, VisitRegistration

__all__ = ["DaxObsCoreAdapter"]


class _RecordExporter(Protocol):
    """Public row-oriented `ObscoreExporter` API used by ObsForge."""

    def iter_records(self) -> Iterator[dict[str, Any]]:
        """Iterate over ObsCore record dictionaries."""


class DaxObsCoreAdapter:
    """Retrieve ObsCore records for registered visit datasets."""

    def __init__(
        self,
        *,
        butler_factory: LabeledButlerFactory,
        butler_label: str,
        config: ExporterConfig,
        dataset_type: str,
    ) -> None:
        self._butler_factory = butler_factory
        self._butler_label = butler_label
        self._config = config
        self._dataset_type = dataset_type

    def iter_visit_records(
        self, registration: VisitRegistration
    ) -> Iterator[ObsCoreUpsert]:
        """Iterate over ObsCore records for matching visit datasets."""
        dataset_ids = [
            dataset.id
            for dataset in registration.datasets
            if dataset.dataset_type == self._dataset_type
        ]
        if not dataset_ids:
            raise ValueError(
                "Registration payload does not include "
                f"{self._dataset_type} datasets"
            )

        cfg = self._config.model_copy(deep=True)
        cfg.select_dataset_types([self._dataset_type])
        cfg.dataset_type_constraints = {
            self._dataset_type: [
                WhereBind(
                    where="dataset_id IN (:dataset_ids)",
                    bind={"dataset_ids": dataset_ids},
                )
            ]
        }

        butler = self._butler_factory.create_butler(label=self._butler_label)
        exporter = ObscoreExporter(butler, cfg)
        if not hasattr(exporter, "iter_records"):
            raise RuntimeError(
                "lsst.dax.obscore ObscoreExporter.iter_records is required"
            )
        record_exporter = cast("_RecordExporter", exporter)
        for record in record_exporter.iter_records():
            yield ObsCoreUpsert.model_validate(record)
