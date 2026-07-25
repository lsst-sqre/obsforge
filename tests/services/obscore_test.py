"""Tests for ObsCore business logic."""

import pytest

from obsforge.models import ObsCoreUpsert, SerializedObsCore
from obsforge.services import ObsCoreService


def make_obscore_upsert() -> ObsCoreUpsert:
    return ObsCoreUpsert(
        dataproduct_type="image",
        dataproduct_subtype="lsst.visit_image",
        facility_name="Rubin:Simonyi",
        calib_level=2,
        target_name="ddf_ecdfs, lowdust",
        obs_id="MC_O_20260108_000095",
        obs_collection="LSST.Prompt",
        obs_publisher_did="D019ba0a6-0173-765f-bf27-56884ff9342a",
        access_url=(
            "https://example.com/api/datalink/links?"
            "ID=D019ba0a6-0173-765f-bf27-56884ff9342a"
        ),
        access_format="application/x-votable+xml;content=datalink",
        access_estsize=None,
        s_resolution=None,
        s_xel1=None,
        s_xel2=None,
        t_xel=None,
        t_min=61049.11561010359,
        t_max=61049.115968101854,
        t_exptime=30.0,
        t_resolution=None,
        em_xel=None,
        em_min=4.026e-07,
        em_max=5.483e-07,
        em_res_power=None,
        em_filter_name="g",
        o_ucd="phot.flux.density",
        pol_xel=None,
        instrument_name="LSSTCam",
        lsst_visit=2026010800095,
        lsst_detector=125,
        lsst_tract=None,
        lsst_patch=None,
        lsst_band="g",
        lsst_filter="g_6",
        obs_title=(
            "visit_image - g - MC_O_20260108_000095-R30_S22 "
            "2026-01-09T02:45:51.712950Z"
        ),
        s_ra=54.00926387186998,
        s_dec=-27.174727694762304,
        s_fov=0.3572492942259721,
        s_region=(
            "POLYGON ICRS 53.891809 -27.319323 "
            "54.174563 -27.276221 54.126402 -27.030061 "
            "53.844298 -27.072994"
        ),
    )


def make_obscore() -> SerializedObsCore:
    return SerializedObsCore.model_validate(make_obscore_upsert().model_dump())


class FakeObsCoreStore:
    def __init__(self) -> None:
        self.obscore = make_obscore()
        self.calls: list[str] = []

    async def upsert(self, record: ObsCoreUpsert) -> SerializedObsCore:
        self.calls.append("upsert")
        return self.obscore

    async def get_by_obs_id(self, obs_id: str) -> SerializedObsCore:
        self.calls.append("get_by_obs_id")
        return self.obscore


@pytest.mark.asyncio
async def test_upsert_delegates_to_store() -> None:
    store = FakeObsCoreStore()
    service = ObsCoreService(store)

    obscore = await service.upsert(make_obscore_upsert())

    assert obscore == store.obscore
    assert store.calls == ["upsert"]


@pytest.mark.asyncio
async def test_get_by_obs_id_delegates_to_store() -> None:
    store = FakeObsCoreStore()
    service = ObsCoreService(store)

    obscore = await service.get_by_obs_id(store.obscore.obs_id)

    assert obscore == store.obscore
    assert store.calls == ["get_by_obs_id"]
