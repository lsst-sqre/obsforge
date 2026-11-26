"""Tests for the Prompt Butler Visit adapter."""

import math
from typing import Any, cast
from uuid import UUID

import numpy as np
import pytest
from astropy.table import MaskedColumn, Table
from lsst.daf.butler import LabeledButlerFactory

from obsforge.adapters import (
    ButlerAdapter,
    ButlerDatasetCardinalityError,
    ButlerDatasetNotFoundError,
    ButlerDatasetTypeError,
    DuplicateVisitDetectorRowsError,
    DuplicateVisitRowsError,
    InvalidButlerTableError,
    VisitNotFoundInDatasetError,
)
from obsforge.models import VisitDetectorUpsert, VisitUpsert
from tests.support.registration import make_visit_registration
from tests.support.visit import (
    CCD_VISIT_ID,
    DETECTOR_ID,
    SECOND_DETECTOR_ID,
    VISIT_ID,
    make_visit_detector_table,
    make_visit_table,
)

VISIT_DATASET_ID = UUID("01a1b340-154e-7fce-b26c-b671f660788f")
DETECTOR_DATASET_ID = UUID("01a1b340-154e-7fce-b26c-b671f6607890")


class FakeDatasetType:
    """Minimal Butler dataset type."""

    def __init__(self, name: str) -> None:
        self.name = name


class FakeDatasetRef:
    """Minimal Butler dataset reference."""

    def __init__(self, dataset_id: UUID, dataset_type: str) -> None:
        self.id = dataset_id
        self.datasetType = FakeDatasetType(dataset_type)


class FakeButler:
    """In-memory Butler test double."""

    def __init__(self, datasets: dict[UUID, tuple[str, Any]]) -> None:
        self.datasets = datasets
        self.requested_ids: list[UUID] = []
        self.requested_refs: list[FakeDatasetRef] = []

    def get_dataset(self, dataset_id: UUID) -> FakeDatasetRef | None:
        self.requested_ids.append(dataset_id)
        entry = self.datasets.get(dataset_id)
        if entry is None:
            return None
        return FakeDatasetRef(dataset_id, entry[0])

    def get(self, ref: FakeDatasetRef) -> Any:
        self.requested_refs.append(ref)
        return self.datasets[ref.id][1]


class FakeButlerFactory:
    """Factory that returns one configured fake Butler."""

    def __init__(self, butler: FakeButler) -> None:
        self.butler = butler
        self.calls: list[tuple[str, str | None]] = []

    def create_butler(
        self, *, label: str, access_token: str | None = None
    ) -> FakeButler:
        self.calls.append((label, access_token))
        return self.butler


def make_registration() -> Any:
    """Make a registration with both required table datasets."""
    return make_visit_registration(
        visit=VISIT_ID,
        datasets=[
            {"dataset_type": "visit_table", "id": VISIT_DATASET_ID},
            {
                "dataset_type": "visit_detector_table",
                "id": DETECTOR_DATASET_ID,
            },
        ],
    )


def make_adapter(
    datasets: dict[UUID, tuple[str, Any]],
) -> tuple[ButlerAdapter, FakeButler, FakeButlerFactory]:
    """Make an adapter and its fakes."""
    butler = FakeButler(datasets)
    factory = FakeButlerFactory(butler)
    adapter = ButlerAdapter(
        butler_factory=cast("LabeledButlerFactory", factory),
        butler_label="prompt",
        access_token="worker-token",
    )
    return adapter, butler, factory


def test_realistic_tables_have_all_columns_and_dtypes() -> None:
    visit_table = make_visit_table()
    detector_table = make_visit_detector_table()

    assert visit_table.colnames == list(VisitUpsert.model_fields)
    assert detector_table.colnames == list(VisitDetectorUpsert.model_fields)
    assert visit_table["visitId"].dtype == np.dtype("int64")
    assert visit_table["physical_filter"].dtype == np.dtype("U4")
    assert visit_table["ra"].dtype == np.dtype("float64")
    assert visit_table["expMidpt"].dtype == np.dtype("datetime64[ns]")
    assert visit_table["expMidpt"][0] == np.datetime64(
        "2026-11-05T04:40:22.317658362", "ns"
    )
    assert detector_table["detectorId"].dtype == np.dtype("int64")
    assert detector_table["nShapeletsStar"].dtype == np.dtype("int32")
    assert detector_table["pixelScale"].dtype == np.dtype("float32")
    assert detector_table["decl"].dtype == np.dtype("float64")
    assert detector_table["physical_filter"].dtype == np.dtype("U32")
    assert detector_table["obsStart"].dtype == np.dtype("datetime64[ns]")


def test_fetch_visit_records() -> None:
    adapter, butler, factory = make_adapter(
        {
            VISIT_DATASET_ID: (
                "visit_table",
                make_visit_table(rows=[{"visitId": 123, "visit": 123}, {}]),
            ),
            DETECTOR_DATASET_ID: (
                "visit_detector_table",
                make_visit_detector_table(
                    rows=[
                        {
                            "visitId": 123,
                            "ccdVisitId": CCD_VISIT_ID - 1,
                        },
                        {},
                        {
                            "detectorId": SECOND_DETECTOR_ID,
                            "ccdVisitId": CCD_VISIT_ID + 1,
                        },
                    ]
                ),
            ),
        }
    )

    records = adapter.fetch_visit_records(make_registration())

    assert records.visit.visitId == VISIT_ID
    assert records.visit.expMidpt is not None
    assert records.visit.expMidpt.microsecond == 317658
    assert records.visit.obsStart is not None
    assert records.visit.obsStart.microsecond == 317396
    assert records.visit.physical_filter == "r_57"
    assert records.visit.skyRotation == pytest.approx(203.302231459618)
    assert [record.detectorId for record in records.detectors] == [
        DETECTOR_ID,
        SECOND_DETECTOR_ID,
    ]
    assert [record.detector for record in records.detectors] == [
        DETECTOR_ID,
        DETECTOR_ID,
    ]
    assert isinstance(records.visit.visitId, int)
    assert isinstance(records.detectors[0].pixelScale, float)
    assert records.detectors[0].pixelScale == pytest.approx(
        0.20009875297546387
    )
    assert records.detectors[0].nShapeletsStar == 20
    assert records.detectors[0].ccdVisitId == CCD_VISIT_ID
    assert records.detectors[0].xSize == 4095
    assert records.detectors[0].starComa1Median is not None
    assert math.isnan(records.detectors[0].starComa1Median)
    assert factory.calls == [("prompt", "worker-token")]
    assert butler.requested_ids == [VISIT_DATASET_ID, DETECTOR_DATASET_ID]


def test_normalizes_masked_values_and_nat() -> None:
    visit_table = make_visit_table()
    visit_table["physical_filter"] = MaskedColumn(
        visit_table["physical_filter"], mask=[True]
    )
    visit_table["obsStart"][0] = np.datetime64("NaT", "ns")
    detector_table = make_visit_detector_table()
    detector_table["zeroPoint"] = MaskedColumn(
        detector_table["zeroPoint"], mask=[True]
    )
    adapter, _, _ = make_adapter(
        {
            VISIT_DATASET_ID: ("visit_table", visit_table),
            DETECTOR_DATASET_ID: (
                "visit_detector_table",
                detector_table,
            ),
        }
    )

    records = adapter.fetch_visit_records(make_registration())

    assert records.visit.physical_filter is None
    assert records.visit.obsStart is None
    assert records.detectors[0].zeroPoint is None


@pytest.mark.parametrize(
    "dataset_type", ["visit_table", "visit_detector_table"]
)
def test_rejects_missing_or_multiple_registered_datasets(
    dataset_type: str,
) -> None:
    datasets = [
        {"dataset_type": "visit_table", "id": VISIT_DATASET_ID},
        {
            "dataset_type": "visit_detector_table",
            "id": DETECTOR_DATASET_ID,
        },
    ]
    datasets = [
        entry for entry in datasets if entry["dataset_type"] != dataset_type
    ]
    adapter, _, factory = make_adapter({})
    with pytest.raises(ButlerDatasetCardinalityError) as exc_info:
        adapter.fetch_visit_records(
            make_visit_registration(visit=VISIT_ID, datasets=datasets)
        )
    assert exc_info.value.dataset_type == dataset_type
    assert factory.calls == []

    duplicate = [*datasets]
    duplicate.extend(
        [
            {"dataset_type": dataset_type, "id": VISIT_DATASET_ID},
            {"dataset_type": dataset_type, "id": DETECTOR_DATASET_ID},
        ]
    )
    with pytest.raises(ButlerDatasetCardinalityError):
        adapter.fetch_visit_records(
            make_visit_registration(visit=VISIT_ID, datasets=duplicate)
        )


def test_rejects_unknown_dataset_uuid() -> None:
    adapter, _, _ = make_adapter({})
    with pytest.raises(ButlerDatasetNotFoundError) as exc_info:
        adapter.fetch_visit_records(make_registration())
    assert exc_info.value.dataset_id == VISIT_DATASET_ID


def test_rejects_wrong_dataset_type() -> None:
    adapter, _, _ = make_adapter(
        {VISIT_DATASET_ID: ("wrong_type", make_visit_table())}
    )
    with pytest.raises(ButlerDatasetTypeError, match="wrong_type"):
        adapter.fetch_visit_records(make_registration())


@pytest.mark.parametrize("value", [object(), Table({"visit": [VISIT_ID]})])
def test_rejects_invalid_table(value: Any) -> None:
    adapter, _, _ = make_adapter({VISIT_DATASET_ID: ("visit_table", value)})
    with pytest.raises(InvalidButlerTableError):
        adapter.fetch_visit_records(make_registration())


@pytest.mark.parametrize(
    "dataset_type", ["visit_table", "visit_detector_table"]
)
def test_rejects_missing_visit_in_either_table(dataset_type: str) -> None:
    visit_table = make_visit_table()
    detector_table = make_visit_detector_table()
    if dataset_type == "visit_table":
        visit_table = make_visit_table(rows=[{"visitId": 123, "visit": 123}])
    else:
        detector_table = make_visit_detector_table(rows=[{"visitId": 123}])
    adapter, _, _ = make_adapter(
        {
            VISIT_DATASET_ID: ("visit_table", visit_table),
            DETECTOR_DATASET_ID: (
                "visit_detector_table",
                detector_table,
            ),
        }
    )
    with pytest.raises(VisitNotFoundInDatasetError) as exc_info:
        adapter.fetch_visit_records(make_registration())
    assert exc_info.value.dataset_type == dataset_type


def test_rejects_duplicate_visit_rows() -> None:
    adapter, _, _ = make_adapter(
        {
            VISIT_DATASET_ID: (
                "visit_table",
                make_visit_table(rows=[{}, {}]),
            ),
            DETECTOR_DATASET_ID: (
                "visit_detector_table",
                make_visit_detector_table(),
            ),
        }
    )
    with pytest.raises(DuplicateVisitRowsError):
        adapter.fetch_visit_records(make_registration())


def test_rejects_duplicate_visit_detector_id_keys() -> None:
    table = make_visit_detector_table(
        rows=[{}, {"detector": SECOND_DETECTOR_ID}]
    )
    adapter, _, _ = make_adapter(
        {
            VISIT_DATASET_ID: ("visit_table", make_visit_table()),
            DETECTOR_DATASET_ID: ("visit_detector_table", table),
        }
    )
    with pytest.raises(DuplicateVisitDetectorRowsError):
        adapter.fetch_visit_records(make_registration())


@pytest.mark.parametrize(
    ("dataset_type", "table"),
    [
        ("visit_table", Table({"visitId": [VISIT_ID]})),
        (
            "visit_detector_table",
            Table({"visitId": [VISIT_ID], "detector": [1]}),
        ),
    ],
)
def test_rejects_invalid_table_rows(dataset_type: str, table: Table) -> None:
    datasets = {
        VISIT_DATASET_ID: ("visit_table", make_visit_table()),
        DETECTOR_DATASET_ID: (
            "visit_detector_table",
            make_visit_detector_table(),
        ),
    }
    dataset_id = (
        VISIT_DATASET_ID
        if dataset_type == "visit_table"
        else DETECTOR_DATASET_ID
    )
    datasets[dataset_id] = (dataset_type, table)
    adapter, _, _ = make_adapter(datasets)

    with pytest.raises(InvalidButlerTableError) as exc_info:
        adapter.fetch_visit_records(make_registration())

    assert exc_info.value.dataset_type == dataset_type
