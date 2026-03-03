"""add pipeline fields to applications

Revision ID: k3l4m5n6o7p8
Revises: j2k3l4m5n6o7
Create Date: 2026-03-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "k3l4m5n6o7p8"
down_revision: Union[str, None] = "j2k3l4m5n6o7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pipeline_started_at: acts as a distributed lock (set when tailoring starts, cleared on finish/error)
    op.add_column(
        "applications",
        sa.Column("pipeline_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    # pipeline_error: stores the last pipeline failure message and which stage it failed at
    op.add_column(
        "applications",
        sa.Column("pipeline_error", sa.Text(), nullable=True),
    )
    # pipeline_selection: persists the AI-selected experience/project IDs after stage 2,
    # enabling per-stage retry without re-running selection
    op.add_column(
        "applications",
        sa.Column("pipeline_selection", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applications", "pipeline_selection")
    op.drop_column("applications", "pipeline_error")
    op.drop_column("applications", "pipeline_started_at")
