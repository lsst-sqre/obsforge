"""Tests for the ObsForge database schema."""

from sqlalchemy import BigInteger, Float, Integer, Text

from obsforge.schema import (
    EnrichmentJob,
    EnrichmentJobPhase,
    ObsCore,
    SchemaBase,
)


def test_enrichment_job_table_registered() -> None:
    assert (
        SchemaBase.metadata.tables["enrichment_job"] is EnrichmentJob.__table__
    )


def test_enrichment_job_columns() -> None:
    columns = EnrichmentJob.__table__.columns

    assert set(columns.keys()) == {
        "id",
        "visit_id",
        "instrument",
        "day_obs",
        "phase",
        "error_code",
        "error_message",
        "registration_payload",
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
    }
    assert columns["visit_id"].nullable is False
    assert columns["error_code"].nullable is True
    assert columns["error_message"].nullable is True
    assert columns["started_at"].nullable is True
    assert columns["completed_at"].nullable is True


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
        "visit_id",
        "band",
        "physical_filter",
    }
    assert columns["visit_id"].primary_key is True
    assert columns["visit_id"].nullable is False
    assert isinstance(columns["dataproduct_subtype"].type, Text)
    assert isinstance(columns["access_url"].type, Text)
    assert isinstance(columns["calib_level"].type, Integer)
    assert isinstance(columns["s_xel1"].type, BigInteger)
    assert isinstance(columns["s_ra"].type, Float)
    assert columns["target_name"].nullable is True
    assert columns["dataproduct_type"].nullable is False
    assert columns["dataproduct_type"].server_default is not None
    assert columns["target_name"].server_default is None


def test_obscore_column_info() -> None:
    columns = ObsCore.__table__.columns

    assert columns["s_ra"].info == {
        "unit": "deg",
        "description": "Central Spatial Position in ICRS; Right ascension",
        "ucd": "pos.eq.ra",
    }
    assert columns["access_estsize"].info == {
        "unit": "kbyte",
        "description": "Estimated size of dataset in kilobytes",
        "ucd": "meta.id",
    }
    assert columns["visit_id"].info == {
        "unit": "",
        "description": "Identifier for a specific LSSTCam pointing",
        "ucd": "meta.id;obs",
    }


def test_obscore_constraints() -> None:
    constraint_names = {
        constraint.name
        for constraint in SchemaBase.metadata.tables[
            "ivoa.ObsCore"
        ].constraints
    }

    assert "obscore_dataproduct_type_check" in constraint_names
    assert "obscore_target_name_null_check" in constraint_names
    assert "obscore_access_estsize_null_check" in constraint_names
    assert "obscore_instrument_name_check" in constraint_names
