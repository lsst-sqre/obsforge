"""Tests for ObsCore storage."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge.exceptions import UnknownObsCoreRecordError
from obsforge.models import ObsCoreUpsert
from obsforge.storage import ObsCoreStore


def make_obscore(
    *,
    visit_id: str = "LSSTCam-20260327-123456",
    dataproduct_subtype: str = "lsst.raw",
    obs_id: str = "obs-1",
    s_ra: float = 12.3,
    band: str = "r",
) -> ObsCoreUpsert:
    return ObsCoreUpsert(
        visit_id=visit_id,
        dataproduct_subtype=dataproduct_subtype,
        obs_id=obs_id,
        obs_publisher_did=f"ivo://rubin/{visit_id}",
        access_url=f"https://example.com/datalink/{visit_id}",
        s_ra=s_ra,
        s_dec=-45.6,
        s_region="CIRCLE ICRS 12.3 -45.6 0.1",
        s_resolution=0.7,
        t_min=60396.344,
        t_max=60396.345,
        t_exptime=30.0,
        em_min=5.5e-7,
        em_max=7.0e-7,
        band=band,
        physical_filter="r_03",
    )


@pytest.mark.asyncio
async def test_upsert_inserts_obscore_record(
    db_session: AsyncSession,
) -> None:
    store = ObsCoreStore(db_session)
    record = make_obscore()

    created = await store.upsert(record)

    assert created.visit_id == record.visit_id
    assert created.dataproduct_subtype == "lsst.raw"
    assert created.obs_id == "obs-1"
    assert created.dataproduct_type == "image"
    assert created.calib_level == 2
    assert created.obs_collection == "Prompt Processing Visits"
    assert created.access_format == (
        "application/x-votable+xml;content=datalink"
    )
    assert created.s_fov == 3.5
    assert created.o_ucd == "phot.flux"
    assert created.instrument_name == "LSSTCAM"
    assert created.facility_name == "Rubin:Simonyi"
    assert created.target_name is None
    assert created.access_estsize is None
    assert created.s_xel1 is None
    assert created.t_resolution is None
    assert created.em_res_power is None


@pytest.mark.asyncio
async def test_upsert_updates_obscore_record(
    db_session: AsyncSession,
) -> None:
    store = ObsCoreStore(db_session)
    first = await store.upsert(make_obscore())

    updated = await store.upsert(
        make_obscore(
            dataproduct_subtype="lsst.calexp",
            obs_id="obs-2",
            s_ra=98.7,
            band="i",
        )
    )

    assert updated.visit_id == first.visit_id
    assert updated.dataproduct_subtype == "lsst.calexp"
    assert updated.obs_id == "obs-2"
    assert updated.s_ra == 98.7
    assert updated.band == "i"
    assert updated.dataproduct_type == "image"


@pytest.mark.asyncio
async def test_get_by_visit_id(db_session: AsyncSession) -> None:
    store = ObsCoreStore(db_session)
    created = await store.upsert(make_obscore())

    seen = await store.get_by_visit_id(created.visit_id)

    assert seen == created


@pytest.mark.asyncio
async def test_delete_by_visit_id(db_session: AsyncSession) -> None:
    store = ObsCoreStore(db_session)
    created = await store.upsert(make_obscore())

    await store.delete_by_visit_id(created.visit_id)

    with pytest.raises(UnknownObsCoreRecordError):
        await store.get_by_visit_id(created.visit_id)


@pytest.mark.asyncio
async def test_get_unknown_visit_raises(db_session: AsyncSession) -> None:
    store = ObsCoreStore(db_session)

    with pytest.raises(UnknownObsCoreRecordError):
        await store.get_by_visit_id("unknown-visit")


@pytest.mark.asyncio
async def test_delete_unknown_visit_raises(db_session: AsyncSession) -> None:
    store = ObsCoreStore(db_session)

    with pytest.raises(UnknownObsCoreRecordError):
        await store.delete_by_visit_id("unknown-visit")
