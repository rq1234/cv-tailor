"""Tailoring pipeline route — triggers the full agent pipeline with SSE streaming."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend.agents.cv_tailor import tailor_activities, tailor_experiences, tailor_projects
from backend.agents.gap_analyzer import analyze_gaps
from backend.agents.graph import run_pipeline
from backend.api.auth import get_current_user
from backend.api.db_helpers import (
    fetch_active_rules_text,
    fetch_experience_meta,
    fetch_project_meta,
    fetch_activity_meta,
    fetch_education_data,
    fetch_skills_data,
    find_similar_applications,
    get_or_404,
)
from backend.config import get_settings
from backend.models.database import get_db
from backend.models.tables import Activity, Application, CvVersion, Project, WorkExperience
from backend.schemas.pydantic import AcceptChangesRequest, PipelineStatusOut, RegenerateBulletRequest, TailorRunRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tailor", tags=["tailor"])
limiter = Limiter(key_func=get_remote_address)

_settings = get_settings()
_PIPELINE_TIMEOUT_S = _settings.pipeline_timeout_s
_LOCK_TTL_S = _settings.pipeline_stale_lock_s


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
    # Validate application exists and acquire DB-based lock (multi-process safe).
    # SELECT FOR UPDATE serialises concurrent requests so only one can set pipeline_started_at.
    result = await db.execute(
        select(Application)
        .where(
            Application.id == body.application_id,
            Application.user_id == user_id,
        )
        .with_for_update()
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(seconds=_LOCK_TTL_S)
    if app.pipeline_started_at and app.pipeline_started_at > stale_cutoff:
        raise HTTPException(
            status_code=409,
            detail="A tailoring job is already running for your account. Please wait for it to finish.",
        )

    # Acquire lock: set pipeline_started_at and clear any previous error.
    await db.execute(
        update(Application)
        .where(Application.id == body.application_id)
        .values(pipeline_started_at=now, pipeline_error=None)
    )
    await db.commit()

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

        pipeline_task = asyncio.create_task(
            asyncio.wait_for(
                run_pipeline(
                    str(body.application_id),
                    app.jd_raw,
                    db,
                    user_id,
                    on_step,
                    manual_selection,
                    selection_mode=body.selection_mode,
                    skip_completed=True,
                ),
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
                await db.execute(
                    update(Application)
                    .where(Application.id == body.application_id)
                    .values(pipeline_started_at=None, pipeline_error=state.error)
                )
                await db.commit()
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
            error_msg = "Tailoring timed out. Please try again."
            await db.execute(
                update(Application)
                .where(Application.id == body.application_id)
                .values(pipeline_started_at=None, pipeline_error=error_msg)
            )
            await db.commit()
            yield {"event": "error", "data": json.dumps({"error": error_msg})}

        except asyncio.CancelledError:
            pipeline_task.cancel()
            await db.execute(
                update(Application)
                .where(Application.id == body.application_id)
                .values(pipeline_started_at=None)
            )
            await db.commit()
            return

        except Exception:
            pipeline_task.cancel()
            logger.exception("Pipeline raised unexpectedly for application %s", body.application_id)
            error_msg = "An unexpected error occurred. Please try again."
            await db.execute(
                update(Application)
                .where(Application.id == body.application_id)
                .values(pipeline_started_at=None, pipeline_error=error_msg)
            )
            await db.commit()
            yield {"event": "error", "data": json.dumps({"error": error_msg})}

        finally:
            # Ensure lock is always released (guards against unhandled paths).
            try:
                await db.execute(
                    update(Application)
                    .where(Application.id == body.application_id, Application.pipeline_started_at.isnot(None))
                    .values(pipeline_started_at=None)
                )
                await db.commit()
            except Exception:
                pass

    return EventSourceResponse(event_generator())


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
    app = await get_or_404(db, Application, application_id, user_id, "Application not found")

    # Separate IDs by type from diff_json
    diff = cv_version.diff_json or {}
    exp_ids = [k for k, v in diff.items() if v.get("type", "experience") == "experience"]
    proj_ids = [k for k, v in diff.items() if v.get("type") == "project"]
    act_ids = [k for k, v in diff.items() if v.get("type") == "activity"]
    edu_ids = cv_version.selected_education or []
    skill_ids = cv_version.selected_skills or []

    # SQLAlchemy AsyncSession does not allow concurrent operations on the same session;
    # queries must run sequentially.
    experience_meta = await fetch_experience_meta(db, exp_ids, user_id)
    project_meta = await fetch_project_meta(db, proj_ids, user_id)
    activity_meta = await fetch_activity_meta(db, act_ids, user_id)
    education_data = await fetch_education_data(db, edu_ids, user_id)
    skills_data = await fetch_skills_data(db, skill_ids, user_id)

    # Find similar past applications by domain + keyword overlap
    similar_applications = await find_similar_applications(db, app, user_id)

    return {
        "cv_version_id": str(cv_version.id),
        "application_id": str(application_id),
        "company_name": app.company_name,
        "role_title": app.role_title,
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
        "baseline_ats_score": cv_version.baseline_ats_score,
        "baseline_ats_warnings": cv_version.baseline_ats_warnings or [],
        "similar_applications": similar_applications,
        "status": app.status,
    }


@router.get("/status/{application_id}", response_model=PipelineStatusOut)
async def get_pipeline_status(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Return current pipeline status for an application.

    Used by the frontend to recover from stream disconnects:
    - If cv_version_id is set, the pipeline completed and the user can view results.
    - If pipeline_error is set, the pipeline failed and the user can retry.
    - If pipeline_started_at is recent and neither above, the pipeline is still running.
    """
    app = await get_or_404(db, Application, application_id, user_id, "Application not found")

    # Get latest CvVersion id if one exists
    cv_result = await db.execute(
        select(CvVersion.id)
        .where(
            CvVersion.application_id == application_id,
            CvVersion.user_id == user_id,
        )
        .order_by(CvVersion.created_at.desc())
        .limit(1)
    )
    cv_version_id = cv_result.scalar_one_or_none()

    return PipelineStatusOut(
        status=app.status,
        pipeline_error=app.pipeline_error,
        pipeline_started_at=app.pipeline_started_at,
        cv_version_id=cv_version_id,
    )


@router.put("/cv-versions/{version_id}/accept-changes")
async def accept_changes(
    version_id: uuid.UUID,
    body: AcceptChangesRequest,
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

    accepted_changes = body.accepted_changes
    rejected_changes = body.rejected_changes

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
            final_cv[exp_id] = {"bullets": exp_diff.get("suggested_bullets", exp_diff.get("original_bullets", []))}

    cv_version.final_cv_json = final_cv
    await db.commit()

    return {"status": "saved", "cv_version_id": str(version_id)}


@router.post("/re-tailor/{application_id}")
@limiter.limit("10/hour")
async def re_tailor_application(
    request: Request,
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Re-run tailoring for an existing application without changing selection.

    This applies the latest tailoring logic (including line optimization) to
    the existing selected experiences/projects/activities.
    """
    # Get application
    app = await get_or_404(db, Application, application_id, user_id, "Application not found")

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

    # Update CV version — new diff supersedes old decisions, so clear them
    cv_version.diff_json = diff_json
    cv_version.accepted_changes = None
    cv_version.rejected_changes = None
    cv_version.final_cv_json = None
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
    app = await get_or_404(db, Application, body.application_id, user_id, "Application not found")
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

    # Append hint and rejected variants to the rules context for this regeneration
    effective_rules = rules_text
    if body.hint:
        effective_rules += (
            f"\n\nUSER HINT FOR THIS SPECIFIC BULLET ONLY: {body.hint.strip()}\n"
            "Treat this as a hard instruction for the rewrite — prioritise it above all other guidance."
        )
    if body.rejected_variants:
        variants_list = "\n".join(f"- {v}" for v in body.rejected_variants[:5])
        effective_rules += (
            f"\n\nPREVIOUS REJECTED VERSIONS (user did not like these — do NOT reproduce any of them):\n"
            f"{variants_list}"
        )

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
            effective_rules,
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
            effective_rules,
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
            effective_rules,
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
