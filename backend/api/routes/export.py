"""Export routes — PDF, DOCX, LaTeX, and Overleaf generation."""

from __future__ import annotations

import base64
import json
import uuid
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_db
from backend.models.tables import Application, CvVersion
from backend.services.exporter import generate_docx, generate_pdf, generate_latex

router = APIRouter(prefix="/api/export", tags=["export"])


async def _get_cv_version(
    cv_version_id: uuid.UUID, db: AsyncSession
) -> CvVersion:
    result = await db.execute(
        select(CvVersion).where(CvVersion.id == cv_version_id)
    )
    cv_version = result.scalar_one_or_none()
    if not cv_version:
        raise HTTPException(status_code=404, detail="CV version not found")
    return cv_version


@router.post("/pdf/{cv_version_id}")
async def export_pdf(
    cv_version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Generate and return a PDF for the given CV version."""
    cv_version = await _get_cv_version(cv_version_id, db)

    pdf_bytes = await generate_pdf(db, cv_version)

    # Build a filename from the application
    filename = "tailored_cv.pdf"
    if cv_version.application_id:
        app_result = await db.execute(
            select(Application).where(Application.id == cv_version.application_id)
        )
        app = app_result.scalar_one_or_none()
        if app:
            company = (app.company_name or "company").replace(" ", "_").lower()
            role = (app.role_title or "role").replace(" ", "_").lower()
            filename = f"cv_{company}_{role}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/docx/{cv_version_id}")
async def export_docx(
    cv_version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Generate and return a DOCX for the given CV version."""
    cv_version = await _get_cv_version(cv_version_id, db)

    docx_bytes = await generate_docx(db, cv_version)

    filename = "tailored_cv.docx"
    if cv_version.application_id:
        app_result = await db.execute(
            select(Application).where(Application.id == cv_version.application_id)
        )
        app = app_result.scalar_one_or_none()
        if app:
            company = (app.company_name or "company").replace(" ", "_").lower()
            role = (app.role_title or "role").replace(" ", "_").lower()
            filename = f"cv_{company}_{role}.docx"

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/latex/{cv_version_id}")
async def export_latex(
    cv_version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Generate and return LaTeX source for the given CV version."""
    cv_version = await _get_cv_version(cv_version_id, db)

    latex_content = await generate_latex(db, cv_version)

    filename = "cv.tex"
    if cv_version.application_id:
        app_result = await db.execute(
            select(Application).where(Application.id == cv_version.application_id)
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
):
    """Return LaTeX content for Overleaf. Frontend submits via hidden POST form."""
    cv_version = await _get_cv_version(cv_version_id, db)

    latex_content = await generate_latex(db, cv_version)

    return {
        "success": True,
        "latex_content": latex_content,
        "message": "Use the returned content to POST to Overleaf",
    }
