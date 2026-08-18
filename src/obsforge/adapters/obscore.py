"""Adapter for retrieving ObsCore records from `lsst.dax.obscore`."""

from collections.abc import Iterator

from lsst.daf.butler import LabeledButlerFactory
from lsst.dax.obscore import ExporterConfig, ObscoreExporter
from lsst.dax.obscore.config import WhereBind

from obsforge.models import ObsCoreUpsert, VisitRegistration

__all__ = ["DaxObsCoreAdapter", "MissingObsCoreDatasetError"]


class MissingObsCoreDatasetError(ValueError):
    """Raised when a registration has no datasets for ObsCore export."""

    def __init__(self, dataset_type: str) -> None:
        super().__init__(
            f"Registration payload does not include {dataset_type} datasets"
        )
        self.dataset_type = dataset_type


class DaxObsCoreAdapter:
    """Retrieve ObsCore records for registered visit datasets."""

    def __init__(
        self,
        *,
        butler_factory: LabeledButlerFactory,
        butler_label: str,
        config: ExporterConfig,
        dataset_type: str,
        access_token: str,
    ) -> None:
        self._butler_factory = butler_factory
        self._butler_label = butler_label
        self._config = config
        self._dataset_type = dataset_type
        self._access_token = access_token

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
            raise MissingObsCoreDatasetError(self._dataset_type)

        cfg = self._config.model_copy(deep=True)
        cfg.select_dataset_types([self._dataset_type])
        # Use the globally unique Butler dataset UUID as `obs_id`.
        cfg.dataset_types[self._dataset_type].obs_id_fmt = "{id}"
        cfg.dataset_type_constraints = {
            self._dataset_type: [
                WhereBind(
                    where="dataset_id IN (:dataset_ids)",
                    bind={"dataset_ids": dataset_ids},
                )
            ]
        }

        butler = self._butler_factory.create_butler(
            label=self._butler_label,
            access_token=self._access_token,
        )
        exporter = ObscoreExporter(butler, cfg)
        for record in exporter.iter_records():
            yield ObsCoreUpsert.model_validate(record)
