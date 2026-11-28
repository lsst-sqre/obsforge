"""Add visit and visitdetector tables.

Revision ID: 8d4e5f607192
Revises: 7c3d4e5f6081
Create Date: 2026-11-25 00:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8d4e5f607192"
down_revision: str | None = "7c3d4e5f6081"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "visit",
        sa.Column("instrument", sa.Text(), nullable=False),
        sa.Column(
            "visitId", sa.BigInteger(), autoincrement=False, nullable=False
        ),
        sa.Column("visit", sa.BigInteger(), nullable=False),
        sa.Column("physical_filter", sa.String(length=4), nullable=True),
        sa.Column("band", sa.String(length=1), nullable=True),
        sa.Column("ra", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("dec", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("decl", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("skyRotation", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("azimuth", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("altitude", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("zenithDistance", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("airmass", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("expTime", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("expMidpt", sa.DateTime(), nullable=True),
        sa.Column("expMidptMJD", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("obsStart", sa.DateTime(), nullable=True),
        sa.Column("obsStartMJD", sa.DOUBLE_PRECISION(), nullable=True),
        sa.PrimaryKeyConstraint("instrument", "visitId"),
        sa.UniqueConstraint(
            "instrument", "visit", name="visit_instrument_visit_key"
        ),
    )
    op.create_table(
        "visitdetector",
        sa.Column("instrument", sa.Text(), nullable=False),
        sa.Column(
            "detectorId", sa.BigInteger(), autoincrement=False, nullable=False
        ),
        sa.Column(
            "visitId", sa.BigInteger(), autoincrement=False, nullable=False
        ),
        sa.Column("physical_filter", sa.String(length=32), nullable=True),
        sa.Column("band", sa.String(length=32), nullable=True),
        sa.Column("ra", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("dec", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("pixelScale", sa.REAL(), nullable=True),
        sa.Column("zenithDistance", sa.REAL(), nullable=True),
        sa.Column("expTime", sa.REAL(), nullable=True),
        sa.Column("zeroPoint", sa.REAL(), nullable=True),
        sa.Column("psfSigma", sa.REAL(), nullable=True),
        sa.Column("psfArea", sa.REAL(), nullable=True),
        sa.Column("psfIxx", sa.REAL(), nullable=True),
        sa.Column("psfIyy", sa.REAL(), nullable=True),
        sa.Column("psfIxy", sa.REAL(), nullable=True),
        sa.Column("skyBg", sa.REAL(), nullable=True),
        sa.Column("skyNoise", sa.REAL(), nullable=True),
        sa.Column("psfAdaptiveThresholdValue", sa.REAL(), nullable=True),
        sa.Column(
            "psfAdaptiveIncludeThresholdMultiplier",
            sa.REAL(),
            nullable=True,
        ),
        sa.Column("nShapeletsStar", sa.Integer(), nullable=True),
        sa.Column("shapeletsOnlyIqScore", sa.REAL(), nullable=True),
        sa.Column("shapeletsIqScore", sa.REAL(), nullable=True),
        sa.Column(
            "centroidDiffShapeletsVsSlotMedian", sa.REAL(), nullable=True
        ),
        sa.Column("shapeletsStarEMedian", sa.REAL(), nullable=True),
        sa.Column(
            "shapeletsStarUnNormalizedEMedian", sa.REAL(), nullable=True
        ),
        sa.Column("refCatSourceDensity", sa.REAL(), nullable=True),
        sa.Column("astromOffsetMean", sa.REAL(), nullable=True),
        sa.Column("astromOffsetStd", sa.REAL(), nullable=True),
        sa.Column("nPsfStar", sa.Integer(), nullable=True),
        sa.Column("psfStarDeltaE1Median", sa.REAL(), nullable=True),
        sa.Column("psfStarDeltaE2Median", sa.REAL(), nullable=True),
        sa.Column("psfStarDeltaE1Scatter", sa.REAL(), nullable=True),
        sa.Column("psfStarDeltaE2Scatter", sa.REAL(), nullable=True),
        sa.Column("psfStarDeltaSizeMedian", sa.REAL(), nullable=True),
        sa.Column("psfStarDeltaSizeScatter", sa.REAL(), nullable=True),
        sa.Column("psfStarScaledDeltaSizeScatter", sa.REAL(), nullable=True),
        sa.Column("psfTraceRadiusDelta", sa.REAL(), nullable=True),
        sa.Column("psfApFluxDelta", sa.REAL(), nullable=True),
        sa.Column("psfApCorrSigmaScaledDelta", sa.REAL(), nullable=True),
        sa.Column("maxDistToNearestPsf", sa.REAL(), nullable=True),
        sa.Column("starEMedian", sa.REAL(), nullable=True),
        sa.Column("starUnNormalizedEMedian", sa.REAL(), nullable=True),
        sa.Column("starComa1Median", sa.REAL(), nullable=True),
        sa.Column("starComa2Median", sa.REAL(), nullable=True),
        sa.Column("starTrefoil1Median", sa.REAL(), nullable=True),
        sa.Column("starTrefoil2Median", sa.REAL(), nullable=True),
        sa.Column("starKurtosisMedian", sa.REAL(), nullable=True),
        sa.Column("starE41Median", sa.REAL(), nullable=True),
        sa.Column("starE42Median", sa.REAL(), nullable=True),
        sa.Column("effTime", sa.REAL(), nullable=True),
        sa.Column("effTimePsfSigmaScale", sa.REAL(), nullable=True),
        sa.Column("effTimeSkyBgScale", sa.REAL(), nullable=True),
        sa.Column("effTimeZeroPointScale", sa.REAL(), nullable=True),
        sa.Column("magLim", sa.REAL(), nullable=True),
        sa.Column("decl", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("ccdVisitId", sa.BigInteger(), nullable=True),
        sa.Column("detector", sa.BigInteger(), nullable=False),
        sa.Column("seeing", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("skyRotation", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("expMidpt", sa.DateTime(), nullable=True),
        sa.Column("expMidptMJD", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("obsStart", sa.DateTime(), nullable=True),
        sa.Column("obsStartMJD", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("darkTime", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("xSize", sa.Integer(), nullable=True),
        sa.Column("ySize", sa.Integer(), nullable=True),
        sa.Column("llcra", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("llcdec", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("ulcra", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("ulcdec", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("urcra", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("urcdec", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("lrcra", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("lrcdec", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column(
            "wcsPreliminaryDetectorPointingResidual",
            sa.DOUBLE_PRECISION(),
            nullable=True,
        ),
        sa.Column(
            "wcsPreliminaryVisitPointingResidual",
            sa.DOUBLE_PRECISION(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["instrument", "visitId"], ["visit.instrument", "visit.visitId"]
        ),
        sa.PrimaryKeyConstraint("instrument", "visitId", "detectorId"),
    )


def downgrade() -> None:
    op.drop_table("visitdetector")
    op.drop_table("visit")
