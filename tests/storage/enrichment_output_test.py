"""Tests for atomic writes of visit enrichment outputs."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from obsforge.exceptions import UnknownObsCoreRecordError
from obsforge.storage import (
    EnrichmentOutputStore,
    ObsCoreStore,
    VisitDetectorStore,
    VisitStore,
)
from tests.support.obscore import make_obscore_upsert
from tests.support.visit import (
    DETECTOR_ID,
    INSTRUMENT,
    SECOND_DETECTOR_ID,
    VISIT_ID,
    make_visit_detector_upsert,
    make_visit_upsert,
)


@pytest.mark.asyncio
async def test_constraint_failure_rolls_back_all_outputs(
    db_session: AsyncSession,
) -> None:
    visits = VisitStore(db_session)
    detectors = VisitDetectorStore(db_session)
    obscore = ObsCoreStore(db_session)
    original_visit = make_visit_upsert(skyRotation=200.0)
    original_detector = make_visit_detector_upsert(seeing=1.8)
    original_obscore = make_obscore_upsert(lsst_visit=VISIT_ID)
    await visits.upsert(original_visit)
    await detectors.upsert(original_detector)
    await obscore.upsert(original_obscore)

    new_detector = make_visit_detector_upsert(
        detectorId=SECOND_DETECTOR_ID, detector=SECOND_DETECTOR_ID
    )
    new_obscore = make_obscore_upsert(obs_id="new-output", lsst_visit=VISIT_ID)
    invalid_obscore = make_obscore_upsert(
        obs_id="invalid-output", lsst_visit=VISIT_ID
    ).model_copy(update={"obs_collection": None})

    with pytest.raises(IntegrityError, match="obs_collection"):
        await EnrichmentOutputStore(db_session).write(
            original_visit.model_copy(update={"skyRotation": 201.0}),
            [
                original_detector.model_copy(update={"seeing": 2.0}),
                new_detector,
            ],
            [
                original_obscore.model_copy(update={"obs_collection": "new"}),
                new_obscore,
                invalid_obscore,
            ],
        )

    saved_visit = await visits.get_by_visit_id(INSTRUMENT, VISIT_ID)
    assert saved_visit.skyRotation == original_visit.skyRotation
    saved_detectors = await detectors.get_by_visit_id(INSTRUMENT, VISIT_ID)
    assert [record.detectorId for record in saved_detectors] == [DETECTOR_ID]
    assert saved_detectors[0].seeing == pytest.approx(original_detector.seeing)
    saved_obscore = await obscore.get_by_obs_id(original_obscore.obs_id)
    assert saved_obscore.obs_collection == original_obscore.obs_collection
    with pytest.raises(UnknownObsCoreRecordError):
        await obscore.get_by_obs_id(new_obscore.obs_id)
    with pytest.raises(UnknownObsCoreRecordError):
        await obscore.get_by_obs_id(invalid_obscore.obs_id)
