"""add missing indexes for FK columns and query patterns

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-02-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # FK columns used in WHERE clauses — seq-scanned on every upload query otherwise
    op.create_index("ix_work_experiences_upload_source_id", "work_experiences", ["upload_source_id"])
    op.create_index("ix_education_upload_source_id", "education", ["upload_source_id"])
    op.create_index("ix_projects_upload_source_id", "projects", ["upload_source_id"])
    op.create_index("ix_activities_upload_source_id", "activities", ["upload_source_id"])

    # cv_versions.application_id: every tailor-result lookup filters on this
    op.create_index("ix_cv_versions_application_id", "cv_versions", ["application_id"])

    # cv_versions.created_at: ORDER BY DESC on every result fetch
    op.create_index("ix_cv_versions_created_at", "cv_versions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_cv_versions_created_at", table_name="cv_versions")
    op.drop_index("ix_cv_versions_application_id", table_name="cv_versions")
    op.drop_index("ix_activities_upload_source_id", table_name="activities")
    op.drop_index("ix_projects_upload_source_id", table_name="projects")
    op.drop_index("ix_education_upload_source_id", table_name="education")
    op.drop_index("ix_work_experiences_upload_source_id", table_name="work_experiences")
