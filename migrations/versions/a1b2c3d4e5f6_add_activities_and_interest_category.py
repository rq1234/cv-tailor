"""add activities table and interest skill category

Revision ID: a1b2c3d4e5f6
Revises: 88264ac1bfd6
Create Date: 2026-02-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import pgvector.sqlalchemy.vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '88264ac1bfd6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create activities table
    op.create_table('activities',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('upload_source_id', sa.UUID(), nullable=True),
        sa.Column('organization', sa.Text(), nullable=True),
        sa.Column('role_title', sa.Text(), nullable=True),
        sa.Column('location', sa.Text(), nullable=True),
        sa.Column('date_start', sa.Date(), nullable=True),
        sa.Column('date_end', sa.Date(), nullable=True),
        sa.Column('is_current', sa.Boolean(), nullable=False),
        sa.Column('organization_confidence', sa.Float(), nullable=True),
        sa.Column('dates_confidence', sa.Float(), nullable=True),
        sa.Column('bullets', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('raw_block', sa.Text(), nullable=False),
        sa.Column('domain_tags', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('skill_tags', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1536), nullable=True),
        sa.Column('variant_group_id', sa.UUID(), nullable=True),
        sa.Column('is_primary_variant', sa.Boolean(), nullable=False),
        sa.Column('similarity_score', sa.Float(), nullable=True),
        sa.Column('is_reviewed', sa.Boolean(), nullable=False),
        sa.Column('needs_review', sa.Boolean(), nullable=False),
        sa.Column('review_reason', sa.Text(), nullable=True),
        sa.Column('user_corrections', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['upload_source_id'], ['cv_uploads.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Add selected_activities column to cv_versions
    op.add_column('cv_versions',
        sa.Column('selected_activities', postgresql.ARRAY(sa.UUID()), nullable=True)
    )

    # Update skills category constraint to include 'interest'
    op.drop_constraint('ck_skills_category', 'skills', type_='check')
    op.create_check_constraint(
        'ck_skills_category',
        'skills',
        "category IN ('technical', 'language', 'tool', 'soft', 'other', 'certification', 'framework', 'interest')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Revert skills category constraint
    op.drop_constraint('ck_skills_category', 'skills', type_='check')
    op.create_check_constraint(
        'ck_skills_category',
        'skills',
        "category IN ('technical', 'language', 'tool', 'soft', 'other', 'certification', 'framework')",
    )

    # Remove selected_activities column
    op.drop_column('cv_versions', 'selected_activities')

    # Drop activities table
    op.drop_table('activities')
