"""Application routes — create and manage job applications."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.api.db_helpers import delete_or_404, get_or_404
from backend.models.database import get_db
from backend.models.tables import Application, CvVersion
from backend.schemas.pydantic import ApplicationCreate, ApplicationOut, ApplicationUpdate
from backend.services.screenshot_ocr import extract_text_from_screenshot

router = APIRouter(prefix="/api/applications", tags=["applications"])

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_APPLICATIONS_PER_USER = 20


@router.get("", response_model=list[ApplicationOut])
async def list_applications(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """List all applications for the current user, newest first."""
    result = await db.execute(
        select(Application)
        .where(Application.user_id == user_id)
        .order_by(Application.created_at.desc())
    )
    return [ApplicationOut.model_validate(app) for app in result.scalars().all()]


@router.post("", response_model=ApplicationOut)
async def create_application(
    body: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Create a new job application with raw JD."""
    count_result = await db.execute(
        select(func.count(Application.id)).where(Application.user_id == user_id)
    )
    application_count = count_result.scalar_one()
    if application_count >= MAX_APPLICATIONS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"Application limit reached ({MAX_APPLICATIONS_PER_USER}). Delete an old application to create a new one.",
        )

    app = Application(
        user_id=user_id,
        company_name=body.company_name,
        role_title=body.role_title,
        jd_raw=body.jd_raw,
        jd_source=body.jd_source,
        status="draft",
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return ApplicationOut.model_validate(app)


class ScreenshotExtractResponse(BaseModel):
    extracted_text: str


@router.post("/screenshot", response_model=ScreenshotExtractResponse)
async def extract_screenshot_text(
    file: UploadFile,
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Extract job description text from a screenshot using GPT-4o Vision."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type: {file.content_type}. Allowed: PNG, JPEG, WebP, GIF.",
        )

    image_bytes = await file.read()
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="Image too large. Maximum size is 20 MB.")

    extracted_text = await extract_text_from_screenshot(image_bytes, file.content_type)
    return ScreenshotExtractResponse(extracted_text=extracted_text)


@router.get("/{application_id}", response_model=ApplicationOut)
async def get_application(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Get a single application by ID."""
    app = await get_or_404(db, Application, application_id, user_id, "Application not found")
    return ApplicationOut.model_validate(app)


VALID_OUTCOMES = {"applied", "interview", "offer", "rejected", "withdrawn"}


@router.patch("/{application_id}", response_model=ApplicationOut)
async def update_application(
    application_id: uuid.UUID,
    body: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Update outcome for an application."""
    if body.outcome is not None and body.outcome not in VALID_OUTCOMES:
        raise HTTPException(status_code=400, detail=f"Invalid outcome. Must be one of: {', '.join(sorted(VALID_OUTCOMES))}")
    app = await get_or_404(db, Application, application_id, user_id, "Application not found")
    app.outcome = body.outcome
    await db.commit()
    await db.refresh(app)
    return ApplicationOut.model_validate(app)


@router.delete("/{application_id}")
async def delete_application(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Delete an application and all associated data."""
    await db.execute(
        delete(CvVersion).where(
            CvVersion.user_id == user_id,
            CvVersion.application_id == application_id,
        )
    )
    return await delete_or_404(db, Application, application_id, user_id, "Application not found")
