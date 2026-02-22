"""add outcome to applications

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-02-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("outcome", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_applications_outcome",
        "applications",
        "outcome IS NULL OR outcome IN ('applied', 'interview', 'offer', 'rejected', 'withdrawn')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_applications_outcome", "applications", type_="check")
    op.drop_column("applications", "outcome")
