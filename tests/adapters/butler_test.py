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
from tests.support.registration import make_visit_registration

VISIT_ID = 2026010800095
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


def make_visit_table(*, visit_ids: list[int] | None = None) -> Table:
    """Make an Astropy visit table."""
    visit_ids = visit_ids or [VISIT_ID]
    table = Table(
        {
            "visitId": np.asarray(visit_ids, dtype=np.int64),
            "visit": np.asarray(visit_ids, dtype=np.int64),
            "expMidpt": np.asarray(
                ["2026-01-09T02:46:06.123456789"] * len(visit_ids),
                dtype="datetime64[ns]",
            ),
            "obsStart": np.asarray(
                ["NaT"] * len(visit_ids), dtype="datetime64[ns]"
            ),
        }
    )
    table["physical_filter"] = MaskedColumn(
        ["g_6"] * len(visit_ids), mask=[True] * len(visit_ids)
    )
    return table


def make_detector_table(
    *,
    visit_ids: list[int] | None = None,
    detector_ids: list[int] | None = None,
) -> Table:
    """Make an Astropy detector table."""
    visit_ids = visit_ids or [VISIT_ID, VISIT_ID]
    detector_ids = detector_ids or [1001, 1002]
    return Table(
        {
            "detectorId": np.asarray(detector_ids, dtype=np.int64),
            "visitId": np.asarray(visit_ids, dtype=np.int64),
            "detector": np.arange(1, len(visit_ids) + 1, dtype=np.int64),
            "pixelScale": np.asarray([0.2] * len(visit_ids), dtype=np.float32),
            "skyBg": np.asarray([np.nan] * len(visit_ids), dtype=np.float32),
        }
    )


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


def test_fetch_visit_records() -> None:
    adapter, butler, factory = make_adapter(
        {
            VISIT_DATASET_ID: (
                "visit_table",
                make_visit_table(visit_ids=[123, VISIT_ID]),
            ),
            DETECTOR_DATASET_ID: (
                "visit_detector_table",
                make_detector_table(
                    visit_ids=[123, VISIT_ID, VISIT_ID],
                    detector_ids=[1000, 1001, 1002],
                ),
            ),
        }
    )

    records = adapter.fetch_visit_records(make_registration())

    assert records.visit.visitId == VISIT_ID
    assert records.visit.expMidpt is not None
    assert records.visit.expMidpt.microsecond == 123456
    assert records.visit.obsStart is None
    assert records.visit.physical_filter is None
    assert [record.detectorId for record in records.detectors] == [1001, 1002]
    assert isinstance(records.visit.visitId, int)
    assert isinstance(records.detectors[0].pixelScale, float)
    assert records.detectors[0].pixelScale == pytest.approx(0.2)
    assert records.detectors[0].skyBg is not None
    assert math.isnan(records.detectors[0].skyBg)
    assert factory.calls == [("prompt", "worker-token")]
    assert butler.requested_ids == [VISIT_DATASET_ID, DETECTOR_DATASET_ID]


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
    detector_table = make_detector_table()
    if dataset_type == "visit_table":
        visit_table = make_visit_table(visit_ids=[123])
    else:
        detector_table = make_detector_table(visit_ids=[123, 123])
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
                make_visit_table(visit_ids=[VISIT_ID, VISIT_ID]),
            ),
            DETECTOR_DATASET_ID: (
                "visit_detector_table",
                make_detector_table(),
            ),
        }
    )
    with pytest.raises(DuplicateVisitRowsError):
        adapter.fetch_visit_records(make_registration())


@pytest.mark.parametrize("identity", ["detectorId", "visit_detector"])
def test_rejects_duplicate_detector_identities(identity: str) -> None:
    table = make_detector_table()
    if identity == "detectorId":
        table["detectorId"][1] = table["detectorId"][0]
    else:
        table["detector"][1] = table["detector"][0]
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
            make_detector_table(),
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
