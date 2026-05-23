"""Initial schema.

Revision ID: 4f8a2b6c9d10
Revises:
Create Date: 2026-05-22 00:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f8a2b6c9d10"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "enrichment_job",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("visit_id", sa.Text(), nullable=False),
        sa.Column("instrument", sa.Text(), nullable=False),
        sa.Column("day_obs", sa.Integer(), nullable=False),
        sa.Column(
            "phase",
            sa.Enum(
                "PENDING",
                "QUEUED",
                "EXECUTING",
                "COMPLETED",
                "ERROR",
                name="enrichmentjobphase",
            ),
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "registration_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "attempt_count >= 0", name="enrichment_job_attempt_count_check"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("visit_id", name="enrichment_job_visit_id_key"),
    )
    op.create_index(
        "enrichment_job_by_instrument_day_obs",
        "enrichment_job",
        ["instrument", "day_obs"],
        unique=False,
    )
    op.create_index(
        "enrichment_job_by_phase_updated_at",
        "enrichment_job",
        ["phase", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "enrichment_job_by_phase_updated_at", table_name="enrichment_job"
    )
    op.drop_index(
        "enrichment_job_by_instrument_day_obs", table_name="enrichment_job"
    )
    op.drop_table("enrichment_job")
    sa.Enum(name="enrichmentjobphase").drop(op.get_bind(), checkfirst=True)
