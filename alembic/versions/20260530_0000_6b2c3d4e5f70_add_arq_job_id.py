"""Add arq job ID to enrichment jobs.

Revision ID: 6b2c3d4e5f70
Revises: 5a1c2d3e4f60
Create Date: 2026-05-30 00:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6b2c3d4e5f70"
down_revision: str | None = "5a1c2d3e4f60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "enrichment_job", sa.Column("arq_job_id", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("enrichment_job", "arq_job_id")
