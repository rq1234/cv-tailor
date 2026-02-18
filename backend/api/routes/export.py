"""Export routes — LaTeX and Overleaf generation."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.models.database import get_db
from backend.models.tables import Application, CvVersion
from backend.services.exporter import generate_latex

router = APIRouter(prefix="/api/export", tags=["export"])


async def _get_cv_version(
    cv_version_id: uuid.UUID,
    db: AsyncSession,
    user_id: uuid.UUID,
) -> CvVersion:
    result = await db.execute(
        select(CvVersion).where(
            CvVersion.id == cv_version_id,
            CvVersion.user_id == user_id,
        )
    )
    cv_version = result.scalar_one_or_none()
    if not cv_version:
        raise HTTPException(status_code=404, detail="CV version not found")
    return cv_version


@router.post("/latex/{cv_version_id}")
async def export_latex(
    cv_version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Generate and return LaTeX source for the given CV version."""
    cv_version = await _get_cv_version(cv_version_id, db, user_id)

    latex_content = await generate_latex(db, cv_version, user_id)

    filename = "cv.tex"
    if cv_version.application_id:
        app_result = await db.execute(
            select(Application).where(
                Application.id == cv_version.application_id,
                Application.user_id == user_id,
            )
        )
        app = app_result.scalar_one_or_none()
        if app:
            company = (app.company_name or "company").replace(" ", "_").lower()
            role = (app.role_title or "role").replace(" ", "_").lower()
            filename = f"cv_{company}_{role}.tex"

    return Response(
        content=latex_content.encode("utf-8"),
        media_type="text/x-tex",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/overleaf/{cv_version_id}")
async def export_overleaf(
    cv_version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Return LaTeX content for Overleaf. Frontend submits via hidden POST form."""
    cv_version = await _get_cv_version(cv_version_id, db, user_id)

    latex_content = await generate_latex(db, cv_version, user_id)

    return {
        "success": True,
        "latex_content": latex_content,
        "message": "Use the returned content to POST to Overleaf",
    }
