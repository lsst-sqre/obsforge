"""Tests for the ObsForge database schema."""

import subprocess
from datetime import datetime
from pathlib import Path
from typing import cast

import pytest
from safir.database import create_database_engine, drop_database
from sqlalchemy import (
    DDL,
    DOUBLE_PRECISION,
    REAL,
    BigInteger,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_mock_engine,
    inspect,
    text,
)

from obsforge.config import config
from obsforge.schema import (
    EnrichmentJob,
    EnrichmentJobPhase,
    ObsCore,
    SchedulerObservatoryState,
    SchemaBase,
    Visit,
    VisitDetector,
)


@pytest.mark.asyncio
async def test_schema_migrations() -> None:
    """Test that Alembic migrations create the current ORM schema."""
    alembic_config_path = Path(__file__).parents[1] / "alembic.ini"
    engine = create_database_engine(
        config.database_url, config.database_password
    )
    try:
        await drop_database(engine, SchemaBase.metadata)
        async with engine.begin() as connection:
            await connection.execute(
                text("DROP SCHEMA IF EXISTS ivoa CASCADE")
            )
            await connection.execute(
                text("DROP SCHEMA IF EXISTS scheduler CASCADE")
            )
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

        async with engine.connect() as connection:
            ivoa_tables = await connection.run_sync(
                lambda conn: inspect(conn).get_table_names(schema="ivoa")
            )
        assert "obscore" in ivoa_tables
        assert "ObsCore" not in ivoa_tables

        async with engine.connect() as connection:
            primary_key = await connection.run_sync(
                lambda conn: inspect(conn).get_pk_constraint("VisitDetector")
            )
            foreign_keys = await connection.run_sync(
                lambda conn: inspect(conn).get_foreign_keys("VisitDetector")
            )
        assert primary_key["constrained_columns"] == ["visitId", "detectorId"]
        assert len(foreign_keys) == 1
        assert foreign_keys[0]["constrained_columns"] == ["visitId"]
        assert foreign_keys[0]["referred_table"] == "Visit"
        assert foreign_keys[0]["referred_columns"] == ["visitId"]
    finally:
        await engine.dispose()


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
    assert SchemaBase.metadata.tables["ivoa.obscore"] is ObsCore.__table__


def test_obscore_schema_create_ddl_registered() -> None:
    # ObsCore owns the ivoa schema setup, so importing it should register the
    # metadata hook that creates the schema before tables are created.
    statements: list[str] = []

    def record(sql: object, *_args: object, **_kwargs: object) -> None:
        if isinstance(sql, DDL):
            statements.append(str(sql))

    engine = create_mock_engine(
        "postgresql+psycopg://",
        record,
    )

    SchemaBase.metadata.create_all(engine)

    assert "CREATE SCHEMA IF NOT EXISTS ivoa" in statements
    assert "CREATE SCHEMA IF NOT EXISTS scheduler" in statements


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


def test_visit_tables_registered() -> None:
    assert SchemaBase.metadata.tables["Visit"] is Visit.__table__
    assert (
        SchemaBase.metadata.tables["VisitDetector"] is VisitDetector.__table__
    )


def test_visit_columns_and_types() -> None:
    columns = Visit.__table__.columns
    assert set(columns.keys()) == {
        "visitId",
        "visit",
        "physical_filter",
        "band",
        "ra",
        "dec",
        "decl",
        "skyRotation",
        "azimuth",
        "altitude",
        "zenithDistance",
        "airmass",
        "expTime",
        "expMidpt",
        "expMidptMJD",
        "obsStart",
        "obsStartMJD",
    }
    assert columns["visitId"].primary_key is True
    assert isinstance(columns["visitId"].type, BigInteger)
    assert isinstance(columns["visit"].type, BigInteger)
    assert isinstance(columns["ra"].type, DOUBLE_PRECISION)
    assert isinstance(columns["expMidpt"].type, DateTime)
    assert columns["expMidpt"].type.timezone is False
    assert isinstance(columns["physical_filter"].type, String)
    assert columns["physical_filter"].type.length == 4
    assert isinstance(columns["band"].type, String)
    assert columns["band"].type.length == 1
    required = {"visitId", "visit"}
    for name, column in columns.items():
        assert column.nullable is (name not in required)


def test_visit_detector_columns_and_types() -> None:
    columns = VisitDetector.__table__.columns
    assert set(columns.keys()) == {
        "detectorId",
        "visitId",
        "physical_filter",
        "band",
        "ra",
        "dec",
        "pixelScale",
        "zenithDistance",
        "expTime",
        "zeroPoint",
        "psfSigma",
        "psfArea",
        "psfIxx",
        "psfIyy",
        "psfIxy",
        "skyBg",
        "skyNoise",
        "psfAdaptiveThresholdValue",
        "psfAdaptiveIncludeThresholdMultiplier",
        "nShapeletsStar",
        "shapeletsOnlyIqScore",
        "shapeletsIqScore",
        "centroidDiffShapeletsVsSlotMedian",
        "shapeletsStarEMedian",
        "shapeletsStarUnNormalizedEMedian",
        "refCatSourceDensity",
        "astromOffsetMean",
        "astromOffsetStd",
        "nPsfStar",
        "psfStarDeltaE1Median",
        "psfStarDeltaE2Median",
        "psfStarDeltaE1Scatter",
        "psfStarDeltaE2Scatter",
        "psfStarDeltaSizeMedian",
        "psfStarDeltaSizeScatter",
        "psfStarScaledDeltaSizeScatter",
        "psfTraceRadiusDelta",
        "psfApFluxDelta",
        "psfApCorrSigmaScaledDelta",
        "maxDistToNearestPsf",
        "starEMedian",
        "starUnNormalizedEMedian",
        "starComa1Median",
        "starComa2Median",
        "starTrefoil1Median",
        "starTrefoil2Median",
        "starKurtosisMedian",
        "starE41Median",
        "starE42Median",
        "effTime",
        "effTimePsfSigmaScale",
        "effTimeSkyBgScale",
        "effTimeZeroPointScale",
        "magLim",
        "decl",
        "ccdVisitId",
        "detector",
        "seeing",
        "skyRotation",
        "expMidpt",
        "expMidptMJD",
        "obsStart",
        "obsStartMJD",
        "darkTime",
        "xSize",
        "ySize",
        "llcra",
        "llcdec",
        "ulcra",
        "ulcdec",
        "urcra",
        "urcdec",
        "lrcra",
        "lrcdec",
        "wcsPreliminaryDetectorPointingResidual",
        "wcsPreliminaryVisitPointingResidual",
    }
    assert isinstance(columns["detectorId"].type, BigInteger)
    assert isinstance(columns["visitId"].type, BigInteger)
    assert isinstance(columns["nPsfStar"].type, Integer)
    assert isinstance(columns["pixelScale"].type, REAL)
    assert isinstance(columns["decl"].type, DOUBLE_PRECISION)
    assert isinstance(columns["physical_filter"].type, String)
    assert columns["physical_filter"].type.length == 32
    assert isinstance(columns["band"].type, String)
    assert columns["band"].type.length == 32
    assert isinstance(columns["expMidpt"].type, DateTime)
    assert columns["expMidpt"].type.timezone is False
    required = {"detectorId", "visitId", "detector"}
    for name, column in columns.items():
        assert column.nullable is (name not in required)


def test_visit_constraints_and_indexes() -> None:
    visit_table = cast("Table", Visit.__table__)
    visit_uniques = {
        constraint.name: constraint
        for constraint in visit_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert {
        column.name for column in visit_uniques["visit_visit_key"].columns
    } == {"visit"}

    detector_table = cast("Table", VisitDetector.__table__)
    assert [column.name for column in detector_table.primary_key.columns] == [
        "visitId",
        "detectorId",
    ]
    assert not any(
        isinstance(constraint, UniqueConstraint)
        for constraint in detector_table.constraints
    )
    foreign_keys = [
        constraint
        for constraint in detector_table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert len(foreign_keys) == 1
    assert [
        element.target_fullname for element in foreign_keys[0].elements
    ] == ["Visit.visitId"]
    assert not detector_table.indexes


def test_scheduler_observatory_state_schema() -> None:
    table = SchedulerObservatoryState.__table__

    assert SchemaBase.metadata.tables["scheduler.observatory_state"] is table
    assert table.schema == "scheduler"
    assert set(table.columns.keys()) == {
        "timestamp",
        "ra",
        "declination",
        "positionAngle",
        "parallacticAngle",
        "tracking",
        "telescopeAltitude",
        "telescopeAzimuth",
        "telescopeRotator",
        "domeAltitude",
        "domeAzimuth",
        "filterPosition",
        "filterMounted",
        "filterUnmounted",
    }
    timestamp = table.columns["timestamp"]
    assert timestamp.primary_key is True
    assert timestamp.nullable is False
    assert timestamp.type.python_type is datetime
    assert isinstance(timestamp.type, DateTime)
    assert timestamp.type.timezone is True
    assert table.columns["tracking"].type.python_type is bool
    assert table.columns["filterMounted"].type.python_type is str
    assert not table.indexes
