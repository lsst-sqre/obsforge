"""Tests for ObsCore storage."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge.exceptions import UnknownObsCoreRecordError
from obsforge.models import ObsCoreUpsert
from obsforge.storage import ObsCoreStore


def make_obscore(
    *,
    obs_id: str = "MC_O_20260108_000095",
    obs_title: str = (
        "visit_image - g - MC_O_20260108_000095-R30_S22 "
        "2026-01-09T02:45:51.712950Z"
    ),
    lsst_band: str = "g",
) -> ObsCoreUpsert:
    return ObsCoreUpsert(
        dataproduct_type="image",
        dataproduct_subtype="lsst.visit_image",
        facility_name="Rubin:Simonyi",
        calib_level=2,
        target_name="ddf_ecdfs, lowdust",
        obs_id=obs_id,
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
        lsst_band=lsst_band,
        lsst_filter="g_6",
        obs_title=obs_title,
        s_ra=54.00926387186998,
        s_dec=-27.174727694762304,
        s_fov=0.3572492942259721,
        s_region=(
            "POLYGON ICRS 53.891809 -27.319323 "
            "54.174563 -27.276221 54.126402 -27.030061 "
            "53.844298 -27.072994"
        ),
    )


@pytest.mark.asyncio
async def test_upsert_inserts_obscore_record(
    db_session: AsyncSession,
) -> None:
    store = ObsCoreStore(db_session)
    record = make_obscore()

    created = await store.upsert(record)

    assert created.model_dump() == record.model_dump()
    assert created.obs_id == "MC_O_20260108_000095"
    assert created.dataproduct_subtype == "lsst.visit_image"
    assert created.lsst_visit == 2026010800095
    assert created.lsst_detector == 125


@pytest.mark.asyncio
async def test_upsert_updates_obscore_record(
    db_session: AsyncSession,
) -> None:
    store = ObsCoreStore(db_session)
    first = await store.upsert(make_obscore())

    updated = await store.upsert(
        make_obscore(
            obs_title="updated visit image",
            lsst_band="r",
        )
    )

    assert updated.obs_id == first.obs_id
    assert updated.obs_title == "updated visit image"
    assert updated.lsst_band == "r"
    assert updated.dataproduct_type == "image"


@pytest.mark.asyncio
async def test_nullable_fields_round_trip_as_none(
    db_session: AsyncSession,
) -> None:
    store = ObsCoreStore(db_session)

    created = await store.upsert(make_obscore())

    assert created.access_estsize is None
    assert created.s_resolution is None
    assert created.s_xel1 is None
    assert created.s_xel2 is None
    assert created.t_xel is None
    assert created.t_resolution is None
    assert created.em_xel is None
    assert created.em_res_power is None
    assert created.pol_xel is None
    assert created.lsst_patch is None
    assert created.lsst_tract is None


@pytest.mark.asyncio
async def test_get_by_obs_id(db_session: AsyncSession) -> None:
    store = ObsCoreStore(db_session)
    created = await store.upsert(make_obscore())

    seen = await store.get_by_obs_id(created.obs_id)

    assert seen == created


@pytest.mark.asyncio
async def test_get_unknown_obs_id_raises(db_session: AsyncSession) -> None:
    store = ObsCoreStore(db_session)

    with pytest.raises(UnknownObsCoreRecordError):
        await store.get_by_obs_id("unknown-obs-id")
