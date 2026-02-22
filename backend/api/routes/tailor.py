"""Tailoring pipeline route — triggers the full agent pipeline with SSE streaming."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend.agents.cv_tailor import tailor_activities, tailor_experiences, tailor_projects
from backend.agents.gap_analyzer import analyze_gaps
from backend.agents.graph import run_pipeline
from backend.api.auth import get_current_user
from backend.api.db_helpers import fetch_active_rules_text
from backend.models.database import get_db
from backend.models.tables import Activity, Application, CvVersion, Education, Project, Skill, WorkExperience
from backend.schemas.pydantic import RegenerateBulletRequest, TailorRunRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tailor", tags=["tailor"])
limiter = Limiter(key_func=get_remote_address)

# Maximum time a single pipeline run is allowed to take (10 minutes).
_PIPELINE_TIMEOUT_S = 600

# In-flight guard: tracks which users currently have a pipeline running.
# Single-process safe (Render Starter = 1 process). For multi-process, move to Redis.
_active_tailoring: set[str] = set()


@router.post("/run")
@limiter.limit("20/hour")
async def run_tailoring(
    request: Request,
    body: TailorRunRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Trigger the full agent pipeline for an application.

    Returns SSE stream with progress updates, then final result.
    """
    # Validate application exists
    result = await db.execute(
        select(Application).where(
            Application.id == body.application_id,
            Application.user_id == user_id,
        )
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    user_key = str(user_id)

    # Reject concurrent pipelines for the same user.
    if user_key in _active_tailoring:
        raise HTTPException(
            status_code=409,
            detail="A tailoring job is already running for your account. Please wait for it to finish.",
        )

    async def event_generator():
        step_queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

        async def on_step(step_name: str, status: str = "running"):
            await step_queue.put((step_name, status))

        step_labels = {
            "parsing_jd": "Parsing job description...",
            "selecting_experiences": "Selecting best experiences...",
            "analyzing_gaps": "Analyzing gaps...",
            "tailoring_cv": "Tailoring experience bullets...",
            "tailoring_projects": "Tailoring project & activity bullets...",
            "checking_ats": "Checking ATS compliance...",
            "saving": "Saving results...",
        }

        # Build manual_selection dict if the user pinned specific IDs
        manual_selection = None
        if any([body.pinned_experiences, body.pinned_projects, body.pinned_activities,
                body.pinned_education, body.pinned_skills]):
            manual_selection = {
                "selected_experiences": [{"id": str(uid)} for uid in (body.pinned_experiences or [])],
                "selected_projects": [str(uid) for uid in (body.pinned_projects or [])],
                "selected_activities": [str(uid) for uid in (body.pinned_activities or [])],
                "selected_education": [str(uid) for uid in (body.pinned_education or [])],
                "selected_skills": [str(uid) for uid in (body.pinned_skills or [])],
            }

        _active_tailoring.add(user_key)
        pipeline_task = asyncio.create_task(
            asyncio.wait_for(
                run_pipeline(str(body.application_id), app.jd_raw, db, user_id, on_step, manual_selection),
                timeout=_PIPELINE_TIMEOUT_S,
            )
        )

        try:
            completed_steps = 0
            total_steps = 7
            while not pipeline_task.done() or not step_queue.empty():
                try:
                    step, status = await asyncio.wait_for(step_queue.get(), timeout=0.5)
                    if status == "done":
                        completed_steps += 1
                    yield {
                        "event": "step",
                        "data": json.dumps({
                            "step": step,
                            "status": status,
                            "label": step_labels.get(step, step),
                            "progress": completed_steps,
                            "total": total_steps,
                        }),
                    }
                except asyncio.TimeoutError:
                    continue

            # Collect final result — raises if the task itself raised.
            state = await pipeline_task

            if state.error:
                yield {"event": "error", "data": json.dumps({"error": state.error})}
            else:
                yield {
                    "event": "complete",
                    "data": json.dumps({
                        "cv_version_id": state.cv_version_id,
                        "ats_score": state.ats_result.get("ats_score", 0),
                        "ats_warnings_count": len(state.ats_result.get("warnings", [])),
                        "diffs_count": len(state.tailored_experiences),
                    }),
                }

        except asyncio.TimeoutError:
            pipeline_task.cancel()
            logger.error("Pipeline timed out after %ds for application %s", _PIPELINE_TIMEOUT_S, body.application_id)
            yield {"event": "error", "data": json.dumps({"error": "Tailoring timed out. Please try again."})}

        except asyncio.CancelledError:
            pipeline_task.cancel()
            return

        except Exception:
            pipeline_task.cancel()
            logger.exception("Pipeline raised unexpectedly for application %s", body.application_id)
            yield {"event": "error", "data": json.dumps({"error": "An unexpected error occurred. Please try again."})}

        finally:
            _active_tailoring.discard(user_key)

    return EventSourceResponse(event_generator())


# ── Private helpers for get_tailor_result ──────────────────────────────────

async def _fetch_experience_meta(
    db: AsyncSession,
    exp_ids: list[str],
    user_id: uuid.UUID,
) -> dict[str, dict]:
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


async def _fetch_project_meta(
    db: AsyncSession,
    proj_ids: list[str],
    user_id: uuid.UUID,
) -> dict[str, dict]:
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


async def _fetch_activity_meta(
    db: AsyncSession,
    act_ids: list[str],
    user_id: uuid.UUID,
) -> dict[str, dict]:
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


async def _fetch_education_data(
    db: AsyncSession,
    edu_ids: list,
    user_id: uuid.UUID,
) -> list[dict]:
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


async def _fetch_skills_data(
    db: AsyncSession,
    skill_ids: list,
    user_id: uuid.UUID,
) -> dict[str, list[str]]:
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


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/result/{application_id}")
async def get_tailor_result(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Get the tailoring result for an application (non-streaming)."""
    result = await db.execute(
        select(CvVersion)
        .where(
            CvVersion.application_id == application_id,
            CvVersion.user_id == user_id,
        )
        .order_by(CvVersion.created_at.desc())
        .limit(1)
    )
    cv_version = result.scalar_one_or_none()
    if not cv_version:
        raise HTTPException(status_code=404, detail="No tailoring result found")

    # Get ATS result from the application
    app_result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.user_id == user_id,
        )
    )
    app = app_result.scalar_one()

    # Separate IDs by type from diff_json
    diff = cv_version.diff_json or {}
    exp_ids = [k for k, v in diff.items() if v.get("type", "experience") == "experience"]
    proj_ids = [k for k, v in diff.items() if v.get("type") == "project"]
    act_ids = [k for k, v in diff.items() if v.get("type") == "activity"]
    edu_ids = cv_version.selected_education or []
    skill_ids = cv_version.selected_skills or []

    # SQLAlchemy AsyncSession does not allow concurrent operations on the same session;
    # queries must run sequentially.
    experience_meta = await _fetch_experience_meta(db, exp_ids, user_id)
    project_meta = await _fetch_project_meta(db, proj_ids, user_id)
    activity_meta = await _fetch_activity_meta(db, act_ids, user_id)
    education_data = await _fetch_education_data(db, edu_ids, user_id)
    skills_data = await _fetch_skills_data(db, skill_ids, user_id)

    return {
        "cv_version_id": str(cv_version.id),
        "application_id": str(application_id),
        "diff_json": cv_version.diff_json,
        "experience_meta": experience_meta,
        "project_meta": project_meta,
        "activity_meta": activity_meta,
        "education_data": education_data,
        "skills_data": skills_data,
        "selected_experiences": [str(e) for e in (cv_version.selected_experiences or [])],
        "selected_education": [str(e) for e in (cv_version.selected_education or [])],
        "selected_projects": [str(p) for p in (cv_version.selected_projects or [])],
        "selected_activities": [str(a) for a in (cv_version.selected_activities or [])],
        "selected_skills": [str(s) for s in (cv_version.selected_skills or [])],
        "accepted_changes": cv_version.accepted_changes,
        "rejected_changes": cv_version.rejected_changes,
        "ats_score": cv_version.ats_score,
        "ats_warnings": cv_version.ats_warnings or [],
        "status": app.status,
    }


@router.put("/cv-versions/{version_id}/accept-changes")
async def accept_changes(
    version_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Save user's accepted/rejected diffs."""
    result = await db.execute(
        select(CvVersion).where(
            CvVersion.id == version_id,
            CvVersion.user_id == user_id,
        )
    )
    cv_version = result.scalar_one_or_none()
    if not cv_version:
        raise HTTPException(status_code=404, detail="CV version not found")

    accepted_changes = body.get("accepted_changes", {})
    rejected_changes = body.get("rejected_changes", {})

    # Validate accepted_changes structure
    if not isinstance(accepted_changes, dict):
        raise HTTPException(status_code=400, detail="accepted_changes must be a dictionary")

    if not isinstance(rejected_changes, dict):
        raise HTTPException(status_code=400, detail="rejected_changes must be a dictionary")

    _MAX_BULLET_LEN = 600  # ~4 wrapped lines; anything longer would break LaTeX pagination

    # Validate each entry in accepted_changes
    diff_json = cv_version.diff_json or {}
    for key, value in accepted_changes.items():
        if value is None:
            raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'] cannot be null")

        if key in diff_json:
            if not isinstance(value, list):
                raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'] must be a list of bullet strings")
            for i, bullet in enumerate(value):
                if not isinstance(bullet, str):
                    raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'][{i}] must be a string")
                if len(bullet) > _MAX_BULLET_LEN:
                    raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'][{i}] exceeds maximum length of {_MAX_BULLET_LEN} characters")

        elif key.startswith("education_"):
            if isinstance(value, dict):
                achievements = value.get("achievements", [])
                modules = value.get("modules", [])
                if not isinstance(achievements, list) or not isinstance(modules, list):
                    raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'] must contain list fields")
                for i, item in enumerate(achievements):
                    if not isinstance(item, str):
                        raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'].achievements[{i}] must be a string")
                    if len(item) > _MAX_BULLET_LEN:
                        raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'].achievements[{i}] exceeds maximum length of {_MAX_BULLET_LEN} characters")
                for i, item in enumerate(modules):
                    if not isinstance(item, str):
                        raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'].modules[{i}] must be a string")
                    if len(item) > _MAX_BULLET_LEN:
                        raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'].modules[{i}] exceeds maximum length of {_MAX_BULLET_LEN} characters")
            else:
                if not isinstance(value, list):
                    raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'] must be a list")
                for i, item in enumerate(value):
                    if not isinstance(item, str):
                        raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'][{i}] must be a string")
                    if len(item) > _MAX_BULLET_LEN:
                        raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'][{i}] exceeds maximum length of {_MAX_BULLET_LEN} characters")

        elif key.startswith("skills_"):
            if not isinstance(value, list):
                raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'] must be a list of skill strings")
            for i, skill in enumerate(value):
                if not isinstance(skill, str):
                    raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'][{i}] must be a string")

    # Validate rejected_changes structure
    for key, indices in rejected_changes.items():
        if not isinstance(indices, list):
            raise HTTPException(status_code=400, detail=f"rejected_changes['{key}'] must be a list of indices")
        for idx in indices:
            if not isinstance(idx, int):
                raise HTTPException(status_code=400, detail=f"rejected_changes['{key}'] contains non-integer index")

    cv_version.accepted_changes = accepted_changes
    cv_version.rejected_changes = rejected_changes

    # Build final CV JSON from accepted changes
    final_cv = {}
    diff = cv_version.diff_json or {}
    for exp_id, exp_diff in diff.items():
        accepted = cv_version.accepted_changes.get(exp_id, {})
        if accepted:
            final_cv[exp_id] = accepted
        else:
            final_cv[exp_id] = {"bullets": exp_diff.get("original_bullets", [])}

    cv_version.final_cv_json = final_cv
    await db.commit()

    return {"status": "saved", "cv_version_id": str(version_id)}


@router.post("/re-tailor/{application_id}")
async def re_tailor_application(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Re-run tailoring for an existing application without changing selection.

    This applies the latest tailoring logic (including line optimization) to
    the existing selected experiences/projects/activities.
    """
    # Get application
    app_result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.user_id == user_id,
        )
    )
    app = app_result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if not app.jd_parsed:
        raise HTTPException(status_code=400, detail="Application has no parsed JD")

    # Get latest CV version
    cv_result = await db.execute(
        select(CvVersion)
        .where(
            CvVersion.application_id == application_id,
            CvVersion.user_id == user_id,
        )
        .order_by(CvVersion.created_at.desc())
        .limit(1)
    )
    cv_version = cv_result.scalar_one_or_none()
    if not cv_version:
        raise HTTPException(status_code=404, detail="No CV version found")

    rules_text = await fetch_active_rules_text(db, user_id)

    # Re-fetch selected experiences and re-tailor
    exp_ids = cv_version.selected_experiences or []
    if exp_ids:
        exp_result = await db.execute(
            select(WorkExperience).where(
                WorkExperience.id.in_(exp_ids),
                WorkExperience.user_id == user_id,
            )
        )
        experiences = exp_result.scalars().all()
        exp_dicts = [
            {
                "id": str(e.id),
                "company": e.company,
                "role_title": e.role_title,
                "bullets": e.bullets,
            }
            for e in experiences
        ]

        # Re-run gap analysis
        gap_result = await analyze_gaps(exp_dicts, app.jd_parsed, None)
        gap_analysis = gap_result.model_dump()

        # Re-tailor experiences
        tailored_exp = await tailor_experiences(
            exp_dicts, app.jd_parsed, gap_analysis, rules_text
        )
    else:
        tailored_exp = []

    # Re-tailor projects
    proj_ids = cv_version.selected_projects or []
    if proj_ids:
        proj_result = await db.execute(
            select(Project).where(
                Project.id.in_(proj_ids),
                Project.user_id == user_id,
            )
        )
        projects = proj_result.scalars().all()
        proj_dicts = [
            {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "bullets": p.bullets,
            }
            for p in projects
        ]
        tailored_proj = await tailor_projects(proj_dicts, app.jd_parsed, rules_text)
    else:
        tailored_proj = []

    # Re-tailor activities
    act_ids = cv_version.selected_activities or []
    if act_ids:
        act_result = await db.execute(
            select(Activity).where(
                Activity.id.in_(act_ids),
                Activity.user_id == user_id,
            )
        )
        activities = act_result.scalars().all()
        act_dicts = [
            {
                "id": str(a.id),
                "organization": a.organization,
                "role_title": a.role_title,
                "bullets": a.bullets,
            }
            for a in activities
        ]
        tailored_act = await tailor_activities(act_dicts, app.jd_parsed, rules_text)
    else:
        tailored_act = []

    # Build new diff_json
    diff_json = {}
    for te in tailored_exp:
        diff_json[te.experience_id] = {
            "type": "experience",
            "original_bullets": te.original_bullets,
            "suggested_bullets": [
                {"text": b.text, "has_placeholder": b.has_placeholder, "outcome_type": b.outcome_type}
                for b in te.suggested_bullets
            ],
            "changes_made": te.changes_made,
            "confidence": te.confidence,
            "requirements_addressed": te.requirements_addressed,
        }

    for tp in tailored_proj:
        diff_json[tp.project_id] = {
            "type": "project",
            "original_bullets": tp.original_bullets,
            "suggested_bullets": [
                {"text": b.text, "has_placeholder": b.has_placeholder, "outcome_type": b.outcome_type}
                for b in tp.suggested_bullets
            ],
            "changes_made": tp.changes_made,
            "confidence": tp.confidence,
            "requirements_addressed": tp.requirements_addressed,
        }

    for ta in tailored_act:
        diff_json[ta.activity_id] = {
            "type": "activity",
            "original_bullets": ta.original_bullets,
            "suggested_bullets": [
                {"text": b.text, "has_placeholder": b.has_placeholder, "outcome_type": b.outcome_type}
                for b in ta.suggested_bullets
            ],
            "changes_made": ta.changes_made,
            "confidence": ta.confidence,
            "requirements_addressed": ta.requirements_addressed,
        }

    # Update CV version — preserve user's accepted/rejected decisions
    cv_version.diff_json = diff_json
    await db.commit()

    return {
        "status": "re-tailored",
        "cv_version_id": str(cv_version.id),
        "diffs_count": len(diff_json),
    }


@router.post("/regenerate-bullet")
async def regenerate_bullet(
    body: RegenerateBulletRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Re-run tailoring for a single bullet and return the new suggestion.

    Does not persist the result — the frontend patches its local state.
    """
    # 1. Fetch application (ownership check + jd_parsed)
    app_result = await db.execute(
        select(Application).where(
            Application.id == body.application_id,
            Application.user_id == user_id,
        )
    )
    app = app_result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if not app.jd_parsed:
        raise HTTPException(status_code=400, detail="Application has no parsed JD")

    # 2. Fetch latest CvVersion to read diff_json
    cv_result = await db.execute(
        select(CvVersion)
        .where(
            CvVersion.application_id == body.application_id,
            CvVersion.user_id == user_id,
        )
        .order_by(CvVersion.created_at.desc())
        .limit(1)
    )
    cv_version = cv_result.scalar_one_or_none()
    if not cv_version:
        raise HTTPException(status_code=404, detail="No CV version found")

    diff = cv_version.diff_json or {}
    entry = diff.get(body.experience_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found in diff_json")

    original_bullets = entry.get("original_bullets", [])
    if body.bullet_index < 0 or body.bullet_index >= len(original_bullets):
        raise HTTPException(status_code=400, detail="bullet_index out of range")

    original_bullet = original_bullets[body.bullet_index]
    entity_type = entry.get("type", "experience")
    exp_id_str = body.experience_id

    rules_text = await fetch_active_rules_text(db, user_id)

    # 3. Fetch the entity and call the appropriate tailor function with just this bullet
    if entity_type == "experience":
        ent_result = await db.execute(
            select(WorkExperience).where(
                WorkExperience.id == uuid.UUID(exp_id_str),
                WorkExperience.user_id == user_id,
            )
        )
        entity = ent_result.scalar_one_or_none()
        if not entity:
            raise HTTPException(status_code=404, detail="Work experience not found")

        tailored = await tailor_experiences(
            [{"id": exp_id_str, "company": entity.company, "role_title": entity.role_title, "bullets": [original_bullet]}],
            app.jd_parsed,
            None,
            rules_text,
        )
        bullet = tailored[0].suggested_bullets[0]

    elif entity_type == "project":
        ent_result = await db.execute(
            select(Project).where(
                Project.id == uuid.UUID(exp_id_str),
                Project.user_id == user_id,
            )
        )
        entity = ent_result.scalar_one_or_none()
        if not entity:
            raise HTTPException(status_code=404, detail="Project not found")

        tailored = await tailor_projects(
            [{"id": exp_id_str, "name": entity.name, "description": entity.description, "bullets": [original_bullet]}],
            app.jd_parsed,
            rules_text,
        )
        bullet = tailored[0].suggested_bullets[0]

    elif entity_type == "activity":
        ent_result = await db.execute(
            select(Activity).where(
                Activity.id == uuid.UUID(exp_id_str),
                Activity.user_id == user_id,
            )
        )
        entity = ent_result.scalar_one_or_none()
        if not entity:
            raise HTTPException(status_code=404, detail="Activity not found")

        tailored = await tailor_activities(
            [{"id": exp_id_str, "organization": entity.organization, "role_title": entity.role_title, "bullets": [original_bullet]}],
            app.jd_parsed,
            rules_text,
        )
        bullet = tailored[0].suggested_bullets[0]

    else:
        raise HTTPException(status_code=400, detail=f"Unknown entity type: {entity_type}")

    return {
        "suggested_bullet": {
            "text": bullet.text,
            "has_placeholder": bullet.has_placeholder,
            "outcome_type": bullet.outcome_type,
        }
    }
