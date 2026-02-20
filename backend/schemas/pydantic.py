"""Pydantic v2 models for all request/response shapes."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Shared config for all response schemas that are built from ORM objects
_ORM_CONFIG = ConfigDict(from_attributes=True)


# ── CV Upload ──────────────────────────────────────────────────────────
class CvUploadResponse(BaseModel):
    upload_id: uuid.UUID
    original_filename: str | None = Field(None, max_length=255)
    file_type: str = Field(max_length=10)
    raw_text_quality: float | None
    parsing_status: str = Field(max_length=50)
    parsing_notes: str | None = Field(None, max_length=1000)


class ParseSummary(BaseModel):
    upload_id: uuid.UUID
    cleanly_parsed_count: int
    needs_review: list[ReviewItem]
    unclassified_blocks: list[UnclassifiedBlockOut]
    duplicates: list[DuplicateGroup]


class ReviewItem(BaseModel):
    id: uuid.UUID
    table: str  # "work_experiences", "education", etc.
    field: str
    current_value: str | None
    confidence: float
    review_reason: str | None


class UnclassifiedBlockOut(BaseModel):
    id: uuid.UUID
    raw_text: str
    gpt_category_guess: str | None
    gpt_confidence: float | None


class DuplicateGroup(BaseModel):
    variant_group_id: uuid.UUID
    items: list[DuplicateItem]


class DuplicateItem(BaseModel):
    id: uuid.UUID
    company: str | None = None
    role_title: str | None = None
    similarity_score: float | None
    is_primary_variant: bool


# ── Experience Pool ────────────────────────────────────────────────────
class WorkExperienceOut(BaseModel):
    model_config = _ORM_CONFIG
    id: uuid.UUID
    company: str | None
    role_title: str | None
    location: str | None
    date_start: date | None
    date_end: date | None
    is_current: bool
    bullets: list | dict
    domain_tags: list[str] | None
    skill_tags: list[str] | None
    variant_group_id: uuid.UUID | None
    is_primary_variant: bool
    needs_review: bool
    review_reason: str | None


class WorkExperienceUpdate(BaseModel):
    company: str | None = None
    role_title: str | None = None
    location: str | None = None
    date_start: date | None = None
    date_end: date | None = None
    is_current: bool | None = None
    bullets: list | dict | None = None
    domain_tags: list[str] | None = None
    skill_tags: list[str] | None = None


class EducationOut(BaseModel):
    model_config = _ORM_CONFIG
    id: uuid.UUID
    institution: str | None
    degree: str | None
    grade: str | None
    date_start: date | None
    date_end: date | None
    location: str | None
    achievements: list | dict | None
    modules: list | dict | None
    needs_review: bool


class ProjectOut(BaseModel):
    model_config = _ORM_CONFIG
    id: uuid.UUID
    name: str | None
    description: str | None
    date_start: date | None
    date_end: date | None
    url: str | None
    bullets: list | dict | None
    domain_tags: list[str] | None
    skill_tags: list[str] | None
    variant_group_id: uuid.UUID | None = None
    is_primary_variant: bool = True
    needs_review: bool


class ActivityOut(BaseModel):
    model_config = _ORM_CONFIG
    id: uuid.UUID
    organization: str | None
    role_title: str | None
    location: str | None
    date_start: date | None
    date_end: date | None
    is_current: bool
    bullets: list | dict
    domain_tags: list[str] | None
    skill_tags: list[str] | None
    variant_group_id: uuid.UUID | None
    is_primary_variant: bool
    needs_review: bool
    review_reason: str | None


class ActivityUpdate(BaseModel):
    organization: str | None = None
    role_title: str | None = None
    location: str | None = None
    date_start: date | None = None
    date_end: date | None = None
    is_current: bool | None = None
    bullets: list | dict | None = None
    domain_tags: list[str] | None = None
    skill_tags: list[str] | None = None


class SkillOut(BaseModel):
    model_config = _ORM_CONFIG
    id: uuid.UUID
    name: str
    canonical_name: str | None
    category: str | None
    proficiency: str | None
    domain_tags: list[str] | None


class ExperiencePoolResponse(BaseModel):
    profile: CvProfileOut | None
    work_experiences: list[WorkExperienceOut]
    education: list[EducationOut]
    projects: list[ProjectOut]
    activities: list[ActivityOut]
    skills: list[SkillOut]


class CvProfileOut(BaseModel):
    model_config = _ORM_CONFIG
    id: uuid.UUID
    full_name: str | None
    email: str | None
    phone: str | None
    location: str | None
    linkedin_url: str | None
    portfolio_url: str | None
    summary: str | None


# ── Applications ───────────────────────────────────────────────────────
class ApplicationCreate(BaseModel):
    company_name: str = Field(max_length=200)
    role_title: str | None = Field(None, max_length=200)
    jd_raw: str = Field(..., min_length=1, max_length=50_000)
    jd_source: str = "paste"


class ApplicationOut(BaseModel):
    model_config = _ORM_CONFIG
    id: uuid.UUID
    company_name: str
    role_title: str | None
    jd_raw: str
    jd_parsed: dict | None
    jd_source: str | None
    status: str
    created_at: datetime


# ── Tailoring ──────────────────────────────────────────────────────────
class TailorRunRequest(BaseModel):
    application_id: uuid.UUID


class BulletDiff(BaseModel):
    experience_id: uuid.UUID
    original_bullets: list[str]
    suggested_bullets: list[str]
    changes_made: list[str]
    confidence: float


class AtsWarning(BaseModel):
    field: str
    issue: str
    suggestion: str


class TailorRunResponse(BaseModel):
    cv_version_id: uuid.UUID
    diffs: list[BulletDiff]
    ats_warnings: list[AtsWarning]
    ats_score: int


class AcceptChangesRequest(BaseModel):
    accepted_changes: dict
    rejected_changes: dict


# ── Tailoring Rules ───────────────────────────────────────────────────
class TailoringRuleCreate(BaseModel):
    rule_text: str


class TailoringRuleOut(BaseModel):
    model_config = _ORM_CONFIG
    id: uuid.UUID
    rule_text: str
    is_active: bool
    created_at: datetime


class TailoringRuleUpdate(BaseModel):
    rule_text: str | None = None
    is_active: bool | None = None


# ── GPT-4o Structured Output Schemas ──────────────────────────────────
class ParsedBullet(BaseModel):
    text: str
    domain_tags: list[str] = Field(default_factory=list)


class ParsedWorkExperience(BaseModel):
    company: str | None = None
    role_title: str | None = None
    location: str | None = None
    date_start: str | None = None  # ISO date string or partial
    date_end: str | None = None
    is_current: bool = False
    company_confidence: float = Field(ge=0, le=1)
    dates_confidence: float = Field(ge=0, le=1)
    bullets: list[ParsedBullet] = Field(default_factory=list)
    raw_block: str
    domain_tags: list[str] = Field(default_factory=list)
    skill_tags: list[str] = Field(default_factory=list)


class ParsedActivity(BaseModel):
    company: str | None = None  # GPT outputs "company"; mapped to "organization" at DB layer
    role_title: str | None = None
    location: str | None = None
    date_start: str | None = None
    date_end: str | None = None
    is_current: bool = False
    company_confidence: float = Field(ge=0, le=1)
    dates_confidence: float = Field(ge=0, le=1)
    bullets: list[ParsedBullet] = Field(default_factory=list)
    raw_block: str
    domain_tags: list[str] = Field(default_factory=list)
    skill_tags: list[str] = Field(default_factory=list)


class ParsedEducation(BaseModel):
    institution: str | None = None
    degree: str | None = None
    grade: str | None = None
    date_start: str | None = None
    date_end: str | None = None
    location: str | None = None
    achievements: list[str] = Field(default_factory=list)
    modules: list[str] = Field(default_factory=list)
    raw_block: str
    dates_confidence: float = Field(ge=0, le=1)
    institution_confidence: float = Field(ge=0, le=1)


class ParsedProject(BaseModel):
    name: str | None = None
    description: str | None = None
    date_start: str | None = None
    date_end: str | None = None
    url: str | None = None
    bullets: list[ParsedBullet] = Field(default_factory=list)
    raw_block: str
    domain_tags: list[str] = Field(default_factory=list)
    skill_tags: list[str] = Field(default_factory=list)


class ParsedSkill(BaseModel):
    name: str
    category: str | None = None  # technical, language, tool, soft, other, certification, framework, interest
    proficiency: str | None = None


class ParsedUnclassifiedBlock(BaseModel):
    raw_text: str
    category_guess: str | None = None
    confidence: float = Field(ge=0, le=1)


class ParsedProfile(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    summary: str | None = None
    name_confidence: float = Field(ge=0, le=1, default=0.0)
    contact_confidence: float = Field(ge=0, le=1, default=0.0)


class StructuredCvParse(BaseModel):
    """Full structured output from GPT-4o CV parsing."""

    profile: ParsedProfile
    work_experiences: list[ParsedWorkExperience] = Field(default_factory=list)
    education: list[ParsedEducation] = Field(default_factory=list)
    projects: list[ParsedProject] = Field(default_factory=list)
    activities: list[ParsedActivity] = Field(default_factory=list)
    skills: list[ParsedSkill] = Field(default_factory=list)
    unclassified_blocks: list[ParsedUnclassifiedBlock] = Field(default_factory=list)
