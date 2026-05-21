"""Tests for the ObsForge database schema."""

from obsforge.schema import EnrichmentJob, EnrichmentJobPhase, SchemaBase


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
        "attempt_count",
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
