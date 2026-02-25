"""User preferences/settings endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.models.database import get_db
from backend.models.tables import CvProfile
from backend.schemas.pydantic import UserPreferencesOut, UserPreferencesUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/preferences", response_model=UserPreferencesOut)
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Return user preferences. Defaults returned if no profile exists yet."""
    result = await db.execute(
        select(CvProfile).where(CvProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        return UserPreferencesOut(max_resume_pages=1)
    return UserPreferencesOut(max_resume_pages=profile.max_resume_pages)


@router.put("/preferences", response_model=UserPreferencesOut)
async def update_preferences(
    body: UserPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Update user preferences. Creates the profile row if it doesn't exist yet."""
    result = await db.execute(
        select(CvProfile).where(CvProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = CvProfile(user_id=user_id, max_resume_pages=body.max_resume_pages)
        db.add(profile)
    else:
        profile.max_resume_pages = body.max_resume_pages
    await db.commit()
    await db.refresh(profile)
    return UserPreferencesOut(max_resume_pages=profile.max_resume_pages)
