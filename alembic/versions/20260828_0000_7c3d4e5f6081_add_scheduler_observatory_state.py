"""Add Scheduler observatory state telemetry.

Revision ID: 7c3d4e5f6081
Revises: 6b2c3d4e5f70
Create Date: 2026-08-28 00:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c3d4e5f6081"
down_revision: str | None = "6b2c3d4e5f70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS scheduler")
    op.create_table(
        "observatory_state",
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ra", sa.Float(), nullable=False),
        sa.Column("declination", sa.Float(), nullable=False),
        sa.Column("positionAngle", sa.Float(), nullable=False),
        sa.Column("parallacticAngle", sa.Float(), nullable=False),
        sa.Column("tracking", sa.Boolean(), nullable=False),
        sa.Column("telescopeAltitude", sa.Float(), nullable=False),
        sa.Column("telescopeAzimuth", sa.Float(), nullable=False),
        sa.Column("telescopeRotator", sa.Float(), nullable=False),
        sa.Column("domeAltitude", sa.Float(), nullable=False),
        sa.Column("domeAzimuth", sa.Float(), nullable=False),
        sa.Column("filterPosition", sa.Text(), nullable=False),
        sa.Column("filterMounted", sa.Text(), nullable=False),
        sa.Column("filterUnmounted", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("timestamp"),
        schema="scheduler",
    )


def downgrade() -> None:
    op.drop_table("observatory_state", schema="scheduler")
