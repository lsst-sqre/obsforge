"""Adapter for retrieving Visit records from the Prompt Butler."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import numpy as np
from astropy.table import Table
from lsst.daf.butler import Butler, LabeledButlerFactory

from obsforge.models import VisitDetectorUpsert, VisitRegistration, VisitUpsert

__all__ = [
    "ButlerAdapter",
    "ButlerDatasetCardinalityError",
    "ButlerDatasetNotFoundError",
    "ButlerDatasetTypeError",
    "ButlerVisitRecords",
    "DuplicateVisitDetectorRowsError",
    "DuplicateVisitRowsError",
    "InvalidButlerTableError",
    "VisitNotFoundInDatasetError",
]

_VISIT_DATASET_TYPE = "visit_table"
_VISIT_DETECTOR_DATASET_TYPE = "visit_detector_table"


class ButlerDatasetCardinalityError(ValueError):
    """Raised when a registration does not contain one expected dataset."""

    def __init__(self, dataset_type: str, count: int) -> None:
        msg = (
            f"Registration payload must include exactly one {dataset_type} "
            f"dataset; found {count}"
        )
        super().__init__(msg)
        self.dataset_type = dataset_type
        self.count = count


class ButlerDatasetNotFoundError(ValueError):
    """Raised when a registered dataset UUID is unknown to the Butler."""

    def __init__(self, dataset_id: UUID) -> None:
        super().__init__(f"Butler dataset {dataset_id} was not found")
        self.dataset_id = dataset_id


class ButlerDatasetTypeError(ValueError):
    """Raised when a registered UUID has an unexpected dataset type."""

    def __init__(
        self, dataset_id: UUID, *, expected: str, actual: str
    ) -> None:
        msg = (
            f"Butler dataset {dataset_id} has type {actual!r}; "
            f"expected {expected!r}"
        )
        super().__init__(msg)
        self.dataset_id = dataset_id
        self.expected = expected
        self.actual = actual


class InvalidButlerTableError(ValueError):
    """Raised when a Butler dataset is not a valid Visit table."""

    def __init__(self, dataset_type: str, reason: str) -> None:
        super().__init__(f"Invalid {dataset_type} dataset: {reason}")
        self.dataset_type = dataset_type
        self.reason = reason


class VisitNotFoundInDatasetError(ValueError):
    """Raised when a dataset has no rows for the registered visit."""

    def __init__(self, visit: int, dataset_type: str) -> None:
        msg = f"Visit {visit} not found in {dataset_type} dataset"
        super().__init__(msg)
        self.visit = visit
        self.dataset_type = dataset_type


class DuplicateVisitRowsError(ValueError):
    """Raised when visit_table has multiple rows for one visit."""

    def __init__(self, visit: int, count: int) -> None:
        super().__init__(
            f"Visit {visit} has {count} rows in visit_table dataset"
        )
        self.visit = visit
        self.count = count


class DuplicateVisitDetectorRowsError(ValueError):
    """Raised when detector rows contain duplicate database identities."""

    def __init__(self, visit: int) -> None:
        super().__init__(
            f"Visit {visit} has duplicate detector identities in "
            "visit_detector_table dataset"
        )
        self.visit = visit


@dataclass(frozen=True)
class ButlerVisitRecords:
    """Visit and detector records retrieved from Butler datasets."""

    visit: VisitUpsert
    detectors: list[VisitDetectorUpsert]


class ButlerAdapter:
    """Retrieve Visit and VisitDetector records from the Prompt Butler."""

    def __init__(
        self,
        *,
        butler_factory: LabeledButlerFactory,
        butler_label: str,
        access_token: str,
    ) -> None:
        self._butler_factory = butler_factory
        self._butler_label = butler_label
        self._access_token = access_token

    def fetch_visit_records(
        self, registration: VisitRegistration
    ) -> ButlerVisitRecords:
        """Retrieve rows matching one registered visit."""
        visit_dataset_id = self._get_registered_dataset_id(
            registration, _VISIT_DATASET_TYPE
        )
        detector_dataset_id = self._get_registered_dataset_id(
            registration, _VISIT_DETECTOR_DATASET_TYPE
        )
        butler = self._butler_factory.create_butler(
            label=self._butler_label,
            access_token=self._access_token,
        )
        visit_table = self._get_table(
            butler, visit_dataset_id, _VISIT_DATASET_TYPE
        )
        detector_table = self._get_table(
            butler, detector_dataset_id, _VISIT_DETECTOR_DATASET_TYPE
        )
        visit = self._get_visit(visit_table, registration.visit)
        detectors = self._get_visit_detectors(
            detector_table, registration.visit
        )
        return ButlerVisitRecords(visit=visit, detectors=detectors)

    def _get_registered_dataset_id(
        self, registration: VisitRegistration, dataset_type: str
    ) -> UUID:
        dataset_ids = [
            dataset.id
            for dataset in registration.datasets
            if dataset.dataset_type == dataset_type
        ]
        if len(dataset_ids) != 1:
            raise ButlerDatasetCardinalityError(dataset_type, len(dataset_ids))
        return dataset_ids[0]

    def _get_table(
        self, butler: Butler, dataset_id: UUID, dataset_type: str
    ) -> Table:
        ref = butler.get_dataset(dataset_id)
        if ref is None:
            raise ButlerDatasetNotFoundError(dataset_id)
        actual_type = ref.datasetType.name
        if actual_type != dataset_type:
            raise ButlerDatasetTypeError(
                dataset_id, expected=dataset_type, actual=actual_type
            )
        table = butler.get(ref)
        if not isinstance(table, Table):
            raise InvalidButlerTableError(
                dataset_type,
                f"expected astropy.table.Table, got {type(table).__name__}",
            )
        if "visitId" not in table.colnames:
            raise InvalidButlerTableError(
                dataset_type, "missing visitId column"
            )
        return table

    def _get_visit(self, table: Table, visit: int) -> VisitUpsert:
        rows = self._matching_rows(table, visit, _VISIT_DATASET_TYPE)
        if len(rows) == 0:
            raise VisitNotFoundInDatasetError(visit, _VISIT_DATASET_TYPE)
        if len(rows) != 1:
            raise DuplicateVisitRowsError(visit, len(rows))
        try:
            return VisitUpsert.model_validate(self._row_to_dict(rows, 0))
        except (TypeError, ValueError, OverflowError) as e:
            raise InvalidButlerTableError(_VISIT_DATASET_TYPE, str(e)) from e

    def _get_visit_detectors(
        self, table: Table, visit: int
    ) -> list[VisitDetectorUpsert]:
        rows = self._matching_rows(table, visit, _VISIT_DETECTOR_DATASET_TYPE)
        if len(rows) == 0:
            raise VisitNotFoundInDatasetError(
                visit, _VISIT_DETECTOR_DATASET_TYPE
            )
        try:
            records = [
                VisitDetectorUpsert.model_validate(
                    self._row_to_dict(rows, index)
                )
                for index in range(len(rows))
            ]
        except (TypeError, ValueError, OverflowError) as e:
            raise InvalidButlerTableError(
                _VISIT_DETECTOR_DATASET_TYPE, str(e)
            ) from e

        detector_keys = {
            (record.visitId, record.detectorId) for record in records
        }
        if len(detector_keys) != len(records):
            raise DuplicateVisitDetectorRowsError(visit)
        return records

    def _matching_rows(
        self, table: Table, visit: int, dataset_type: str
    ) -> Table:
        try:
            return table[table["visitId"] == visit]
        except (IndexError, TypeError, ValueError) as e:
            raise InvalidButlerTableError(
                dataset_type, f"could not filter visitId rows: {e}"
            ) from e

    def _row_to_dict(self, table: Table, index: int) -> dict[str, Any]:
        return {
            name: self._normalize_value(table[name][index])
            for name in table.colnames
        }

    def _normalize_value(self, value: Any) -> Any:
        if np.ma.is_masked(value):
            return None
        if isinstance(value, np.datetime64):
            if np.isnat(value):
                return None
            converted = value.astype("datetime64[us]").item()
            if not isinstance(converted, datetime):
                raise TypeError(
                    "NumPy datetime conversion did not return datetime"
                )
            return converted
        if isinstance(value, np.generic):
            return value.item()
        return value
