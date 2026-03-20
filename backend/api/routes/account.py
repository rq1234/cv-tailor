"""Account management routes — delete account."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from supabase import create_client

from backend.api.auth import get_current_user
from backend.config import get_settings
from backend.models.database import get_db
from backend.models.tables import (
    Activity,
    Application,
    CvProfile,
    CvUpload,
    CvVersion,
    Education,
    Project,
    Skill,
    TailoringRule,
    UnclassifiedBlock,
    WorkExperience,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/account", tags=["account"])


@router.delete("")
async def delete_account(
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Permanently delete the authenticated user's account and all associated data.

    Deletion order respects FK constraints (CvVersion → Application before Application).
    After DB cleanup, the Supabase auth user is deleted so login is no longer possible.
    """
    try:
        # 1. CvVersion has FK to Application — delete first
        await db.execute(delete(CvVersion).where(CvVersion.user_id == user_id))
        # 2. Application
        await db.execute(delete(Application).where(Application.user_id == user_id))
        # 3. Remaining user-scoped tables (no FK dependencies between them)
        await db.execute(delete(WorkExperience).where(WorkExperience.user_id == user_id))
        await db.execute(delete(Education).where(Education.user_id == user_id))
        await db.execute(delete(Project).where(Project.user_id == user_id))
        await db.execute(delete(Skill).where(Skill.user_id == user_id))
        await db.execute(delete(Activity).where(Activity.user_id == user_id))
        await db.execute(delete(UnclassifiedBlock).where(UnclassifiedBlock.user_id == user_id))
        await db.execute(delete(TailoringRule).where(TailoringRule.user_id == user_id))
        await db.execute(delete(CvUpload).where(CvUpload.user_id == user_id))
        await db.execute(delete(CvProfile).where(CvProfile.user_id == user_id))
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.exception("DB deletion failed for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account data. Please try again.",
        ) from e

    # Delete the Supabase auth user — same pattern as auth.py
    try:
        settings = get_settings()
        supabase = create_client(settings.supabase_url, settings.supabase_service_key)
        supabase.auth.admin.delete_user(str(user_id))
    except Exception as e:
        logger.error("Supabase auth deletion failed for user %s: %s", user_id, e)
        # DB data is already gone — log but don't surface error to user
        # (auth account will eventually be cleaned up or can be deleted manually)

    return {"status": "deleted"}
