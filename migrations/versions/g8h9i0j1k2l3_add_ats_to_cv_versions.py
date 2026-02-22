"""add ats_score and ats_warnings to cv_versions

Revision ID: g8h9i0j1k2l3
Revises: f7a8b9c0d1e2
Create Date: 2026-02-22 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision: str = "g8h9i0j1k2l3"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cv_versions",
        sa.Column("ats_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "cv_versions",
        sa.Column("ats_warnings", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cv_versions", "ats_warnings")
    op.drop_column("cv_versions", "ats_score")
