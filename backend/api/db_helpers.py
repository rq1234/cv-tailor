"""Shared database helpers to eliminate boilerplate in route handlers."""

from __future__ import annotations

import uuid
from typing import Any, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.enums import ApplicationStatus
from backend.exceptions import NotFoundError
from backend.models.tables import Activity, Application, CvProfile, CvVersion, Education, Project, Skill, TailoringRule, WorkExperience
from backend.schemas.pydantic import JdParsed

T = TypeVar("T")


async def is_master_account(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """Return True if this user is the master account — exempt from all usage limits."""
    result = await db.execute(
        select(CvProfile.email).where(CvProfile.user_id == user_id).limit(1)
    )
    email = result.scalar_one_or_none()
    return email == get_settings().master_account_email


async def get_or_404(
    db: AsyncSession,
    model: Type[T],
    obj_id: uuid.UUID,
    user_id: uuid.UUID,
    detail: str = "Not found",
) -> T:
    """Fetch a single row scoped to user_id, or raise NotFoundError (HTTP 404)."""
    result = await db.execute(
        select(model).where(
            model.id == obj_id,  # type: ignore[attr-defined]
            model.user_id == user_id,  # type: ignore[attr-defined]
        )
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise NotFoundError(detail)
    return obj  # type: ignore[return-value]


async def delete_or_404(
    db: AsyncSession,
    model: Type[Any],
    obj_id: uuid.UUID,
    user_id: uuid.UUID,
    detail: str = "Not found",
) -> dict:
    """Fetch and delete a row scoped to user_id, or raise NotFoundError (HTTP 404)."""
    obj = await get_or_404(db, model, obj_id, user_id, detail)
    await db.delete(obj)
    await db.commit()
    return {"status": "deleted"}


def apply_update(obj: Any, update_data: dict) -> None:
    """Set fields on an ORM object from a dict of {field: value}."""
    for field, value in update_data.items():
        setattr(obj, field, value)


async def fetch_latest_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> CvProfile | None:
    """Return the most recently updated CvProfile for a user, or None."""
    result = await db.execute(
        select(CvProfile)
        .where(CvProfile.user_id == user_id)
        .order_by(CvProfile.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def fetch_active_rules_text(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> str:
    """Return active tailoring rules formatted as a single string.

    Shared between the pipeline graph and the re-tailor route to avoid duplication.
    Returns an empty string when no rules are active.
    """
    result = await db.execute(
        select(TailoringRule).where(
            TailoringRule.is_active.is_(True),
            TailoringRule.user_id == user_id,
        )
    )
    rules = result.scalars().all()
    if not rules:
        return ""
    return "Additional tailoring rules to apply:\n" + "\n".join(
        f"- {r.rule_text}" for r in rules
    )


async def fetch_experience_meta(
    db: AsyncSession,
    exp_ids: list[str],
    user_id: uuid.UUID,
) -> dict[str, dict]:
    """Return display metadata for a list of work experience IDs."""
    if not exp_ids:
        return {}
    exp_uuids = [uuid.UUID(eid) for eid in exp_ids]
    result = await db.execute(
        select(WorkExperience).where(
            WorkExperience.id.in_(exp_uuids),
            WorkExperience.user_id == user_id,
        )
    )
    return {
        str(exp.id): {
            "company": exp.company,
            "role_title": exp.role_title,
            "date_start": exp.date_start.isoformat() if exp.date_start else None,
            "date_end": exp.date_end.isoformat() if exp.date_end else None,
            "is_current": exp.is_current,
        }
        for exp in result.scalars()
    }


async def fetch_project_meta(
    db: AsyncSession,
    proj_ids: list[str],
    user_id: uuid.UUID,
) -> dict[str, dict]:
    """Return display metadata for a list of project IDs."""
    if not proj_ids:
        return {}
    proj_uuids = [uuid.UUID(pid) for pid in proj_ids]
    result = await db.execute(
        select(Project).where(
            Project.id.in_(proj_uuids),
            Project.user_id == user_id,
        )
    )
    return {
        str(proj.id): {
            "name": proj.name,
            "description": proj.description,
            "date_start": proj.date_start.isoformat() if proj.date_start else None,
            "date_end": proj.date_end.isoformat() if proj.date_end else None,
        }
        for proj in result.scalars()
    }


async def fetch_activity_meta(
    db: AsyncSession,
    act_ids: list[str],
    user_id: uuid.UUID,
) -> dict[str, dict]:
    """Return display metadata for a list of activity IDs."""
    if not act_ids:
        return {}
    act_uuids = [uuid.UUID(aid) for aid in act_ids]
    result = await db.execute(
        select(Activity).where(
            Activity.id.in_(act_uuids),
            Activity.user_id == user_id,
        )
    )
    return {
        str(act.id): {
            "organization": act.organization,
            "role_title": act.role_title,
            "date_start": act.date_start.isoformat() if act.date_start else None,
            "date_end": act.date_end.isoformat() if act.date_end else None,
            "is_current": act.is_current,
        }
        for act in result.scalars()
    }


async def fetch_education_data(
    db: AsyncSession,
    edu_ids: list,
    user_id: uuid.UUID,
) -> list[dict]:
    """Return structured education rows for export."""
    if not edu_ids:
        return []
    result = await db.execute(
        select(Education).where(
            Education.id.in_(edu_ids),
            Education.user_id == user_id,
        )
    )
    rows = []
    for edu in result.scalars():
        achievements = []
        if isinstance(edu.achievements, list):
            achievements = edu.achievements
        elif isinstance(edu.achievements, dict):
            achievements = edu.achievements.get("items", [])
        modules = []
        if isinstance(edu.modules, list):
            modules = edu.modules
        elif isinstance(edu.modules, dict):
            modules = edu.modules.get("items", [])
        rows.append({
            "id": str(edu.id),
            "institution": edu.institution,
            "degree": edu.degree,
            "grade": edu.grade,
            "location": edu.location,
            "date_start": edu.date_start.isoformat() if edu.date_start else None,
            "date_end": edu.date_end.isoformat() if edu.date_end else None,
            "achievements": achievements,
            "modules": modules,
        })
    return rows


async def fetch_skills_data(
    db: AsyncSession,
    skill_ids: list,
    user_id: uuid.UUID,
) -> dict[str, list[str]]:
    """Return skills grouped by category for export."""
    if not skill_ids:
        return {}
    result = await db.execute(
        select(Skill).where(
            Skill.id.in_(skill_ids),
            Skill.user_id == user_id,
        )
    )
    skills_by_id = {s.id: s for s in result.scalars()}
    skills_data: dict[str, list[str]] = {}
    for sid in skill_ids:
        skill = skills_by_id.get(sid)
        if not skill:
            continue
        cat = (skill.category or "Other").capitalize()
        skills_data.setdefault(cat, []).append(skill.name)
    return skills_data


async def find_similar_applications(
    db: AsyncSession,
    current_app: Application,
    user_id: uuid.UUID,
) -> list[dict]:
    """Return up to 3 past applications similar to the current one by domain + keyword overlap."""
    if not current_app.jd_parsed or not isinstance(current_app.jd_parsed, dict):
        return []

    current_jd: JdParsed = current_app.jd_parsed  # type: ignore[assignment]
    current_domain = (current_jd.get("domain") or "").lower()
    current_keywords = set(
        kw.lower() for kw in (current_jd.get("keywords") or [])
    )

    other_apps_result = await db.execute(
        select(Application).where(
            Application.user_id == user_id,
            Application.id != current_app.id,
            Application.jd_parsed.isnot(None),
            Application.status.in_([ApplicationStatus.REVIEW, ApplicationStatus.COMPLETE]),
        )
    )
    other_apps = other_apps_result.scalars().all()

    if not other_apps:
        return []

    other_app_ids = [a.id for a in other_apps]
    cv_result = await db.execute(
        select(CvVersion.application_id, CvVersion.ats_score)
        .where(
            CvVersion.user_id == user_id,
            CvVersion.application_id.in_(other_app_ids),
            CvVersion.ats_score.isnot(None),
        )
        .order_by(CvVersion.application_id, CvVersion.created_at.desc())
        .distinct(CvVersion.application_id)
    )
    ats_by_app = {str(app_id): score for app_id, score in cv_result.all()}

    scored = []
    for other in other_apps:
        if not other.jd_parsed or not isinstance(other.jd_parsed, dict):
            continue
        other_jd: JdParsed = other.jd_parsed  # type: ignore[assignment]
        other_domain = (other_jd.get("domain") or "").lower()
        other_keywords = set(
            kw.lower() for kw in (other_jd.get("keywords") or [])
        )
        score = 0.0
        if current_domain and current_domain == other_domain:
            score += 2.0
        if current_keywords and other_keywords:
            union = current_keywords | other_keywords
            intersection = current_keywords & other_keywords
            score += (len(intersection) / len(union)) * 10.0 if union else 0.0
        if score > 0:
            scored.append((score, other))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "id": str(a.id),
            "company_name": a.company_name,
            "role_title": a.role_title,
            "ats_score": ats_by_app.get(str(a.id)),
            "domain": (a.jd_parsed.get("domain") or None) if a.jd_parsed else None,
            "created_at": a.created_at.isoformat(),
        }
        for _, a in scored[:3]
    ]
