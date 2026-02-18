import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class CvUpload(Base):
    __tablename__ = "cv_uploads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    original_filename: Mapped[str | None] = mapped_column(Text)
    file_type: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text_quality: Mapped[float | None] = mapped_column(Float)
    parsing_status: Mapped[str] = mapped_column(Text, default="pending")
    parsing_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("file_type IN ('pdf', 'docx', 'paste')", name="ck_cv_uploads_file_type"),
        CheckConstraint(
            "parsing_status IN ('pending', 'partial', 'complete', 'failed')",
            name="ck_cv_uploads_parsing_status",
        ),
    )


class CvProfile(Base):
    __tablename__ = "cv_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    portfolio_url: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    name_confidence: Mapped[float | None] = mapped_column(Float)
    contact_confidence: Mapped[float | None] = mapped_column(Float)
    unstructured_extras: Mapped[dict | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class WorkExperience(Base):
    __tablename__ = "work_experiences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    upload_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cv_uploads.id")
    )
    company: Mapped[str | None] = mapped_column(Text)
    role_title: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    date_start: Mapped[date | None] = mapped_column(Date)
    date_end: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    company_confidence: Mapped[float | None] = mapped_column(Float)
    dates_confidence: Mapped[float | None] = mapped_column(Float)
    bullets: Mapped[dict] = mapped_column(JSONB, nullable=False)
    raw_block: Mapped[str] = mapped_column(Text, nullable=False)
    domain_tags: Mapped[list | None] = mapped_column(ARRAY(Text))
    skill_tags: Mapped[list | None] = mapped_column(ARRAY(Text))
    embedding = mapped_column(Vector(1536), nullable=True)
    variant_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    is_primary_variant: Mapped[bool] = mapped_column(Boolean, default=True)
    similarity_score: Mapped[float | None] = mapped_column(Float)
    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_reason: Mapped[str | None] = mapped_column(Text)
    user_corrections: Mapped[dict | None] = mapped_column(JSONB)


class Education(Base):
    __tablename__ = "education"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    upload_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cv_uploads.id")
    )
    institution: Mapped[str | None] = mapped_column(Text)
    degree: Mapped[str | None] = mapped_column(Text)
    grade: Mapped[str | None] = mapped_column(Text)
    date_start: Mapped[date | None] = mapped_column(Date)
    date_end: Mapped[date | None] = mapped_column(Date)
    location: Mapped[str | None] = mapped_column(Text)
    achievements: Mapped[dict | None] = mapped_column(JSONB)
    modules: Mapped[dict | None] = mapped_column(JSONB)
    raw_block: Mapped[str] = mapped_column(Text, nullable=False)
    dates_confidence: Mapped[float | None] = mapped_column(Float)
    institution_confidence: Mapped[float | None] = mapped_column(Float)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    upload_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cv_uploads.id")
    )
    name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    date_start: Mapped[date | None] = mapped_column(Date)
    date_end: Mapped[date | None] = mapped_column(Date)
    url: Mapped[str | None] = mapped_column(Text)
    bullets: Mapped[dict | None] = mapped_column(JSONB)
    raw_block: Mapped[str] = mapped_column(Text, nullable=False)
    domain_tags: Mapped[list | None] = mapped_column(ARRAY(Text))
    skill_tags: Mapped[list | None] = mapped_column(ARRAY(Text))
    embedding = mapped_column(Vector(1536), nullable=True)
    variant_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    is_primary_variant: Mapped[bool] = mapped_column(Boolean, default=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_name: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    proficiency: Mapped[str | None] = mapped_column(Text)
    domain_tags: Mapped[list | None] = mapped_column(ARRAY(Text))
    is_duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id")
    )

    __table_args__ = (
        CheckConstraint(
            "category IN ('technical', 'language', 'tool', 'soft', 'other', 'certification', 'framework', 'interest')",
            name="ck_skills_category",
        ),
    )


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    upload_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cv_uploads.id")
    )
    organization: Mapped[str | None] = mapped_column(Text)
    role_title: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    date_start: Mapped[date | None] = mapped_column(Date)
    date_end: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    organization_confidence: Mapped[float | None] = mapped_column(Float)
    dates_confidence: Mapped[float | None] = mapped_column(Float)
    bullets: Mapped[dict] = mapped_column(JSONB, nullable=False)
    raw_block: Mapped[str] = mapped_column(Text, nullable=False)
    domain_tags: Mapped[list | None] = mapped_column(ARRAY(Text))
    skill_tags: Mapped[list | None] = mapped_column(ARRAY(Text))
    embedding = mapped_column(Vector(1536), nullable=True)
    variant_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    is_primary_variant: Mapped[bool] = mapped_column(Boolean, default=True)
    similarity_score: Mapped[float | None] = mapped_column(Float)
    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_reason: Mapped[str | None] = mapped_column(Text)
    user_corrections: Mapped[dict | None] = mapped_column(JSONB)


class UnclassifiedBlock(Base):
    __tablename__ = "unclassified_blocks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    upload_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cv_uploads.id")
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    gpt_category_guess: Mapped[str | None] = mapped_column(Text)
    gpt_confidence: Mapped[float | None] = mapped_column(Float)
    user_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_as: Mapped[str | None] = mapped_column(Text)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    role_title: Mapped[str | None] = mapped_column(Text)
    jd_raw: Mapped[str] = mapped_column(Text, nullable=False)
    jd_parsed: Mapped[dict | None] = mapped_column(JSONB)
    jd_source: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="draft")
    include_report: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("jd_source IN ('paste', 'screenshot', 'url')", name="ck_applications_jd_source"),
        CheckConstraint(
            "status IN ('draft', 'tailoring', 'review', 'complete')",
            name="ck_applications_status",
        ),
    )


class CvVersion(Base):
    __tablename__ = "cv_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id")
    )
    selected_experiences: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    selected_education: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    selected_projects: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    selected_skills: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    selected_activities: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    diff_json: Mapped[dict | None] = mapped_column(JSONB)
    accepted_changes: Mapped[dict | None] = mapped_column(JSONB)
    rejected_changes: Mapped[dict | None] = mapped_column(JSONB)
    final_cv_json: Mapped[dict | None] = mapped_column(JSONB)
    pdf_path: Mapped[str | None] = mapped_column(Text)
    docx_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class TailoringRule(Base):
    __tablename__ = "tailoring_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
