"""Test helpers for Visit and VisitDetector records."""

from datetime import datetime
from typing import Any

from obsforge.models import VisitDetectorUpsert, VisitUpsert

__all__ = ["make_visit_detector_upsert", "make_visit_upsert"]


def make_visit_upsert(**overrides: Any) -> VisitUpsert:
    """Make a Visit upsert model."""
    data: dict[str, Any] = {
        "visitId": 2026010800095,
        "visit": 2026010800095,
        "physical_filter": "g_6",
        "band": "g",
        "ra": 54.0,
        "dec": -27.0,
        "decl": -27.0,
        "expTime": 30.0,
        "expMidpt": datetime(2026, 1, 9, 2, 46, 6, 123456),
        "obsStart": datetime(2026, 1, 9, 2, 45, 51),
    }
    data.update(overrides)
    return VisitUpsert(**data)


def make_visit_detector_upsert(**overrides: Any) -> VisitDetectorUpsert:
    """Make a VisitDetector upsert model."""
    data: dict[str, Any] = {
        "detectorId": 2026010800095001,
        "visitId": 2026010800095,
        "detector": 1,
        "physical_filter": "g_6",
        "band": "g",
        "ra": 54.1,
        "dec": -27.1,
        "pixelScale": 0.2,
        "expTime": 30.0,
        "expMidpt": datetime(2026, 1, 9, 2, 46, 6, 123456),
        "obsStart": datetime(2026, 1, 9, 2, 45, 51),
    }
    data.update(overrides)
    return VisitDetectorUpsert(**data)
