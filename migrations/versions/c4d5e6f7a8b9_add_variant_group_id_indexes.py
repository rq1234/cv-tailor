"""add variant_group_id indexes

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-02-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_work_experiences_variant_group_id",
        "work_experiences",
        ["variant_group_id"],
    )
    op.create_index(
        "ix_projects_variant_group_id",
        "projects",
        ["variant_group_id"],
    )
    op.create_index(
        "ix_activities_variant_group_id",
        "activities",
        ["variant_group_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_work_experiences_variant_group_id", table_name="work_experiences")
    op.drop_index("ix_projects_variant_group_id", table_name="projects")
    op.drop_index("ix_activities_variant_group_id", table_name="activities")
