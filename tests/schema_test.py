"""Tests for the ObsForge database schema."""

import subprocess
from pathlib import Path
from typing import cast

import pytest
from safir.database import create_database_engine, drop_database
from sqlalchemy import (
    BigInteger,
    Float,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    text,
)

from obsforge.config import config
from obsforge.schema import (
    EnrichmentJob,
    EnrichmentJobPhase,
    ObsCore,
    SchemaBase,
)


@pytest.mark.asyncio
async def test_schema_migrations() -> None:
    """Test that Alembic migrations create the current ORM schema."""
    engine = create_database_engine(
        config.database_url, config.database_password
    )
    try:
        await drop_database(engine, SchemaBase.metadata)
        async with engine.begin() as connection:
            await connection.execute(
                text("DROP SCHEMA IF EXISTS ivoa CASCADE")
            )
    finally:
        await engine.dispose()

    alembic_config_path = Path(__file__).parents[1] / "alembic.ini"
    subprocess.run(
        ["alembic", "-c", str(alembic_config_path), "upgrade", "head"],
        check=True,
        cwd=alembic_config_path.parent,
    )
    subprocess.run(
        ["alembic", "-c", str(alembic_config_path), "check"],
        check=True,
        cwd=alembic_config_path.parent,
    )


def test_enrichment_job_table_registered() -> None:
    assert (
        SchemaBase.metadata.tables["enrichment_job"] is EnrichmentJob.__table__
    )


def test_enrichment_job_columns() -> None:
    columns = EnrichmentJob.__table__.columns

    assert set(columns.keys()) == {
        "id",
        "visit",
        "instrument",
        "day_obs",
        "phase",
        "error_code",
        "error_message",
        "arq_job_id",
        "registration_payload",
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
    }
    assert columns["visit"].nullable is False
    assert columns["visit"].type.python_type is int
    assert columns["error_code"].nullable is True
    assert columns["error_message"].nullable is True
    assert columns["arq_job_id"].nullable is True
    assert columns["started_at"].nullable is True
    assert columns["completed_at"].nullable is True


def test_enrichment_job_unique_constraints() -> None:
    table = cast("Table", EnrichmentJob.__table__)
    constraints = {
        constraint.name: constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    constraint = constraints["enrichment_job_instrument_visit_key"]
    assert {column.name for column in constraint.columns} == {
        "instrument",
        "visit",
    }


def test_enrichment_job_phase_values() -> None:
    assert [phase.value for phase in EnrichmentJobPhase] == [
        "PENDING",
        "QUEUED",
        "EXECUTING",
        "COMPLETED",
        "ERROR",
    ]


def test_obscore_table_registered() -> None:
    assert SchemaBase.metadata.tables["ivoa.ObsCore"] is ObsCore.__table__


def test_obscore_columns() -> None:
    columns = ObsCore.__table__.columns

    assert set(columns.keys()) == {
        "dataproduct_type",
        "dataproduct_subtype",
        "calib_level",
        "target_name",
        "obs_id",
        "obs_collection",
        "obs_publisher_did",
        "access_url",
        "access_format",
        "access_estsize",
        "s_ra",
        "s_dec",
        "s_fov",
        "s_region",
        "s_resolution",
        "s_xel1",
        "s_xel2",
        "t_xel",
        "t_min",
        "t_max",
        "t_exptime",
        "t_resolution",
        "em_xel",
        "em_min",
        "em_max",
        "em_res_power",
        "o_ucd",
        "pol_xel",
        "instrument_name",
        "facility_name",
        "obs_title",
        "em_filter_name",
        "lsst_visit",
        "lsst_detector",
        "lsst_filter",
        "lsst_band",
        "lsst_patch",
        "lsst_tract",
    }
    assert columns["obs_id"].primary_key is True
    assert columns["obs_id"].nullable is False
    assert isinstance(columns["access_url"].type, Text)
    assert isinstance(columns["calib_level"].type, Integer)
    assert isinstance(columns["lsst_visit"].type, BigInteger)
    assert isinstance(columns["s_ra"].type, Float)


def test_obscore_nullable_columns() -> None:
    columns = ObsCore.__table__.columns
    nullable_columns = {
        "target_name",
        "access_estsize",
        "s_resolution",
        "s_xel1",
        "s_xel2",
        "t_xel",
        "t_resolution",
        "em_xel",
        "em_res_power",
        "pol_xel",
        "lsst_patch",
        "lsst_tract",
    }

    for column_name, column in columns.items():
        assert column.nullable is (column_name in nullable_columns)


def test_obscore_column_info() -> None:
    columns = ObsCore.__table__.columns

    assert columns["s_ra"].info == {
        "unit": "deg",
        "description": "Central Spatial Position in ICRS; Right ascension",
        "ucd": "pos.eq.ra",
    }
    assert columns["obs_id"].info == {
        "unit": "",
        "description": "Internal ID given by the ObsTAP service",
        "ucd": "meta.id",
    }
    assert columns["em_filter_name"].info == {
        "unit": "",
        "description": (
            "Filter name associated with the observation spectral coverage"
        ),
        "ucd": "meta.id;instr.filter",
    }
    assert columns["lsst_detector"].info == {
        "unit": "",
        "description": "Identifier for CCD within the LSSTCam focal plane",
        "ucd": "meta.id;instr.det",
    }
