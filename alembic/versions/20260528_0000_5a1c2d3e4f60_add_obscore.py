"""Add ObsCore schema.

Revision ID: 5a1c2d3e4f60
Revises: 4f8a2b6c9d10
Create Date: 2026-05-28 00:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5a1c2d3e4f60"
down_revision: str | None = "4f8a2b6c9d10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS ivoa")
    op.create_table(
        "ObsCore",
        sa.Column(
            "dataproduct_type",
            sa.Text(),
            server_default="image",
            nullable=False,
        ),
        sa.Column("dataproduct_subtype", sa.Text(), nullable=False),
        sa.Column(
            "calib_level",
            sa.Integer(),
            server_default=sa.text("2"),
            nullable=False,
        ),
        sa.Column("target_name", sa.Text(), nullable=True),
        sa.Column("obs_id", sa.Text(), nullable=False),
        sa.Column(
            "obs_collection",
            sa.Text(),
            server_default="Prompt Processing Visits",
            nullable=False,
        ),
        sa.Column("obs_publisher_did", sa.Text(), nullable=False),
        sa.Column("access_url", sa.Text(), nullable=False),
        sa.Column(
            "access_format",
            sa.Text(),
            server_default="application/x-votable+xml;content=datalink",
            nullable=False,
        ),
        sa.Column("access_estsize", sa.Integer(), nullable=True),
        sa.Column("s_ra", sa.Float(), nullable=False),
        sa.Column("s_dec", sa.Float(), nullable=False),
        sa.Column(
            "s_fov",
            sa.Float(),
            server_default=sa.text("3.5"),
            nullable=False,
        ),
        sa.Column("s_region", sa.Text(), nullable=False),
        sa.Column("s_resolution", sa.Float(), nullable=False),
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
        sa.Column(
            "o_ucd",
            sa.Text(),
            server_default="phot.flux",
            nullable=False,
        ),
        sa.Column("pol_xel", sa.BigInteger(), nullable=True),
        sa.Column(
            "instrument_name",
            sa.Text(),
            server_default="LSSTCAM",
            nullable=False,
        ),
        sa.Column(
            "facility_name",
            sa.Text(),
            server_default="Rubin:Simonyi",
            nullable=False,
        ),
        sa.Column("visit_id", sa.Text(), nullable=False),
        sa.Column("band", sa.Text(), nullable=False),
        sa.Column("physical_filter", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "dataproduct_type = 'image'",
            name="obscore_dataproduct_type_check",
        ),
        sa.CheckConstraint(
            "calib_level = 2", name="obscore_calib_level_check"
        ),
        sa.CheckConstraint(
            "target_name IS NULL", name="obscore_target_name_null_check"
        ),
        sa.CheckConstraint(
            "obs_collection = 'Prompt Processing Visits'",
            name="obscore_obs_collection_check",
        ),
        sa.CheckConstraint(
            "access_format = 'application/x-votable+xml;content=datalink'",
            name="obscore_access_format_check",
        ),
        sa.CheckConstraint(
            "access_estsize IS NULL",
            name="obscore_access_estsize_null_check",
        ),
        sa.CheckConstraint("s_fov = 3.5", name="obscore_s_fov_check"),
        sa.CheckConstraint("s_xel1 IS NULL", name="obscore_s_xel1_null_check"),
        sa.CheckConstraint("s_xel2 IS NULL", name="obscore_s_xel2_null_check"),
        sa.CheckConstraint("t_xel IS NULL", name="obscore_t_xel_null_check"),
        sa.CheckConstraint(
            "t_resolution IS NULL",
            name="obscore_t_resolution_null_check",
        ),
        sa.CheckConstraint("em_xel IS NULL", name="obscore_em_xel_null_check"),
        sa.CheckConstraint(
            "em_res_power IS NULL",
            name="obscore_em_res_power_null_check",
        ),
        sa.CheckConstraint("o_ucd = 'phot.flux'", name="obscore_o_ucd_check"),
        sa.CheckConstraint(
            "pol_xel IS NULL", name="obscore_pol_xel_null_check"
        ),
        sa.CheckConstraint(
            "instrument_name = 'LSSTCAM'",
            name="obscore_instrument_name_check",
        ),
        sa.CheckConstraint(
            "facility_name = 'Rubin:Simonyi'",
            name="obscore_facility_name_check",
        ),
        sa.PrimaryKeyConstraint("visit_id"),
        schema="ivoa",
    )


def downgrade() -> None:
    op.drop_table("ObsCore", schema="ivoa")
