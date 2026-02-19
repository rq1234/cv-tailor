"""Tailoring pipeline route — triggers the full agent pipeline with SSE streaming."""

from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend.agents.graph import run_pipeline
from backend.api.auth import get_current_user
from backend.models.database import get_db
from backend.models.tables import Activity, Application, CvVersion, Education, Project, Skill, TailoringRule, WorkExperience
from backend.schemas.pydantic import TailorRunRequest

router = APIRouter(prefix="/api/tailor", tags=["tailor"])
limiter = Limiter(key_func=get_remote_address)


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

        # Run pipeline in background task
        pipeline_task = asyncio.create_task(
            run_pipeline(str(body.application_id), app.jd_raw, db, user_id, on_step)
        )

        try:
            # Stream step updates
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

            # Get final result
            state = await pipeline_task

            if state.error:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": state.error}),
                }
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
        except asyncio.CancelledError:
            pipeline_task.cancel()
            return

    return EventSourceResponse(event_generator())



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

    # Separate experience and project IDs from diff_json
    diff = cv_version.diff_json or {}
    exp_ids = [k for k, v in diff.items() if v.get("type", "experience") == "experience"]
    proj_ids = [k for k, v in diff.items() if v.get("type") == "project"]
    act_ids = [k for k, v in diff.items() if v.get("type") == "activity"]

    # Fetch experience metadata
    experience_meta = {}
    if exp_ids:
        exp_uuids = [uuid.UUID(eid) for eid in exp_ids]
        exp_result = await db.execute(
            select(WorkExperience).where(
                WorkExperience.id.in_(exp_uuids),
                WorkExperience.user_id == user_id,
            )
        )
        for exp in exp_result.scalars():
            experience_meta[str(exp.id)] = {
                "company": exp.company,
                "role_title": exp.role_title,
                "date_start": exp.date_start.isoformat() if exp.date_start else None,
                "date_end": exp.date_end.isoformat() if exp.date_end else None,
                "is_current": exp.is_current,
            }

    # Fetch project metadata
    project_meta = {}
    if proj_ids:
        proj_uuids = [uuid.UUID(pid) for pid in proj_ids]
        proj_result = await db.execute(
            select(Project).where(
                Project.id.in_(proj_uuids),
                Project.user_id == user_id,
            )
        )
        for proj in proj_result.scalars():
            project_meta[str(proj.id)] = {
                "name": proj.name,
                "description": proj.description,
                "date_start": proj.date_start.isoformat() if proj.date_start else None,
                "date_end": proj.date_end.isoformat() if proj.date_end else None,
            }

    # Fetch activity metadata
    activity_meta = {}
    if act_ids:
        act_uuids = [uuid.UUID(aid) for aid in act_ids]
        act_result = await db.execute(
            select(Activity).where(
                Activity.id.in_(act_uuids),
                Activity.user_id == user_id,
            )
        )
        for act in act_result.scalars():
            activity_meta[str(act.id)] = {
                "organization": act.organization,
                "role_title": act.role_title,
                "date_start": act.date_start.isoformat() if act.date_start else None,
                "date_end": act.date_end.isoformat() if act.date_end else None,
                "is_current": act.is_current,
            }

    # Fetch full education data
    education_data = []
    edu_ids = cv_version.selected_education or []
    if edu_ids:
        edu_result = await db.execute(
            select(Education).where(
                Education.id.in_(edu_ids),
                Education.user_id == user_id,
            )
        )
        for edu in edu_result.scalars():
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
            education_data.append({
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

    # Fetch full skills data grouped by category
    skills_data: dict[str, list[str]] = {}
    skill_ids = cv_version.selected_skills or []
    if skill_ids:
        skill_result = await db.execute(
            select(Skill).where(
                Skill.id.in_(skill_ids),
                Skill.user_id == user_id,
            )
        )
        skills_by_id = {s.id: s for s in skill_result.scalars()}
        for sid in skill_ids:
            skill = skills_by_id.get(sid)
            if not skill:
                continue
            cat = (skill.category or "Other").capitalize()
            if cat not in skills_data:
                skills_data[cat] = []
            skills_data[cat].append(skill.name)

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
    
    # Validate each entry in accepted_changes
    diff_json = cv_version.diff_json or {}
    for key, value in accepted_changes.items():
        # Check if value is properly formatted
        if value is None:
            raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'] cannot be null")
        
        # For experience/project/activity bullets: should be list of strings
        if key in diff_json:
            if not isinstance(value, list):
                raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'] must be a list of bullet strings")
            for i, bullet in enumerate(value):
                if not isinstance(bullet, str):
                    raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'][{i}] must be a string")
        
        # For education entries: should be list of strings (achievements + modules)
        elif key.startswith("education_"):
            if isinstance(value, dict):
                achievements = value.get("achievements", [])
                modules = value.get("modules", [])
                if not isinstance(achievements, list) or not isinstance(modules, list):
                    raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'] must contain list fields")
                for i, item in enumerate(achievements):
                    if not isinstance(item, str):
                        raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'].achievements[{i}] must be a string")
                for i, item in enumerate(modules):
                    if not isinstance(item, str):
                        raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'].modules[{i}] must be a string")
            else:
                if not isinstance(value, list):
                    raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'] must be a list")
                for i, item in enumerate(value):
                    if not isinstance(item, str):
                        raise HTTPException(status_code=400, detail=f"accepted_changes['{key}'][{i}] must be a string")
        
        # For skills entries: should be list of strings (individual skills)
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
            # Use original if not accepted
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
    from backend.agents.cv_tailor import tailor_experiences, tailor_projects, tailor_activities
    from backend.agents.gap_analyzer import analyze_gaps
    from backend.utils import extract_bullet_texts
    
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
    
    # Fetch rules
    rules_result = await db.execute(
        select(TailoringRule).where(
            TailoringRule.is_active.is_(True),
            TailoringRule.user_id == user_id,
        )
    )
    rules = rules_result.scalars().all()
    rules_text = ""
    if rules:
        rules_text = "Additional tailoring rules to apply:\n" + "\n".join(
            f"- {r.rule_text}" for r in rules
        )
    
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
    
    # Update CV version with new diffs
    cv_version.diff_json = diff_json
    # PRESERVE user's accepted/rejected decisions - only update suggestions
    # Do NOT reset accepted_changes and rejected_changes
    # cv_version.accepted_changes and cv_version.rejected_changes stay as-is
    
    await db.commit()
    
    return {
        "status": "re-tailored",
        "cv_version_id": str(cv_version.id),
        "diffs_count": len(diff_json),
    }
