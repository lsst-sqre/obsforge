"""Test doubles for the Butler Visit adapter."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from .visit import INSTRUMENT


class FakeDatasetType:
    """Minimal Butler dataset type."""

    def __init__(self, name: str) -> None:
        self.name = name


class FakeDatasetRef:
    """Minimal Butler dataset reference."""

    def __init__(
        self, dataset_id: UUID, dataset_type: str, instrument: str | None
    ) -> None:
        self.id = dataset_id
        self.datasetType = FakeDatasetType(dataset_type)
        self.dataId = (
            {"instrument": instrument} if instrument is not None else {}
        )


class FakeButler:
    """In-memory Butler test double."""

    def __init__(
        self,
        datasets: Mapping[UUID, tuple[str, Any]],
        *,
        instruments: Mapping[UUID, str | None] | None = None,
    ) -> None:
        self.datasets = datasets
        self.instruments = instruments if instruments is not None else {}
        self.requested_ids: list[UUID] = []
        self.requested_refs: list[FakeDatasetRef] = []

    def get_dataset(self, dataset_id: UUID) -> FakeDatasetRef | None:
        self.requested_ids.append(dataset_id)
        entry = self.datasets.get(dataset_id)
        if entry is None:
            return None
        instrument = self.instruments.get(dataset_id, INSTRUMENT)
        return FakeDatasetRef(dataset_id, entry[0], instrument)

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
