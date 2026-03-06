"""Build the CV template context dict from a CvVersion and its referenced DB records."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db_helpers import fetch_latest_profile
from backend.models.tables import (
    Activity,
    CvVersion,
    Education,
    Project,
    Skill,
    WorkExperience,
)
from backend.utils import extract_bullet_texts, split_description_to_bullets

from ._fitting import (
    _LINE_BUDGET_1PAGE,
    _LINE_BUDGET_2PAGE,
    _compute_page_limits,
    _fit_content_to_page,
)
from ._text import (
    _dedupe_preserve_order,
    _format_date,
    _normalize_bullets,
)


async def _build_cv_context(
    db: AsyncSession,
    cv_version: CvVersion,
    user_id: uuid.UUID,
) -> dict:
    """Build the template context dict from a CvVersion and its referenced records."""
    # Profile
    profile_row = await fetch_latest_profile(db, user_id)
    profile = {}
    if profile_row:
        profile = {
            "name": profile_row.full_name,
            "email": profile_row.email,
            "phone": profile_row.phone,
            "location": profile_row.location,
            "linkedin_url": profile_row.linkedin_url,
            "portfolio_url": profile_row.portfolio_url,
            "summary": profile_row.summary,
        }

    max_pages = getattr(profile_row, "max_resume_pages", 1) if profile_row else 1
    bullet_cap_exp = 5 if max_pages >= 2 else 3
    bullet_cap_act = 4 if max_pages >= 2 else 2

    # Work experiences — sorted by date descending (most recent first)
    experiences = []
    exp_ids = cv_version.selected_experiences or []
    if exp_ids:
        result = await db.execute(
            select(WorkExperience)
            .where(
                WorkExperience.id.in_(exp_ids),
                WorkExperience.user_id == user_id,
            )
            .order_by(WorkExperience.date_start.desc().nullslast())
        )
        for exp in result.scalars().all():
            exp_id_str = str(exp.id)
            final_cv = cv_version.final_cv_json or {}
            accepted = cv_version.accepted_changes or {}

            if exp_id_str in accepted:
                bullets = accepted[exp_id_str]
                if isinstance(bullets, dict):
                    bullets = bullets.get("bullets", [])
            elif exp_id_str in final_cv:
                bullets = final_cv[exp_id_str]
                if isinstance(bullets, dict):
                    bullets = bullets.get("bullets", [])
            else:
                bullets = extract_bullet_texts(exp.bullets)

            if isinstance(bullets, list):
                bullets = _normalize_bullets(bullets)
            bullets = bullets[:bullet_cap_exp] if isinstance(bullets, list) else []

            experiences.append({
                "company": exp.company,
                "role_title": exp.role_title,
                "location": exp.location,
                "date_start": _format_date(exp.date_start),
                "date_end": "Present" if exp.is_current else _format_date(exp.date_end),
                "bullets": bullets if isinstance(bullets, list) else [],
            })

    # Education
    education = []
    edu_ids = cv_version.selected_education or []
    accepted = cv_version.accepted_changes or {}
    if edu_ids:
        result = await db.execute(
            select(Education).where(
                Education.id.in_(edu_ids),
                Education.user_id == user_id,
            )
        )
        for edu in result.scalars().all():
            edu_id_str = str(edu.id)

            if f"education_{edu_id_str}" in accepted:
                manual_items = accepted[f"education_{edu_id_str}"]
                if isinstance(manual_items, dict):
                    achievements = manual_items.get("achievements", [])
                    modules = manual_items.get("modules", [])
                    if isinstance(achievements, str):
                        achievements = [a.strip() for a in achievements.split(",") if a.strip()]
                    if isinstance(modules, str):
                        modules = [m.strip() for m in modules.split(",") if m.strip()]
                elif isinstance(manual_items, list):
                    achievements = manual_items[:2]
                    modules = []
                else:
                    achievements = []
                    modules = []
            else:
                achievements = []
                if isinstance(edu.achievements, list):
                    achievements = edu.achievements
                elif isinstance(edu.achievements, dict):
                    achievements = edu.achievements.get("items", [])
                elif isinstance(edu.achievements, str):
                    achievements = [a.strip() for a in edu.achievements.split(",") if a.strip()]
                modules = []
                if isinstance(edu.modules, list):
                    modules = edu.modules
                elif isinstance(edu.modules, dict):
                    modules = edu.modules.get("items", [])
                elif isinstance(edu.modules, str):
                    modules = [m.strip() for m in edu.modules.split(",") if m.strip()]

            if isinstance(achievements, list):
                achievements = [str(a).strip() for a in achievements if str(a).strip()]
            if isinstance(modules, list):
                modules = [str(m).strip() for m in modules if str(m).strip()]
            achievements_cap = 5 if max_pages >= 2 else 3
            achievements = achievements[:achievements_cap] if isinstance(achievements, list) else []
            modules = modules[:4] if isinstance(modules, list) else []

            education.append({
                "institution": edu.institution,
                "degree": edu.degree,
                "grade": edu.grade,
                "date_start": _format_date(edu.date_start),
                "date_end": _format_date(edu.date_end),
                "location": edu.location,
                "achievements": achievements,
                "modules": modules,
            })

    # Projects — sorted by date descending, deduplicated by name
    projects = []
    seen_proj_names: set[str] = set()
    proj_ids = cv_version.selected_projects or []
    if proj_ids:
        result = await db.execute(
            select(Project)
            .where(Project.id.in_(proj_ids), Project.user_id == user_id)
            .order_by(Project.date_start.desc().nullslast())
        )
        for proj in result.scalars().all():
            name_lower = (proj.name or "").strip().lower()
            if name_lower and name_lower in seen_proj_names:
                continue
            if name_lower:
                seen_proj_names.add(name_lower)
            proj_id_str = str(proj.id)
            final_cv = cv_version.final_cv_json or {}
            accepted = cv_version.accepted_changes or {}

            if proj_id_str in accepted:
                bullets = accepted[proj_id_str]
                if isinstance(bullets, dict):
                    bullets = bullets.get("bullets", [])
            elif proj_id_str in final_cv:
                bullets = final_cv[proj_id_str]
                if isinstance(bullets, dict):
                    bullets = bullets.get("bullets", [])
            else:
                bullets = extract_bullet_texts(proj.bullets)

            if isinstance(bullets, list):
                bullets = _normalize_bullets(bullets)
            bullets = bullets[:3] if isinstance(bullets, list) else []
            if not bullets and proj.description:
                bullets = split_description_to_bullets(proj.description)[:3]

            projects.append({
                "name": proj.name,
                "description": proj.description,
                "url": proj.url,
                "date_start": _format_date(proj.date_start),
                "date_end": _format_date(proj.date_end),
                "bullets": bullets if isinstance(bullets, list) else [],
                "skill_tags": proj.skill_tags or [],
            })

    # Activities — sorted by date descending
    activities = []
    act_ids = cv_version.selected_activities or []
    if act_ids:
        result = await db.execute(
            select(Activity)
            .where(Activity.id.in_(act_ids), Activity.user_id == user_id)
            .order_by(Activity.date_start.desc().nullslast())
        )
        for act in result.scalars().all():
            act_id_str = str(act.id)
            final_cv = cv_version.final_cv_json or {}
            accepted = cv_version.accepted_changes or {}

            if act_id_str in accepted:
                bullets = accepted[act_id_str]
                if isinstance(bullets, dict):
                    bullets = bullets.get("bullets", [])
            elif act_id_str in final_cv:
                bullets = final_cv[act_id_str]
                if isinstance(bullets, dict):
                    bullets = bullets.get("bullets", [])
            else:
                bullets = extract_bullet_texts(act.bullets)

            if isinstance(bullets, list):
                bullets = _normalize_bullets(bullets)
            bullets = bullets[:bullet_cap_act] if isinstance(bullets, list) else []

            activities.append({
                "organization": act.organization,
                "role_title": act.role_title,
                "location": act.location,
                "date_start": _format_date(act.date_start),
                "date_end": "Present" if act.is_current else _format_date(act.date_end),
                "bullets": bullets if isinstance(bullets, list) else [],
            })

    # Skills grouped by category, preserving JD-relevance priority order
    skills_by_category: dict[str, list[str]] = {}
    skill_ids = cv_version.selected_skills or []
    accepted = cv_version.accepted_changes or {}
    if skill_ids:
        result = await db.execute(
            select(Skill).where(Skill.id.in_(skill_ids), Skill.user_id == user_id)
        )
        skills_by_id = {skill.id: skill for skill in result.scalars().all()}
        seen_skills: set[str] = set()
        seen_categories: set[str] = set()

        for sid in skill_ids:
            skill = skills_by_id.get(sid)
            if not skill:
                continue
            name_lower = skill.name.strip().lower()
            if name_lower in seen_skills:
                continue
            seen_skills.add(name_lower)
            cat = (skill.category or "Other").capitalize()
            # Normalise DB category values → LaTeX section keys
            if cat in ("Language", "Tool", "Other"):
                cat = "Technical"
            elif cat == "Interest":
                cat = "Interests"

            skill_key = f"skills_{cat}"
            if skill_key in accepted and cat not in seen_categories:
                seen_categories.add(cat)
                manual_skills = accepted[skill_key]
                if isinstance(manual_skills, list) and len(manual_skills) > 0:
                    parsed_skills = [s.strip() for s in manual_skills if isinstance(s, str) and s.strip()]
                    parsed_skills = _dedupe_preserve_order(parsed_skills)
                    if parsed_skills:
                        skills_by_category[cat] = parsed_skills
                continue

            if cat not in skills_by_category:
                skills_by_category[cat] = []
            skills_by_category[cat].append(skill.name)

        for cat, items in list(skills_by_category.items()):
            skills_by_category[cat] = _dedupe_preserve_order(items)

    limits = _compute_page_limits(bool(projects), bool(activities), max_pages)
    ctx_experiences = experiences[: limits["exp"]]
    ctx_projects = projects[: limits["proj"]] if limits["proj"] else projects
    ctx_activities = activities[: limits["act"]] if limits["act"] else activities

    line_budget = _LINE_BUDGET_2PAGE if max_pages >= 2 else _LINE_BUDGET_1PAGE
    _fit_content_to_page(
        ctx_experiences,
        education,
        ctx_projects,
        ctx_activities,
        skills_by_category,
        line_budget,
    )

    return {
        "profile": profile,
        "experiences": ctx_experiences,
        "education": education,
        "projects": ctx_projects,
        "activities": ctx_activities,
        "skills_by_category": skills_by_category,
    }
