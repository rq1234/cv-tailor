"""CV upload and experience pool routes."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.models.database import get_db
from backend.models.tables import (
    Activity,
    CvProfile,
    Education,
    Project,
    Skill,
    WorkExperience,
)
from backend.schemas.pydantic import (
    ActivityOut,
    CvProfileOut,
    EducationOut,
    ExperiencePoolResponse,
    ParseSummary,
    ProjectOut,
    SkillOut,
    WorkExperienceOut,
)
from backend.services.cv_service import parse_and_store_cv, re_embed_all

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cv", tags=["cv"])


@router.post("/upload", response_model=ParseSummary)
async def upload_cv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Upload a PDF or DOCX CV, extract text, structure with GPT-4o, and store."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_bytes = await file.read()
    filename_lower = file.filename.lower()

    if filename_lower.endswith(".pdf"):
        file_type = "pdf"
    elif filename_lower.endswith(".docx"):
        file_type = "docx"
    else:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    try:
        return await parse_and_store_cv(db, file_bytes, file.filename, file_type, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/re-embed")
async def re_embed_experiences(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Re-generate embeddings for all records with NULL embeddings."""
    return await re_embed_all(db, user_id)


@router.get("/pool", response_model=ExperiencePoolResponse)
async def get_experience_pool(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Get the full experience pool — all work experiences, education, projects, skills."""
    # Get profile (most recent)
    profile_result = await db.execute(
        select(CvProfile)
        .where(CvProfile.user_id == user_id)
        .order_by(CvProfile.updated_at.desc())
        .limit(1)
    )
    profile_row = profile_result.scalar_one_or_none()
    profile_out = None
    if profile_row:
        profile_out = CvProfileOut(
            id=profile_row.id,
            full_name=profile_row.full_name,
            email=profile_row.email,
            phone=profile_row.phone,
            location=profile_row.location,
            linkedin_url=profile_row.linkedin_url,
            portfolio_url=profile_row.portfolio_url,
            summary=profile_row.summary,
        )

    # Get work experiences
    work_result = await db.execute(
        select(WorkExperience)
        .where(WorkExperience.user_id == user_id)
        .order_by(WorkExperience.date_start.desc().nullslast())
    )
    work_exps = [
        WorkExperienceOut(
            id=w.id, company=w.company, role_title=w.role_title, location=w.location,
            date_start=w.date_start, date_end=w.date_end, is_current=w.is_current,
            bullets=w.bullets, domain_tags=w.domain_tags, skill_tags=w.skill_tags,
            variant_group_id=w.variant_group_id, is_primary_variant=w.is_primary_variant,
            needs_review=w.needs_review, review_reason=w.review_reason,
        )
        for w in work_result.scalars().all()
    ]

    # Get education
    edu_result = await db.execute(
        select(Education)
        .where(Education.user_id == user_id)
        .order_by(Education.date_end.desc().nullslast())
    )
    education = [
        EducationOut(
            id=e.id, institution=e.institution, degree=e.degree, grade=e.grade,
            date_start=e.date_start, date_end=e.date_end, location=e.location,
            achievements=e.achievements, modules=e.modules, needs_review=e.needs_review,
        )
        for e in edu_result.scalars().all()
    ]

    # Get projects
    proj_result = await db.execute(
        select(Project)
        .where(Project.user_id == user_id)
        .order_by(Project.date_end.desc().nullslast())
    )
    projects = [
        ProjectOut(
            id=p.id, name=p.name, description=p.description,
            date_start=p.date_start, date_end=p.date_end, url=p.url,
            bullets=p.bullets, domain_tags=p.domain_tags, skill_tags=p.skill_tags,
            variant_group_id=p.variant_group_id, is_primary_variant=p.is_primary_variant,
            needs_review=p.needs_review,
        )
        for p in proj_result.scalars().all()
    ]

    # Get activities
    act_result = await db.execute(
        select(Activity)
        .where(Activity.user_id == user_id)
        .order_by(Activity.date_start.desc().nullslast())
    )
    activities = [
        ActivityOut(
            id=a.id, organization=a.organization, role_title=a.role_title, location=a.location,
            date_start=a.date_start, date_end=a.date_end, is_current=a.is_current,
            bullets=a.bullets, domain_tags=a.domain_tags, skill_tags=a.skill_tags,
            variant_group_id=a.variant_group_id, is_primary_variant=a.is_primary_variant,
            needs_review=a.needs_review, review_reason=a.review_reason,
        )
        for a in act_result.scalars().all()
    ]

    # Get skills (deduplicate by lowercase name)
    skill_result = await db.execute(
        select(Skill)
        .where(Skill.is_duplicate_of.is_(None), Skill.user_id == user_id)
    )
    skills = []
    seen_skill_names: set[str] = set()
    for s in skill_result.scalars().all():
        name_lower = s.name.strip().lower()
        if name_lower in seen_skill_names:
            continue
        seen_skill_names.add(name_lower)
        skills.append(SkillOut(
            id=s.id, name=s.name, canonical_name=s.canonical_name,
            category=s.category, proficiency=s.proficiency, domain_tags=s.domain_tags,
        ))

    return ExperiencePoolResponse(
        profile=profile_out,
        work_experiences=work_exps,
        education=education,
        projects=projects,
        activities=activities,
        skills=skills,
    )
