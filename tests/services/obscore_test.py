"""Tests for ObsCore business logic."""

import pytest

from obsforge.models import ObsCoreUpsert, SerializedObsCore
from obsforge.services import ObsCoreService


def make_obscore_upsert() -> ObsCoreUpsert:
    return ObsCoreUpsert(
        visit_id="LSSTCam-20260327-123456",
        dataproduct_subtype="lsst.raw",
        obs_id="obs-1",
        obs_publisher_did="ivo://rubin/LSSTCam-20260327-123456",
        access_url="https://example.com/datalink/LSSTCam-20260327-123456",
        s_ra=12.3,
        s_dec=-45.6,
        s_region="CIRCLE ICRS 12.3 -45.6 0.1",
        s_resolution=0.7,
        t_min=60396.344,
        t_max=60396.345,
        t_exptime=30.0,
        em_min=5.5e-7,
        em_max=7.0e-7,
        band="r",
        physical_filter="r_03",
    )


def make_obscore() -> SerializedObsCore:
    upsert = make_obscore_upsert()
    return SerializedObsCore(
        dataproduct_type="image",
        dataproduct_subtype=upsert.dataproduct_subtype,
        calib_level=2,
        target_name=None,
        obs_id=upsert.obs_id,
        obs_collection="Prompt Processing Visits",
        obs_publisher_did=upsert.obs_publisher_did,
        access_url=upsert.access_url,
        access_format="application/x-votable+xml;content=datalink",
        access_estsize=None,
        s_ra=upsert.s_ra,
        s_dec=upsert.s_dec,
        s_fov=3.5,
        s_region=upsert.s_region,
        s_resolution=upsert.s_resolution,
        s_xel1=None,
        s_xel2=None,
        t_xel=None,
        t_min=upsert.t_min,
        t_max=upsert.t_max,
        t_exptime=upsert.t_exptime,
        t_resolution=None,
        em_xel=None,
        em_min=upsert.em_min,
        em_max=upsert.em_max,
        em_res_power=None,
        o_ucd="phot.flux",
        pol_xel=None,
        instrument_name="LSSTCAM",
        facility_name="Rubin:Simonyi",
        visit_id=upsert.visit_id,
        band=upsert.band,
        physical_filter=upsert.physical_filter,
    )


class FakeObsCoreStore:
    def __init__(self) -> None:
        self.obscore = make_obscore()
        self.calls: list[str] = []

    async def upsert(self, record: ObsCoreUpsert) -> SerializedObsCore:
        self.calls.append("upsert")
        return self.obscore

    async def get_by_visit_id(self, visit_id: str) -> SerializedObsCore:
        self.calls.append("get_by_visit_id")
        return self.obscore

    async def delete_by_visit_id(self, visit_id: str) -> None:
        self.calls.append("delete_by_visit_id")


@pytest.mark.asyncio
async def test_upsert_delegates_to_store() -> None:
    store = FakeObsCoreStore()
    service = ObsCoreService(store)

    obscore = await service.upsert(make_obscore_upsert())

    assert obscore == store.obscore
    assert store.calls == ["upsert"]


@pytest.mark.asyncio
async def test_get_by_visit_id_delegates_to_store() -> None:
    store = FakeObsCoreStore()
    service = ObsCoreService(store)

    obscore = await service.get_by_visit_id(store.obscore.visit_id)

    assert obscore == store.obscore
    assert store.calls == ["get_by_visit_id"]


@pytest.mark.asyncio
async def test_delete_by_visit_id_delegates_to_store() -> None:
    store = FakeObsCoreStore()
    service = ObsCoreService(store)

    await service.delete_by_visit_id(store.obscore.visit_id)

    assert store.calls == ["delete_by_visit_id"]
