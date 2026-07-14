"""Tests for ObsForge exceptions."""

from fastapi import status
from safir.fastapi import ClientRequestError

from obsforge.exceptions import (
    InvalidEnrichmentJobTransitionError,
    UnknownEnrichmentJobError,
    UnknownEnrichmentJobVisitError,
    UnknownObsCoreRecordError,
)
from obsforge.schema import EnrichmentJobPhase


def test_unknown_enrichment_job_error() -> None:
    error = UnknownEnrichmentJobError(42)

    assert isinstance(error, ClientRequestError)
    assert error.status_code == status.HTTP_404_NOT_FOUND
    assert error.to_dict() == {
        "msg": "Unknown enrichment job 42",
        "type": "unknown_enrichment_job",
    }


def test_unknown_enrichment_job_visit_error() -> None:
    error = UnknownEnrichmentJobVisitError("LATISS", 2026010800095)

    assert isinstance(error, ClientRequestError)
    assert error.status_code == status.HTTP_404_NOT_FOUND
    assert error.to_dict() == {
        "msg": (
            "Unknown enrichment job for "
            "instrument 'LATISS' and visit 2026010800095"
        ),
        "type": "unknown_enrichment_job_visit",
    }


def test_unknown_obscore_record_error() -> None:
    error = UnknownObsCoreRecordError("ivo://rubin.example/obs/42")

    assert isinstance(error, ClientRequestError)
    assert error.status_code == status.HTTP_404_NOT_FOUND
    assert error.to_dict() == {
        "msg": "Unknown ObsCore record ivo://rubin.example/obs/42",
        "type": "unknown_obscore_record",
    }


def test_invalid_enrichment_job_transition_error() -> None:
    error = InvalidEnrichmentJobTransitionError(
        42, EnrichmentJobPhase.COMPLETED, EnrichmentJobPhase.EXECUTING
    )

    assert isinstance(error, ClientRequestError)
    assert error.status_code == status.HTTP_409_CONFLICT
    assert error.to_dict() == {
        "msg": (
            "Cannot transition enrichment job 42 from COMPLETED to EXECUTING"
        ),
        "type": "invalid_enrichment_job_transition",
    }
