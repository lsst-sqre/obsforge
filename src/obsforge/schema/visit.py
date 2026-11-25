"""SQLAlchemy schemas for visit metadata tables."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, REAL
from sqlalchemy.orm import Mapped, mapped_column

from .base import SchemaBase

__all__ = ["Visit", "VisitDetector"]


class Visit(SchemaBase):
    """Metadata about one telescope visit."""

    __tablename__ = "Visit"

    visitId: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )
    visit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    physical_filter: Mapped[str | None] = mapped_column(
        String(4), nullable=True
    )
    band: Mapped[str | None] = mapped_column(String(1), nullable=True)
    ra: Mapped[float | None] = mapped_column(DOUBLE_PRECISION, nullable=True)
    dec: Mapped[float | None] = mapped_column(DOUBLE_PRECISION, nullable=True)
    decl: Mapped[float | None] = mapped_column(DOUBLE_PRECISION, nullable=True)
    skyRotation: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    azimuth: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    altitude: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    zenithDistance: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    airmass: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    expTime: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    expMidpt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    expMidptMJD: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    obsStart: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    obsStartMJD: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )

    __table_args__ = (UniqueConstraint("visit", name="visit_visit_key"),)


class VisitDetector(SchemaBase):
    """Per-detector metadata and metrics for one visit."""

    __tablename__ = "VisitDetector"

    detectorId: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )
    visitId: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("Visit.visitId"),
        nullable=False,
    )
    physical_filter: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    band: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ra: Mapped[float | None] = mapped_column(DOUBLE_PRECISION, nullable=True)
    dec: Mapped[float | None] = mapped_column(DOUBLE_PRECISION, nullable=True)
    pixelScale: Mapped[float | None] = mapped_column(REAL, nullable=True)
    zenithDistance: Mapped[float | None] = mapped_column(REAL, nullable=True)
    expTime: Mapped[float | None] = mapped_column(REAL, nullable=True)
    zeroPoint: Mapped[float | None] = mapped_column(REAL, nullable=True)
    psfSigma: Mapped[float | None] = mapped_column(REAL, nullable=True)
    psfArea: Mapped[float | None] = mapped_column(REAL, nullable=True)
    psfIxx: Mapped[float | None] = mapped_column(REAL, nullable=True)
    psfIyy: Mapped[float | None] = mapped_column(REAL, nullable=True)
    psfIxy: Mapped[float | None] = mapped_column(REAL, nullable=True)
    skyBg: Mapped[float | None] = mapped_column(REAL, nullable=True)
    skyNoise: Mapped[float | None] = mapped_column(REAL, nullable=True)
    psfAdaptiveThresholdValue: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    psfAdaptiveIncludeThresholdMultiplier: Mapped[float | None] = (
        mapped_column(REAL, nullable=True)
    )
    nShapeletsStar: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shapeletsOnlyIqScore: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    shapeletsIqScore: Mapped[float | None] = mapped_column(REAL, nullable=True)
    centroidDiffShapeletsVsSlotMedian: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    shapeletsStarEMedian: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    shapeletsStarUnNormalizedEMedian: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    refCatSourceDensity: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    astromOffsetMean: Mapped[float | None] = mapped_column(REAL, nullable=True)
    astromOffsetStd: Mapped[float | None] = mapped_column(REAL, nullable=True)
    nPsfStar: Mapped[int | None] = mapped_column(Integer, nullable=True)
    psfStarDeltaE1Median: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    psfStarDeltaE2Median: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    psfStarDeltaE1Scatter: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    psfStarDeltaE2Scatter: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    psfStarDeltaSizeMedian: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    psfStarDeltaSizeScatter: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    psfStarScaledDeltaSizeScatter: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    psfTraceRadiusDelta: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    psfApFluxDelta: Mapped[float | None] = mapped_column(REAL, nullable=True)
    psfApCorrSigmaScaledDelta: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    maxDistToNearestPsf: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    starEMedian: Mapped[float | None] = mapped_column(REAL, nullable=True)
    starUnNormalizedEMedian: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    starComa1Median: Mapped[float | None] = mapped_column(REAL, nullable=True)
    starComa2Median: Mapped[float | None] = mapped_column(REAL, nullable=True)
    starTrefoil1Median: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    starTrefoil2Median: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    starKurtosisMedian: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    starE41Median: Mapped[float | None] = mapped_column(REAL, nullable=True)
    starE42Median: Mapped[float | None] = mapped_column(REAL, nullable=True)
    effTime: Mapped[float | None] = mapped_column(REAL, nullable=True)
    effTimePsfSigmaScale: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    effTimeSkyBgScale: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    effTimeZeroPointScale: Mapped[float | None] = mapped_column(
        REAL, nullable=True
    )
    magLim: Mapped[float | None] = mapped_column(REAL, nullable=True)
    decl: Mapped[float | None] = mapped_column(DOUBLE_PRECISION, nullable=True)
    ccdVisitId: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    detector: Mapped[int] = mapped_column(BigInteger, nullable=False)
    seeing: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    skyRotation: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    expMidpt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    expMidptMJD: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    obsStart: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    obsStartMJD: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    darkTime: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    xSize: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ySize: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llcra: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    llcdec: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    ulcra: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    ulcdec: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    urcra: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    urcdec: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    lrcra: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    lrcdec: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )
    wcsPreliminaryDetectorPointingResidual: Mapped[float | None] = (
        mapped_column(DOUBLE_PRECISION, nullable=True)
    )
    wcsPreliminaryVisitPointingResidual: Mapped[float | None] = mapped_column(
        DOUBLE_PRECISION, nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "visitId",
            "detector",
            name="visit_detector_visit_detector_key",
        ),
        Index("visit_detector_by_visit_id", "visitId"),
    )
