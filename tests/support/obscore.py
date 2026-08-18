"""Test helpers for ObsCore records."""

from typing import Any
from uuid import UUID

from obsforge.models import ObsCoreUpsert

DATASET_ID = UUID("019ba0a6-0173-765f-bf27-56884ff9342a")
SECOND_DATASET_ID = UUID("019ba0a5-fe48-7c7a-8c3f-540057f026c3")


def make_obscore_upsert(**overrides: Any) -> ObsCoreUpsert:
    """Make an ObsCore upsert model."""
    data: dict[str, Any] = {
        "dataproduct_type": "image",
        "dataproduct_subtype": "lsst.preliminary_visit_image",
        "facility_name": "Rubin:Simonyi",
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
        "access_estsize": None,
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
        "em_filter_name": "g",
        "o_ucd": "phot.flux.density",
        "pol_xel": None,
        "instrument_name": "LSSTCam",
        "lsst_visit": 2026010800095,
        "lsst_detector": 122,
        "lsst_tract": None,
        "lsst_patch": None,
        "lsst_band": "g",
        "lsst_filter": "g_6",
        "obs_title": (
            "preliminary_visit_image - g - "
            "MC_O_20260108_000095-R30_S22 2026-01-09T02:45:51Z"
        ),
    }
    data.update(overrides)
    return ObsCoreUpsert(**data)


def make_obscore_row(**overrides: Any) -> dict[str, Any]:
    """Make a row dictionary returned by the dax_obscore exporter."""
    return make_obscore_upsert(**overrides).model_dump(
        exclude={"access_estsize"}
    )
