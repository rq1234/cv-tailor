"""Export routes — LaTeX and Overleaf generation."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.models.database import get_db
from backend.models.tables import Application, CvVersion
from backend.services.exporter import generate_latex
from backend.services.pdf_compiler import compile_latex_to_pdf

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
            company = re.sub(r"[^\w\-]", "_", (app.company_name or "company").lower())[:50]
            role = re.sub(r"[^\w\-]", "_", (app.role_title or "role").lower())[:50]
            filename = f"cv_{company}_{role}.tex"

    return Response(
        content=latex_content.encode("utf-8"),
        media_type="text/x-tex",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/pdf/{cv_version_id}")
async def export_pdf(
    cv_version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Compile LaTeX to PDF server-side using Tectonic and return the PDF file."""
    cv_version = await _get_cv_version(cv_version_id, db, user_id)
    latex_content = await generate_latex(db, cv_version, user_id)

    filename = "cv.pdf"
    if cv_version.application_id:
        app_result = await db.execute(
            select(Application).where(
                Application.id == cv_version.application_id,
                Application.user_id == user_id,
            )
        )
        app = app_result.scalar_one_or_none()
        if app:
            company = re.sub(r"[^\w\-]", "_", (app.company_name or "company").lower())[:50]
            role = re.sub(r"[^\w\-]", "_", (app.role_title or "role").lower())[:50]
            filename = f"cv_{company}_{role}.pdf"

    try:
        pdf_bytes = await compile_latex_to_pdf(latex_content)
    except FileNotFoundError:
        raise HTTPException(
            status_code=501,
            detail="PDF compilation is not available on this server. Use 'Save & Open in Overleaf' to download a PDF, or download the .tex file.",
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail="PDF compilation failed. Try downloading the .tex file instead.")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
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
