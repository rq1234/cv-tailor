"""add baseline_ats_score, baseline_ats_warnings, gap_analysis to cv_versions

Revision ID: i1j2k3l4m5n6
Revises: h9i0j1k2l3m4
Create Date: 2026-02-26 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision: str = "i1j2k3l4m5n6"
down_revision: Union[str, None] = "h9i0j1k2l3m4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cv_versions",
        sa.Column("baseline_ats_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "cv_versions",
        sa.Column("baseline_ats_warnings", JSONB(), nullable=True),
    )
    op.add_column(
        "cv_versions",
        sa.Column("gap_analysis", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cv_versions", "gap_analysis")
    op.drop_column("cv_versions", "baseline_ats_warnings")
    op.drop_column("cv_versions", "baseline_ats_score")
