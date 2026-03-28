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
    # 1. Delete Supabase auth user first — if this fails, DB data is still intact
    #    and the user can retry. Avoids the worse failure mode of DB gone but auth remains.
    try:
        settings = get_settings()
        supa = create_client(settings.supabase_url, settings.supabase_service_key)
        supa.auth.admin.delete_user(str(user_id))
    except Exception as e:
        logger.error("Supabase auth deletion failed for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account. Please try again.",
        ) from e

    # 2. Delete all DB data — auth is already gone so user cannot log back in
    try:
        await db.execute(delete(CvVersion).where(CvVersion.user_id == user_id))
        await db.execute(delete(Application).where(Application.user_id == user_id))
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
        logger.exception("DB deletion failed for user %s (auth already deleted)", user_id)
        # Auth is gone — log for manual cleanup but don't block the user
        logger.error("Orphaned DB data for deleted user %s — manual cleanup required", user_id)

    return {"status": "deleted"}
