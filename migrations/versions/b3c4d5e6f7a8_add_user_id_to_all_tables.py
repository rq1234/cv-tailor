"""add user_id to all tables

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-02-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Placeholder UUID for existing data — reassign after first real user signs up.
PLACEHOLDER_USER_ID = "00000000-0000-0000-0000-000000000000"

TABLES = [
    "cv_uploads",
    "cv_profiles",
    "work_experiences",
    "education",
    "projects",
    "skills",
    "activities",
    "unclassified_blocks",
    "applications",
    "cv_versions",
    "tailoring_rules",
]


def upgrade() -> None:
    # Step 1: Add nullable user_id column to all tables
    for table in TABLES:
        op.add_column(table, sa.Column("user_id", UUID(as_uuid=True), nullable=True))

    # Step 2: Backfill existing rows with placeholder UUID
    for table in TABLES:
        op.execute(
            f"UPDATE {table} SET user_id = '{PLACEHOLDER_USER_ID}' WHERE user_id IS NULL"
        )

    # Step 3: Make NOT NULL and add index
    for table in TABLES:
        op.alter_column(table, "user_id", nullable=False)
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])


def downgrade() -> None:
    for table in TABLES:
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_column(table, "user_id")
