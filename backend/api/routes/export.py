"""Export routes — LaTeX and Overleaf generation."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.models.database import get_db
from backend.models.tables import Application, CvVersion
from backend.services.exporter import generate_docx, generate_latex
from backend.services.pdf_compiler import compile_latex_to_pdf

router = APIRouter(prefix="/api/export", tags=["export"])


# ── Cover letter PDF helpers ───────────────────────────────────────────────

def _latex_escape(text: str) -> str:
    """Escape special LaTeX characters in plain text."""
    text = text.replace("\\", "\\textbackslash{}")
    for char, cmd in [
        ("&", "\\&"), ("%", "\\%"), ("$", "\\$"),
        ("#", "\\#"), ("_", "\\_"), ("{", "\\{"), ("}", "\\}"),
        ("~", "\\textasciitilde{}"), ("^", "\\textasciicircum{}"),
    ]:
        text = text.replace(char, cmd)
    return text


def _build_cover_letter_latex(parts: dict) -> str:
    e = _latex_escape
    candidate_block = " \\\\\n".join(e(ln) for ln in parts.get("candidate_lines", []))
    date = e(parts.get("date", ""))
    company_block = " \\\\\n".join(e(ln) for ln in parts.get("company_lines", []))
    salutation = e(parts.get("salutation", "Dear Sir/Madam,"))
    paragraphs_latex = "\n\n".join(e(p) for p in parts.get("paragraphs", []))
    closing = e(parts.get("closing", ""))
    sign_off = e(parts.get("sign_off", "Yours sincerely,"))
    candidate_name = e(parts.get("candidate_name", ""))

    return rf"""\documentclass[a4paper,11pt]{{article}}
\usepackage[top=2cm,bottom=2.5cm,left=2.5cm,right=2.5cm]{{geometry}}
\usepackage[T1]{{fontenc}}
\usepackage{{lmodern}}
\usepackage{{microtype}}
\pagestyle{{empty}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{0.75em}}
\renewcommand{{\baselinestretch}}{{1.15}}

\begin{{document}}

\begin{{flushright}}
{candidate_block}
\end{{flushright}}

\vspace{{0.6em}}

{date}

\vspace{{0.6em}}

{company_block}

\vspace{{0.6em}}

{salutation}

\vspace{{0.4em}}

{paragraphs_latex}

{closing}

\vspace{{0.8em}}

{sign_off}\\\\[0.2em]
{candidate_name}

\end{{document}}"""


class _CoverLetterParts(BaseModel):
    """Typed cover letter sections — prevents injection of arbitrary LaTeX content."""

    candidate_lines: list[str] = Field(max_length=10)
    date: str = Field(max_length=20)
    company_lines: list[str] = Field(max_length=10)
    salutation: str = Field(max_length=200)
    paragraphs: list[str] = Field(max_length=6)
    closing: str = Field(max_length=500)
    sign_off: str = Field(max_length=100)
    candidate_name: str = Field(max_length=200)


class _CoverLetterPdfBody(BaseModel):
    parts: _CoverLetterParts


@router.post("/cover-letter")
async def export_cover_letter_pdf(
    body: _CoverLetterPdfBody,
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Compile cover letter parts to a PDF using Tectonic."""
    latex = _build_cover_letter_latex(body.parts.model_dump())

    try:
        pdf_bytes = await compile_latex_to_pdf(latex)
    except FileNotFoundError:
        raise HTTPException(
            status_code=501,
            detail=(
                "PDF compilation is not available on this server. "
                "Use 'Copy to clipboard' and paste into Word or Google Docs instead."
            ),
        )
    except RuntimeError:
        raise HTTPException(status_code=500, detail="PDF compilation failed.")

    company_raw = body.parts.company_lines[0] if body.parts.company_lines else ""
    company_slug = re.sub(r"[^\w\-]", "_", company_raw.lower())[:30] or "company"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="cover_letter_{company_slug}.pdf"'},
    )


def _cv_filename(company: str | None, role: str | None, ext: str) -> str:
    """Build a safe filename like cv_google_engineer.pdf from company/role strings."""
    c = re.sub(r"[^\w\-]", "_", (company or "company").lower())[:50]
    r = re.sub(r"[^\w\-]", "_", (role or "role").lower())[:50]
    return f"cv_{c}_{r}.{ext}"


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
            filename = _cv_filename(app.company_name, app.role_title, "tex")

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
            filename = _cv_filename(app.company_name, app.role_title, "pdf")

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


@router.post("/docx/{cv_version_id}")
async def export_docx(
    cv_version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Generate and return a Word document (.docx) for the given CV version."""
    cv_version = await _get_cv_version(cv_version_id, db, user_id)

    filename = "cv.docx"
    if cv_version.application_id:
        app_result = await db.execute(
            select(Application).where(
                Application.id == cv_version.application_id,
                Application.user_id == user_id,
            )
        )
        app = app_result.scalar_one_or_none()
        if app:
            filename = _cv_filename(app.company_name, app.role_title, "docx")

    try:
        docx_bytes = await generate_docx(db, cv_version, user_id)
    except Exception:
        raise HTTPException(status_code=500, detail="DOCX generation failed.")

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
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
