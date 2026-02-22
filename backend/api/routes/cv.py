"""CV upload and experience pool routes."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.api.db_helpers import fetch_latest_profile
from backend.models.database import get_db
from backend.models.tables import (
    Activity,
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
limiter = Limiter(key_func=get_remote_address)

MAX_CV_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


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
    if len(file_bytes) > MAX_CV_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10 MB.")

    filename_lower = file.filename.lower()

    if filename_lower.endswith(".pdf"):
        file_type = "pdf"
    elif filename_lower.endswith(".docx"):
        file_type = "docx"
    else:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    # Validate magic bytes match the declared file type
    PDF_MAGIC = b"%PDF"
    DOCX_MAGIC = b"PK\x03\x04"
    if file_type == "pdf" and not file_bytes.startswith(PDF_MAGIC):
        raise HTTPException(status_code=400, detail="File content does not match PDF format")
    if file_type == "docx" and not file_bytes.startswith(DOCX_MAGIC):
        raise HTTPException(status_code=400, detail="File content does not match DOCX format")

    try:
        return await parse_and_store_cv(db, file_bytes, file.filename, file_type, user_id)
    except ValueError as e:
        logger.warning("CV parse validation error for user %s: %s", user_id, e)
        raise HTTPException(status_code=400, detail="Could not parse the uploaded file. Please ensure it is a valid CV.")
    except RuntimeError as e:
        logger.error("CV parse runtime error for user %s: %s", user_id, e)
        raise HTTPException(status_code=500, detail="An error occurred while processing your CV.")


@router.post("/re-embed")
@limiter.limit("5/hour")
async def re_embed_experiences(
    request: Request,
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
    # SQLAlchemy AsyncSession does not allow concurrent operations on the same session;
    # queries must run sequentially.
    profile_row = await fetch_latest_profile(db, user_id)
    work_rows = await db.execute(
        select(WorkExperience)
        .where(WorkExperience.user_id == user_id)
        .order_by(WorkExperience.date_start.desc().nullslast())
    )
    edu_rows = await db.execute(
        select(Education)
        .where(Education.user_id == user_id)
        .order_by(Education.date_end.desc().nullslast())
    )
    proj_rows = await db.execute(
        select(Project)
        .where(Project.user_id == user_id)
        .order_by(Project.date_end.desc().nullslast())
    )
    act_rows = await db.execute(
        select(Activity)
        .where(Activity.user_id == user_id)
        .order_by(Activity.date_start.desc().nullslast())
    )
    skill_rows = await db.execute(
        select(Skill).where(Skill.is_duplicate_of.is_(None), Skill.user_id == user_id)
    )

    profile_out = CvProfileOut.model_validate(profile_row) if profile_row else None

    work_exps = [WorkExperienceOut.model_validate(w) for w in work_rows.scalars().all()]
    education = [EducationOut.model_validate(e) for e in edu_rows.scalars().all()]
    projects = [ProjectOut.model_validate(p) for p in proj_rows.scalars().all()]
    activities = [ActivityOut.model_validate(a) for a in act_rows.scalars().all()]

    # Deduplicate skills by lowercase name
    skills: list[SkillOut] = []
    seen_skill_names: set[str] = set()
    for s in skill_rows.scalars().all():
        name_lower = s.name.strip().lower()
        if name_lower in seen_skill_names:
            continue
        seen_skill_names.add(name_lower)
        skills.append(SkillOut.model_validate(s))

    return ExperiencePoolResponse(
        profile=profile_out,
        work_experiences=work_exps,
        education=education,
        projects=projects,
        activities=activities,
        skills=skills,
    )
