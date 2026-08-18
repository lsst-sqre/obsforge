"""Test helpers for visit registration payloads."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from obsforge.models import VisitDataset, VisitRegistration

from .obscore import DATASET_ID


def make_visit_registration(
    *,
    instrument: str = "LSSTCam",
    day_obs: int = 20260108,
    visit: int = 2026010800095,
    datasets: Sequence[VisitDataset | Mapping[str, Any]] | None = None,
    timespan: Mapping[str, Any] | None = None,
) -> VisitRegistration:
    """Make a visit registration model."""
    if datasets is None:
        datasets = [
            {
                "dataset_type": "preliminary_visit_image",
                "id": DATASET_ID,
            }
        ]
    if timespan is None:
        timespan = {
            "begin": datetime(2026, 1, 9, 2, 45, 51, tzinfo=UTC),
            "end": datetime(2026, 1, 9, 2, 46, 26, tzinfo=UTC),
        }

    return VisitRegistration.model_validate(
        {
            "instrument": instrument,
            "day_obs": day_obs,
            "visit": visit,
            "datasets": datasets,
            "timespan": timespan,
        }
    )
