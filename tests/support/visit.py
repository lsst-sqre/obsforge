"""Test helpers for realistic Visit and VisitDetector records."""

from collections.abc import Mapping, Sequence
from datetime import datetime
from math import nan
from typing import Any

import numpy as np
from astropy.table import Table

from obsforge.models import VisitDetectorUpsert, VisitUpsert

__all__ = [
    "CCD_VISIT_ID",
    "DETECTOR_ID",
    "INSTRUMENT",
    "SECOND_DETECTOR_ID",
    "SECOND_INSTRUMENT",
    "VISIT_ID",
    "make_visit_detector_table",
    "make_visit_detector_upsert",
    "make_visit_table",
    "make_visit_upsert",
]

VISIT_ID = 2026110400269
INSTRUMENT = "LSSTCam"
SECOND_INSTRUMENT = "LATISS"
DETECTOR_ID = 99
SECOND_DETECTOR_ID = 100
CCD_VISIT_ID = 51598396771

_EXP_MIDPT = datetime(2026, 11, 5, 4, 40, 22, 317658)
_OBS_START = datetime(2026, 11, 5, 4, 40, 7, 317396)
_EXP_MIDPT_NS = np.datetime64("2026-11-05T04:40:22.317658362", "ns")
_OBS_START_NS = np.datetime64("2026-11-05T04:40:07.317396817", "ns")

_VISIT_VALUES: dict[str, Any] = {
    "visitId": VISIT_ID,
    "visit": VISIT_ID,
    "physical_filter": "r_57",
    "band": "r",
    "ra": 59.3436829534788,
    "dec": -50.9206695961387,
    "decl": -50.9206695961387,
    "skyRotation": 203.302231459618,
    "azimuth": 154.484782163507,
    "altitude": 66.241281600753,
    "zenithDistance": 23.758718399247,
    "airmass": 1.09240193849216,
    "expTime": 30.0005230903625,
    "expMidpt": _EXP_MIDPT,
    "expMidptMJD": 61349.194702750676,
    "obsStart": _OBS_START,
    "obsStartMJD": 61349.19452913654,
}

_VISIT_DETECTOR_VALUES: dict[str, Any] = {
    "detectorId": DETECTOR_ID,
    "visitId": VISIT_ID,
    "physical_filter": "r_57",
    "band": "r",
    "ra": 60.17058403353784,
    "dec": -50.88736235081859,
    "pixelScale": 0.20009875297546387,
    "zenithDistance": 23.998197555541992,
    "expTime": 30.00052261352539,
    "zeroPoint": 32.09132385253906,
    "psfSigma": 3.856926202774048,
    "psfArea": 222.49093627929688,
    "psfIxx": 15.49645709991455,
    "psfIyy": 14.280294418334961,
    "psfIxy": -0.04658737778663635,
    "skyBg": 902.7697143554688,
    "skyNoise": 30.64198875427246,
    "psfAdaptiveThresholdValue": 10.0,
    "psfAdaptiveIncludeThresholdMultiplier": 5.0,
    "nShapeletsStar": 20,
    "shapeletsOnlyIqScore": 0.00017784938972909003,
    "shapeletsIqScore": 0.0002247098891530186,
    "centroidDiffShapeletsVsSlotMedian": 0.10766542702913284,
    "shapeletsStarEMedian": 0.021966874599456787,
    "shapeletsStarUnNormalizedEMedian": 0.9720441102981567,
    "refCatSourceDensity": 3608.039794921875,
    "astromOffsetMean": 0.009986107237637043,
    "astromOffsetStd": 0.0055314404889941216,
    "nPsfStar": 89,
    "psfStarDeltaE1Median": 0.00022055953741073608,
    "psfStarDeltaE2Median": -0.0003860252909362316,
    "psfStarDeltaE1Scatter": 0.008088266476988792,
    "psfStarDeltaE2Scatter": 0.007786925882101059,
    "psfStarDeltaSizeMedian": -0.00019583693938329816,
    "psfStarDeltaSizeScatter": 0.02226710319519043,
    "psfStarScaledDeltaSizeScatter": 0.005757183767855167,
    "psfTraceRadiusDelta": 0.053464099764823914,
    "psfApFluxDelta": 0.0034147105179727077,
    "psfApCorrSigmaScaledDelta": 0.00400592340156436,
    "maxDistToNearestPsf": 789.022705078125,
    "starEMedian": 0.040347397327423096,
    "starUnNormalizedEMedian": 1.1962352991104126,
    "starComa1Median": nan,
    "starComa2Median": nan,
    "starTrefoil1Median": nan,
    "starTrefoil2Median": nan,
    "starKurtosisMedian": nan,
    "starE41Median": nan,
    "starE42Median": nan,
    "effTime": 6.552976608276367,
    "effTimePsfSigmaScale": 0.16359367966651917,
    "effTimeSkyBgScale": 1.0949827432632446,
    "effTimeZeroPointScale": 0.8294715881347656,
    "magLim": 23.69414710998535,
    "decl": -50.88736235081859,
    "ccdVisitId": CCD_VISIT_ID,
    "detector": DETECTOR_ID,
    "seeing": 1.8173703439476878,
    "skyRotation": 203.302231459618,
    "expMidpt": _EXP_MIDPT,
    "expMidptMJD": 61349.194702750676,
    "obsStart": _OBS_START,
    "obsStartMJD": 61349.19452913654,
    "darkTime": 30.9286,
    "xSize": 4095,
    "ySize": 4003,
    "llcra": 60.07249925114238,
    "llcdec": -50.74071581306461,
    "ulcra": 60.40478296881343,
    "ulcdec": -50.82840673565947,
    "urcra": 60.269272087909016,
    "urcdec": -51.033919891835346,
    "lrcra": 59.9357507561287,
    "lrcdec": -50.945856506814714,
    "wcsPreliminaryDetectorPointingResidual": 0.24023500314399332,
    "wcsPreliminaryVisitPointingResidual": 0.24023500314399332,
}

_VISIT_DTYPES = {
    "visitId": "int64",
    "visit": "int64",
    "physical_filter": "U4",
    "band": "U1",
    "ra": "float64",
    "dec": "float64",
    "decl": "float64",
    "skyRotation": "float64",
    "azimuth": "float64",
    "altitude": "float64",
    "zenithDistance": "float64",
    "airmass": "float64",
    "expTime": "float64",
    "expMidpt": "datetime64[ns]",
    "expMidptMJD": "float64",
    "obsStart": "datetime64[ns]",
    "obsStartMJD": "float64",
}

_FLOAT32_DETECTOR_COLUMNS = {
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
    "shapeletsOnlyIqScore",
    "shapeletsIqScore",
    "centroidDiffShapeletsVsSlotMedian",
    "shapeletsStarEMedian",
    "shapeletsStarUnNormalizedEMedian",
    "refCatSourceDensity",
    "astromOffsetMean",
    "astromOffsetStd",
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
}
_INT32_DETECTOR_COLUMNS = {"nShapeletsStar", "nPsfStar", "xSize", "ySize"}
_INT64_DETECTOR_COLUMNS = {"detectorId", "visitId", "ccdVisitId", "detector"}
_DATETIME_DETECTOR_COLUMNS = {"expMidpt", "obsStart"}

_VISIT_DETECTOR_DTYPES = {
    name: (
        "U32"
        if name in {"physical_filter", "band"}
        else "float32"
        if name in _FLOAT32_DETECTOR_COLUMNS
        else "int32"
        if name in _INT32_DETECTOR_COLUMNS
        else "int64"
        if name in _INT64_DETECTOR_COLUMNS
        else "datetime64[ns]"
        if name in _DATETIME_DETECTOR_COLUMNS
        else "float64"
    )
    for name in _VISIT_DETECTOR_VALUES
}


def make_visit_upsert(**overrides: Any) -> VisitUpsert:
    """Make a complete, production-shaped Visit upsert model."""
    return VisitUpsert.model_validate(
        _VISIT_VALUES | {"instrument": INSTRUMENT} | overrides
    )


def make_visit_detector_upsert(**overrides: Any) -> VisitDetectorUpsert:
    """Make a complete, production-shaped VisitDetector upsert model."""
    return VisitDetectorUpsert.model_validate(
        _VISIT_DETECTOR_VALUES | {"instrument": INSTRUMENT} | overrides
    )


def make_visit_table(
    *, rows: Sequence[Mapping[str, Any]] | None = None
) -> Table:
    """Make a dtype-accurate Astropy visit table from row overrides."""
    defaults = _VISIT_VALUES | {
        "expMidpt": _EXP_MIDPT_NS,
        "obsStart": _OBS_START_NS,
    }
    return _make_table(defaults, _VISIT_DTYPES, rows)


def make_visit_detector_table(
    *, rows: Sequence[Mapping[str, Any]] | None = None
) -> Table:
    """Make a dtype-accurate Astropy detector table from row overrides."""
    defaults = _VISIT_DETECTOR_VALUES | {
        "expMidpt": _EXP_MIDPT_NS,
        "obsStart": _OBS_START_NS,
    }
    return _make_table(defaults, _VISIT_DETECTOR_DTYPES, rows)


def _make_table(
    defaults: Mapping[str, Any],
    dtypes: Mapping[str, str],
    rows: Sequence[Mapping[str, Any]] | None,
) -> Table:
    row_overrides = rows if rows is not None else [{}]
    columns = {
        name: np.asarray(
            [row.get(name, default) for row in row_overrides],
            dtype=dtypes[name],
        )
        for name, default in defaults.items()
    }
    return Table(columns)
