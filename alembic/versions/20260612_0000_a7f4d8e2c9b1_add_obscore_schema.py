"""Add ObsCore schema.

Revision ID: a7f4d8e2c9b1
Revises: 4f8a2b6c9d10
Create Date: 2026-06-12 00:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7f4d8e2c9b1"
down_revision: str | None = "4f8a2b6c9d10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS ivoa")
    op.create_table(
        "ObsCore",
        sa.Column("dataproduct_type", sa.Text(), nullable=False),
        sa.Column("dataproduct_subtype", sa.Text(), nullable=False),
        sa.Column("calib_level", sa.Integer(), nullable=False),
        sa.Column("target_name", sa.Text(), nullable=True),
        sa.Column("obs_id", sa.Text(), nullable=False),
        sa.Column("obs_collection", sa.Text(), nullable=False),
        sa.Column("obs_publisher_did", sa.Text(), nullable=False),
        sa.Column("access_url", sa.Text(), nullable=False),
        sa.Column("access_format", sa.Text(), nullable=False),
        sa.Column("access_estsize", sa.Integer(), nullable=True),
        sa.Column("s_ra", sa.Float(), nullable=False),
        sa.Column("s_dec", sa.Float(), nullable=False),
        sa.Column("s_fov", sa.Float(), nullable=False),
        sa.Column("s_region", sa.Text(), nullable=False),
        sa.Column("s_resolution", sa.Float(), nullable=True),
        sa.Column("s_xel1", sa.BigInteger(), nullable=True),
        sa.Column("s_xel2", sa.BigInteger(), nullable=True),
        sa.Column("t_xel", sa.BigInteger(), nullable=True),
        sa.Column("t_min", sa.Float(), nullable=False),
        sa.Column("t_max", sa.Float(), nullable=False),
        sa.Column("t_exptime", sa.Float(), nullable=False),
        sa.Column("t_resolution", sa.Float(), nullable=True),
        sa.Column("em_xel", sa.BigInteger(), nullable=True),
        sa.Column("em_min", sa.Float(), nullable=False),
        sa.Column("em_max", sa.Float(), nullable=False),
        sa.Column("em_res_power", sa.Float(), nullable=True),
        sa.Column("o_ucd", sa.Text(), nullable=False),
        sa.Column("pol_xel", sa.BigInteger(), nullable=True),
        sa.Column("instrument_name", sa.Text(), nullable=False),
        sa.Column("facility_name", sa.Text(), nullable=False),
        sa.Column("obs_title", sa.Text(), nullable=False),
        sa.Column("em_filter_name", sa.Text(), nullable=False),
        sa.Column("lsst_visit", sa.BigInteger(), nullable=False),
        sa.Column("lsst_detector", sa.BigInteger(), nullable=False),
        sa.Column("lsst_filter", sa.Text(), nullable=False),
        sa.Column("lsst_band", sa.Text(), nullable=False),
        sa.Column("lsst_patch", sa.BigInteger(), nullable=True),
        sa.Column("lsst_tract", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("obs_id"),
        schema="ivoa",
    )


def downgrade() -> None:
    op.drop_table("ObsCore", schema="ivoa")
