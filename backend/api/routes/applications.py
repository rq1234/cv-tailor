"""Application routes — create and manage job applications."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.clients import get_openai_client
from backend.api.db_helpers import delete_or_404, get_or_404, is_master_account
from backend.config import get_settings
from backend.enums import ApplicationStatus
from backend.models.database import get_db
from backend.models.tables import Activity, Application, CvProfile, CvVersion, Education, WorkExperience
from backend.schemas.pydantic import ApplicationCreate, ApplicationOut, ApplicationUpdate
from backend.services.screenshot_ocr import extract_text_from_screenshot

router = APIRouter(prefix="/api/applications", tags=["applications"])
limiter = Limiter(key_func=get_remote_address)

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB


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
    if not await is_master_account(db, user_id):
        count_result = await db.execute(
            select(func.count(Application.id)).where(Application.user_id == user_id)
        )
        application_count = count_result.scalar_one()
        max_apps = get_settings().max_applications_per_user
        if application_count >= max_apps:
            raise HTTPException(
                status_code=400,
                detail=f"Application limit reached ({max_apps}). Delete an old application to create a new one.",
            )

    app = Application(
        user_id=user_id,
        company_name=body.company_name,
        role_title=body.role_title,
        jd_raw=body.jd_raw,
        jd_source=body.jd_source,
        jd_url=body.jd_url,
        status=ApplicationStatus.DRAFT,
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

    try:
        extracted_text = await asyncio.wait_for(
            extract_text_from_screenshot(image_bytes, file.content_type),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Screenshot OCR timed out. Please try again.")
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


@router.patch("/{application_id}", response_model=ApplicationOut)
async def update_application(
    application_id: uuid.UUID,
    body: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Update outcome for an application."""
    app = await get_or_404(db, Application, application_id, user_id, "Application not found")
    app.outcome = body.outcome
    if body.notes is not None:
        app.notes = body.notes
    await db.commit()
    await db.refresh(app)
    return ApplicationOut.model_validate(app)


@router.get("/stats/summary")
async def get_application_stats(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Return aggregated stats across all applications for the current user."""
    apps_result = await db.execute(
        select(Application).where(Application.user_id == user_id)
    )
    apps = apps_result.scalars().all()

    # Fetch latest ATS score per application from cv_versions
    ats_by_app: dict[str, int | None] = {}
    cv_result = await db.execute(
        select(CvVersion.application_id, CvVersion.ats_score)
        .where(CvVersion.user_id == user_id, CvVersion.ats_score.isnot(None))
        .order_by(CvVersion.application_id, CvVersion.created_at.desc())
        .distinct(CvVersion.application_id)
    )
    for app_id, score in cv_result.all():
        ats_by_app[str(app_id)] = score

    total = len(apps)
    by_outcome: dict[str, int] = {}
    domain_stats: dict[str, dict] = {}

    for app in apps:
        outcome = app.outcome or "pending"
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1

        domain = None
        if app.jd_parsed and isinstance(app.jd_parsed, dict):
            domain = app.jd_parsed.get("domain") or "other"
        domain = (domain or "other").lower()

        if domain not in domain_stats:
            domain_stats[domain] = {"count": 0, "offers": 0, "interviews": 0, "ats_scores": []}
        domain_stats[domain]["count"] += 1
        if app.outcome == "offer":
            domain_stats[domain]["offers"] += 1
        if app.outcome in ("interview", "offer"):
            domain_stats[domain]["interviews"] += 1
        ats = ats_by_app.get(str(app.id))
        if ats is not None:
            domain_stats[domain]["ats_scores"].append(ats)

    all_ats = [s for d in domain_stats.values() for s in d["ats_scores"]]
    avg_ats = round(sum(all_ats) / len(all_ats)) if all_ats else None

    by_domain = [
        {
            "domain": domain,
            "count": stats["count"],
            "avg_ats_score": round(sum(stats["ats_scores"]) / len(stats["ats_scores"])) if stats["ats_scores"] else None,
            "offer_rate": round(stats["offers"] / stats["count"], 2) if stats["count"] else 0,
            "interview_rate": round(stats["interviews"] / stats["count"], 2) if stats["count"] else 0,
        }
        for domain, stats in domain_stats.items()
    ]

    return {
        "total": total,
        "by_outcome": by_outcome,
        "avg_ats_score": avg_ats,
        "by_domain": sorted(by_domain, key=lambda x: x["count"], reverse=True),
    }


@router.get("/gap-recommendations")
async def get_gap_recommendations(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Return the most common skill gaps across recent applications, grouped by domain."""
    cv_result = await db.execute(
        select(CvVersion.gap_analysis, CvVersion.application_id)
        .where(CvVersion.user_id == user_id, CvVersion.gap_analysis.isnot(None))
        .order_by(CvVersion.created_at.desc())
        .limit(10)
    )
    rows = cv_result.all()

    # Build domain lookup from applications
    app_ids = [row.application_id for row in rows if row.application_id]
    domain_by_app: dict[str, str] = {}
    company_by_app: dict[str, str] = {}
    if app_ids:
        apps_result = await db.execute(
            select(Application.id, Application.jd_parsed, Application.company_name)
            .where(Application.id.in_(app_ids), Application.user_id == user_id)
        )
        for app_id, jd_parsed, company_name in apps_result.all():
            domain = "other"
            if jd_parsed and isinstance(jd_parsed, dict):
                domain = (jd_parsed.get("domain") or "other").lower()
            domain_by_app[str(app_id)] = domain
            company_by_app[str(app_id)] = company_name or "Unknown"

    # Aggregate gaps
    gap_freq: dict[str, dict[str, object]] = {}  # key: f"{domain}||{requirement}"
    for row in rows:
        gap_analysis = row.gap_analysis
        app_id = str(row.application_id) if row.application_id else None
        domain = domain_by_app.get(app_id or "", "other")
        company = company_by_app.get(app_id or "", "Unknown")
        if not gap_analysis or not isinstance(gap_analysis, dict):
            continue
        for mapping in gap_analysis.get("mappings", []):
            if mapping.get("status") == "gap":
                req = mapping.get("requirement", "").strip()
                if not req:
                    continue
                gkey = f"{domain}||{req}"
                if gkey not in gap_freq:
                    gap_freq[gkey] = {"domain": domain, "gap": req, "count": 0, "companies": []}
                gap_freq[gkey]["count"] = int(gap_freq[gkey]["count"]) + 1  # type: ignore[arg-type]
                companies = gap_freq[gkey]["companies"]
                assert isinstance(companies, list)
                if company not in companies:
                    companies.append(company)

    recommendations = sorted(gap_freq.values(), key=lambda x: int(x["count"]), reverse=True)  # type: ignore[arg-type]
    # Keep top 5 per domain
    domain_seen: dict[str, int] = {}
    filtered = []
    for rec in recommendations:
        d = str(rec["domain"])
        if domain_seen.get(d, 0) < 5:
            filtered.append(rec)
            domain_seen[d] = domain_seen.get(d, 0) + 1

    return {"recommendations": filtered}


class ScrapeUrlRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)

    @field_validator("url")
    @classmethod
    def validate_url_scheme(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return v


class ScrapeUrlResponse(BaseModel):
    jd_text: str


@router.post("/scrape-url", response_model=ScrapeUrlResponse)
@limiter.limit("15/hour")
async def scrape_jd_url(
    request: Request,
    body: ScrapeUrlRequest,
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Fetch a job posting URL and extract JD text using GPT-4o-mini."""
    from backend.services.jd_scraper import scrape_jd_from_url

    try:
        jd_text = await scrape_jd_from_url(body.url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return ScrapeUrlResponse(jd_text=jd_text)


class _LetterParts(BaseModel):
    """Internal schema for GPT structured output — not exposed directly."""

    candidate_lines: list[str]  # name, address line(s), phone, email — in order
    date: str  # DD/MM/YYYY
    company_lines: list[str]  # company name + full address lines
    salutation: str  # "Dear Sir/Madam,"
    paragraphs: list[str]  # 4 body paragraphs
    closing: str  # "Thank you very much…" sentence
    sign_off: str  # "Yours sincerely,"
    candidate_name: str  # just the name for the signature


class CoverLetterResponse(BaseModel):
    cover_letter: str  # flat text (backward compat)
    parts: dict | None = None  # structured data for rich frontend rendering


@router.post("/{application_id}/cover-letter", response_model=CoverLetterResponse)
@limiter.limit("10/hour")
async def generate_cover_letter(
    request: Request,
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Generate a complete, formally formatted cover letter using GPT-4o."""
    from datetime import date as date_type

    app = await get_or_404(db, Application, application_id, user_id, "Application not found")

    # Fetch user profile
    profile_result = await db.execute(
        select(CvProfile)
        .where(CvProfile.user_id == user_id)
        .order_by(CvProfile.updated_at.desc())
        .limit(1)
    )
    profile = profile_result.scalar_one_or_none()

    # Fetch latest cv_version for tailored bullet context + gap analysis
    cv_result = await db.execute(
        select(CvVersion)
        .where(CvVersion.application_id == application_id, CvVersion.user_id == user_id)
        .order_by(CvVersion.created_at.desc())
        .limit(1)
    )
    cv_version = cv_result.scalar_one_or_none()

    # Fetch work experiences (prefer selected ones from tailoring)
    selected_exp_ids = cv_version.selected_experiences if cv_version else None
    if selected_exp_ids:
        exp_result = await db.execute(
            select(WorkExperience)
            .where(WorkExperience.user_id == user_id, WorkExperience.id.in_(selected_exp_ids))
        )
    else:
        exp_result = await db.execute(
            select(WorkExperience)
            .where(WorkExperience.user_id == user_id)
            .order_by(WorkExperience.date_end.desc().nullsfirst())
            .limit(5)
        )
    experiences = exp_result.scalars().all()

    # Fetch education
    edu_result = await db.execute(
        select(Education)
        .where(Education.user_id == user_id)
        .order_by(Education.date_end.desc().nullsfirst())
        .limit(2)
    )
    educations = edu_result.scalars().all()

    # Fetch activities
    act_result = await db.execute(
        select(Activity)
        .where(Activity.user_id == user_id)
        .order_by(Activity.date_end.desc().nullsfirst())
        .limit(4)
    )
    activities = act_result.scalars().all()

    jd_parsed = app.jd_parsed or {}
    company = app.company_name
    role = app.role_title or jd_parsed.get("title", "the role")
    today_date = date_type.today().strftime("%d/%m/%Y")

    # Candidate contact info
    candidate_name = (profile.full_name or "Candidate") if profile else "Candidate"
    candidate_location = (profile.location or "") if profile else ""
    candidate_phone = (profile.phone or "") if profile else ""
    candidate_email = (profile.email or "") if profile else ""

    # Build experience context: prefer accepted bullets from final_cv_json, then tailored
    # suggestions from diff_json, fall back to raw experience bullets
    experience_context_parts: list[str] = []
    if cv_version and cv_version.diff_json:
        final_cv = cv_version.final_cv_json or {}
        for exp_id, diff in list(cv_version.diff_json.items())[:6]:
            label = diff.get("label", "")
            # Use user-reviewed accepted bullets if available, otherwise suggested
            final_entry = final_cv.get(exp_id, {})
            final_bullets_raw = final_entry.get("bullets", []) if final_entry else []
            if final_bullets_raw:
                bullets = [b if isinstance(b, str) else b.get("text", "") for b in final_bullets_raw[:3]]
            else:
                suggested = diff.get("suggested_bullets", [])
                bullets = [b if isinstance(b, str) else b.get("text", "") for b in suggested[:3]]
            bullets = [b for b in bullets if b]
            if label and bullets:
                experience_context_parts.append(f"{label}:\n" + "\n".join(f"  - {b}" for b in bullets))

    if not experience_context_parts:
        for exp in experiences[:4]:
            bullets_data = exp.bullets or {}
            items = bullets_data.get("items", []) if isinstance(bullets_data, dict) else []
            if exp.company and items:
                sample = [b for b in items[:2] if isinstance(b, str)]
                if sample:
                    experience_context_parts.append(
                        f"{exp.role_title} at {exp.company}:\n" + "\n".join(f"  - {b}" for b in sample)
                    )

    # Education context
    edu_context = ""
    for edu in educations[:1]:
        if edu.institution and edu.degree:
            edu_context = f"{edu.degree} at {edu.institution}"
            if edu.date_end:
                edu_context += f" (graduating {edu.date_end.year})"

    # Activities context
    activities_context: list[str] = []
    for act in activities[:3]:
        if act.organization:
            bullets_data = act.bullets or {}
            items = bullets_data.get("items", []) if isinstance(bullets_data, dict) else []
            desc = f"{act.role_title or 'Member'} at {act.organization}"
            if items and isinstance(items[0], str):
                desc += f": {items[0]}"
            activities_context.append(desc)

    # Gap analysis strengths
    transferable_strengths: list[str] = []
    if cv_version and cv_version.gap_analysis:
        transferable_strengths = cv_version.gap_analysis.get("transferable_strengths", [])[:4]

    requirements = jd_parsed.get("requirements", [])[:6]
    skills_required = jd_parsed.get("skills_required", [])[:8]
    domain = jd_parsed.get("domain", "")
    outcome_signals = jd_parsed.get("outcome_signals", [])[:3]

    prompt = f"""Write a complete, formally formatted UK cover letter. Return it as structured JSON matching the schema.

CANDIDATE:
Name: {candidate_name}
Location/Address: {candidate_location}
Phone: {candidate_phone}
Email: {candidate_email}

APPLICATION:
Company: {company}
Role: {role}
Date: {today_date}
Domain: {domain}
{f"Key requirements: {', '.join(requirements)}" if requirements else ""}
{f"Skills sought: {', '.join(skills_required)}" if skills_required else ""}
{f"Valued outcomes: {', '.join(outcome_signals)}" if outcome_signals else ""}

CANDIDATE EXPERIENCE HIGHLIGHTS:
{chr(10).join(experience_context_parts) if experience_context_parts else "Not available"}

{f"Education: {edu_context}" if edu_context else ""}
{f"Activities & achievements: {'; '.join(activities_context)}" if activities_context else ""}
{f"Transferable strengths identified: {', '.join(transferable_strengths)}" if transferable_strengths else ""}

FIELD INSTRUCTIONS:
- candidate_lines: list of strings — [full name, street address or city, phone, email]. Use the candidate details above exactly.
- date: today's date "{today_date}"
- company_lines: list of strings — [company name, then each address line, city + postcode, country]. Use your knowledge of {company}'s main London or UK office. If unknown, use just the company name and "United Kingdom".
- salutation: "Dear Sir/Madam,"
- paragraphs: list of exactly 4 strings. Each paragraph is 3-5 sentences.
  Para 1 — Opening: introduce the candidate by name + degree/institution, state the role + team, express genuine excitement about {company}'s specific mission or values.
  Para 2 — Experience: describe the most relevant work experience with concrete technical details, outcomes, and tools from the highlights above; connect directly to this role's requirements.
  Para 3 — Breadth: highlight 2-3 complementary experiences (consulting, military, research, personal projects, extracurricular) showing problem-solving and breadth.
  Para 4 — Fit & ambition: express enthusiasm for {company}'s specific culture/product; reference 1-2 notable achievements from activities; state what contribution the candidate will make.
- closing: one sentence starting with "Thank you very much for your consideration." that ends with looking forward to discussing how they can contribute to {company}'s team.
- sign_off: "Yours sincerely,"
- candidate_name: the candidate's name only

RULES:
- British English, formal and professional
- Be specific to {company} and {role} — no generic filler
- Use actual details from the context throughout; do not invent facts
- Match tone to domain: {domain or "professional"}
"""

    client = get_openai_client()
    settings = get_settings()
    response = await client.beta.chat.completions.parse(
        model=settings.model_name,
        messages=[{"role": "user", "content": prompt}],
        response_format=_LetterParts,
        max_tokens=1600,
        temperature=0.7,
    )
    parsed = response.choices[0].message.parsed

    if not parsed:
        raise HTTPException(
            status_code=500,
            detail="Cover letter generation failed — please try again.",
        )

    # Build a flat text version from the structured parts (for clipboard copy)
    flat_lines: list[str] = [
        *parsed.candidate_lines,
        "",
        parsed.date,
        "",
        *parsed.company_lines,
        "",
        parsed.salutation,
        "",
        *[f"{p}\n" for p in parsed.paragraphs],
        parsed.closing,
        "",
        parsed.sign_off,
        parsed.candidate_name,
    ]
    flat_text = "\n".join(flat_lines)

    return CoverLetterResponse(cover_letter=flat_text, parts=parsed.model_dump())


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
