"""Pipeline definition — orchestrates the full tailoring flow as sequential async steps."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.ats_checker import AtsCheckResult, check_ats_compliance
from backend.agents.cv_tailor import TailoredActivity, TailoredExperience, TailoredProject, tailor_activities, tailor_experiences, tailor_projects
from backend.agents.draft_selector import SelectionResult, select_experiences
from backend.agents.gap_analyzer import GapAnalysis, analyze_gaps
from backend.agents.jd_parser import ParsedJD, parse_jd
from backend.api.db_helpers import fetch_active_rules_text
from backend.models.tables import (
    Activity,
    Application,
    CvProfile,
    CvVersion,
    Education,
    Project,
    Skill,
    WorkExperience,
)


class PipelineState(BaseModel):
    """State flowing through the LangGraph pipeline."""

    application_id: str
    user_id: str
    jd_raw: str = ""
    jd_parsed: dict = Field(default_factory=dict)
    selection: dict = Field(default_factory=dict)
    gap_analysis: dict = Field(default_factory=dict)
    tailored_experiences: list[dict] = Field(default_factory=list)
    tailored_projects: list[dict] = Field(default_factory=list)
    tailored_activities: list[dict] = Field(default_factory=list)
    ats_result: dict = Field(default_factory=dict)
    cv_version_id: str = ""
    current_step: str = "pending"
    error: str | None = None


def _orm_to_dict(obj, fields: list[str]) -> dict:
    """Convert an ORM object to a dict with the given fields."""
    d = {"id": str(obj.id)}
    for f in fields:
        d[f] = getattr(obj, f, None)
    return d


async def parse_jd_node(state: PipelineState, db: AsyncSession) -> PipelineState:
    """Node 1: Parse the job description."""
    state.current_step = "parsing_jd"
    try:
        parsed = await parse_jd(state.jd_raw)
        state.jd_parsed = parsed.model_dump()
        user_uuid = uuid.UUID(state.user_id)

        # Update the application with parsed JD
        result = await db.execute(
            select(Application).where(
                Application.id == uuid.UUID(state.application_id),
                Application.user_id == user_uuid,
            )
        )
        app = result.scalar_one()
        app.jd_parsed = state.jd_parsed
        app.status = "tailoring"
        await db.commit()
    except Exception as e:
        state.error = f"JD parsing failed: {e}"
    return state


async def select_experiences_node(state: PipelineState, db: AsyncSession) -> PipelineState:
    """Node 2: Select best experiences from the pool."""
    state.current_step = "selecting_experiences"
    if state.error:
        return state
    try:
        user_uuid = uuid.UUID(state.user_id)
        selection = await select_experiences(db, state.jd_parsed, user_uuid)
        state.selection = selection.model_dump()
    except Exception as e:
        state.error = f"Experience selection failed: {e}"
    return state


async def analyze_gaps_node(state: PipelineState, db: AsyncSession) -> PipelineState:
    """Node 3: Map experience to JD requirements and identify gaps."""
    state.current_step = "analyzing_gaps"
    if state.error:
        return state
    try:
        selected_exp_ids = [
            exp["id"] for exp in state.selection.get("selected_experiences", [])
        ]
        if not selected_exp_ids:
            state.error = "No experiences selected for gap analysis"
            return state

        user_uuid = uuid.UUID(state.user_id)

        # Fetch experiences from DB and convert to plain dicts
        exp_uuids = [uuid.UUID(eid) for eid in selected_exp_ids]
        result = await db.execute(
            select(WorkExperience).where(
                WorkExperience.id.in_(exp_uuids),
                WorkExperience.user_id == user_uuid,
            )
        )
        exp_dicts = [
            _orm_to_dict(e, ["company", "role_title", "bullets"])
            for e in result.scalars().all()
        ]

        # Fetch activities if selected
        act_dicts = None
        selected_act_ids = state.selection.get("selected_activities", [])
        if selected_act_ids:
            act_uuids = [uuid.UUID(aid) for aid in selected_act_ids]
            act_result = await db.execute(
                select(Activity).where(
                    Activity.id.in_(act_uuids),
                    Activity.user_id == user_uuid,
                )
            )
            act_dicts = [
                _orm_to_dict(a, ["organization", "role_title", "bullets"])
                for a in act_result.scalars().all()
            ]

        gap_result = await analyze_gaps(exp_dicts, state.jd_parsed, act_dicts)
        state.gap_analysis = gap_result.model_dump()
    except Exception as e:
        state.error = f"Gap analysis failed: {e}"
    return state


async def tailor_cv_node(state: PipelineState, db: AsyncSession) -> PipelineState:
    """Node 4: Tailor selected experiences to the JD, informed by gap analysis."""
    state.current_step = "tailoring_cv"
    if state.error:
        return state
    try:
        selected_exp_ids = [
            exp["id"] for exp in state.selection.get("selected_experiences", [])
        ]
        if not selected_exp_ids:
            state.error = "No experiences selected for tailoring"
            return state

        user_uuid = uuid.UUID(state.user_id)

        # Fetch experiences and rules from DB
        exp_uuids = [uuid.UUID(eid) for eid in selected_exp_ids]
        result = await db.execute(
            select(WorkExperience).where(
                WorkExperience.id.in_(exp_uuids),
                WorkExperience.user_id == user_uuid,
            )
        )
        exp_dicts = [
            _orm_to_dict(e, ["company", "role_title", "bullets"])
            for e in result.scalars().all()
        ]
        rules_text = await fetch_active_rules_text(db, user_uuid)

        tailored = await tailor_experiences(
            exp_dicts, state.jd_parsed, state.gap_analysis, rules_text
        )
        state.tailored_experiences = [t.model_dump() for t in tailored]
    except Exception as e:
        state.error = f"CV tailoring failed: {e}"
    return state


async def tailor_projects_node(state: PipelineState, db: AsyncSession) -> PipelineState:
    """Node 5: Tailor selected projects and activities to the JD."""
    state.current_step = "tailoring_projects"
    if state.error:
        return state
    try:
        user_uuid = uuid.UUID(state.user_id)
        rules_text = await fetch_active_rules_text(db, user_uuid)

        selected_proj_ids = state.selection.get("selected_projects", [])
        if selected_proj_ids:
            proj_uuids = [uuid.UUID(pid) for pid in selected_proj_ids]
            result = await db.execute(
                select(Project).where(
                    Project.id.in_(proj_uuids),
                    Project.user_id == user_uuid,
                )
            )
            proj_dicts = [
                _orm_to_dict(p, ["name", "description", "bullets"])
                for p in result.scalars().all()
            ]
            tailored = await tailor_projects(proj_dicts, state.jd_parsed, rules_text)
            state.tailored_projects = [t.model_dump() for t in tailored]

        selected_act_ids = state.selection.get("selected_activities", [])
        if selected_act_ids:
            act_uuids = [uuid.UUID(aid) for aid in selected_act_ids]
            act_result = await db.execute(
                select(Activity).where(
                    Activity.id.in_(act_uuids),
                    Activity.user_id == user_uuid,
                )
            )
            act_dicts = [
                _orm_to_dict(a, ["organization", "role_title", "bullets"])
                for a in act_result.scalars().all()
            ]
            tailored_acts = await tailor_activities(act_dicts, state.jd_parsed, rules_text)
            state.tailored_activities = [t.model_dump() for t in tailored_acts]
    except Exception as e:
        state.error = f"Project/activity tailoring failed: {e}"
    return state


async def ats_check_node(state: PipelineState, db: AsyncSession) -> PipelineState:
    """Node 6: Check ATS compliance."""
    state.current_step = "checking_ats"
    if state.error:
        return state
    try:
        user_uuid = uuid.UUID(state.user_id)
        # Build a CV-like structure for ATS checking
        app_result = await db.execute(
            select(Application).where(
                Application.id == uuid.UUID(state.application_id),
                Application.user_id == user_uuid,
            )
        )
        app = app_result.scalar_one()

        # Get profile
        profile_result = await db.execute(
            select(CvProfile)
            .where(CvProfile.user_id == user_uuid)
            .order_by(CvProfile.updated_at.desc())
            .limit(1)
        )
        profile = profile_result.scalar_one_or_none()

        cv_json = {
            "profile": {
                "name": profile.full_name if profile else None,
                "email": profile.email if profile else None,
                "phone": profile.phone if profile else None,
                "location": profile.location if profile else None,
            },
            "target_role": app.role_title,
            "experiences": state.tailored_experiences,
            "projects": state.tailored_projects,
            "activities": state.tailored_activities,
            "education": state.selection.get("selected_education", []),
            "skills": state.selection.get("selected_skills", []),
        }

        ats_result = await check_ats_compliance(cv_json)
        state.ats_result = ats_result.model_dump()
    except Exception as e:
        state.error = f"ATS check failed: {e}"
    return state


async def save_results_node(state: PipelineState, db: AsyncSession) -> PipelineState:
    """Final node: Save results to cv_versions table."""
    state.current_step = "saving"
    if state.error:
        return state
    try:
        # Build diff_json from tailored experiences
        diff_json = {}
        for te in state.tailored_experiences:
            diff_json[te["experience_id"]] = {
                "type": "experience",
                "original_bullets": te["original_bullets"],
                "suggested_bullets": te["suggested_bullets"],
                "changes_made": te["changes_made"],
                "confidence": te["confidence"],
                "requirements_addressed": te.get("requirements_addressed", []),
            }

        # Add tailored projects to diff_json
        for tp in state.tailored_projects:
            diff_json[tp["project_id"]] = {
                "type": "project",
                "original_bullets": tp["original_bullets"],
                "suggested_bullets": tp["suggested_bullets"],
                "changes_made": tp["changes_made"],
                "confidence": tp["confidence"],
                "requirements_addressed": tp.get("requirements_addressed", []),
            }

        # Add tailored activities to diff_json
        for ta in state.tailored_activities:
            diff_json[ta["activity_id"]] = {
                "type": "activity",
                "original_bullets": ta["original_bullets"],
                "suggested_bullets": ta["suggested_bullets"],
                "changes_made": ta["changes_made"],
                "confidence": ta["confidence"],
                "requirements_addressed": ta.get("requirements_addressed", []),
            }

        selection = state.selection
        cv_version = CvVersion(
            user_id=uuid.UUID(state.user_id),
            application_id=uuid.UUID(state.application_id),
            selected_experiences=[
                uuid.UUID(e["id"]) for e in selection.get("selected_experiences", [])
            ],
            selected_education=[
                uuid.UUID(e) for e in selection.get("selected_education", [])
            ],
            selected_projects=[
                uuid.UUID(p) for p in selection.get("selected_projects", [])
            ],
            selected_activities=[
                uuid.UUID(a) for a in selection.get("selected_activities", [])
            ],
            selected_skills=[
                uuid.UUID(s) for s in selection.get("selected_skills", [])
            ],
            diff_json=diff_json,
        )
        db.add(cv_version)
        await db.flush()
        state.cv_version_id = str(cv_version.id)

        # Update application status
        app_result = await db.execute(
            select(Application).where(
                Application.id == uuid.UUID(state.application_id),
                Application.user_id == uuid.UUID(state.user_id),
            )
        )
        app = app_result.scalar_one()
        app.status = "review"
        await db.commit()

        state.current_step = "complete"
    except Exception as e:
        state.error = f"Saving results failed: {e}"
    return state


async def run_pipeline(
    application_id: str,
    jd_raw: str,
    db: AsyncSession,
    user_id: uuid.UUID,
    on_step: Any | None = None,
) -> PipelineState:
    """Run the full tailoring pipeline.

    Args:
        application_id: UUID of the application
        jd_raw: Raw job description text
        db: Database session
        on_step: Optional async callback called with step name for SSE streaming
    """
    state = PipelineState(application_id=application_id, jd_raw=jd_raw, user_id=str(user_id))

    steps = [
        ("parsing_jd", parse_jd_node),
        ("selecting_experiences", select_experiences_node),
        ("analyzing_gaps", analyze_gaps_node),
        ("tailoring_cv", tailor_cv_node),
        ("tailoring_projects", tailor_projects_node),
        ("checking_ats", ats_check_node),
        ("saving", save_results_node),
    ]

    for step_name, node_fn in steps:
        if on_step:
            await on_step(step_name, "running")
        state = await node_fn(state, db)
        if state.error:
            if on_step:
                await on_step(step_name, "error")
            break
        if on_step:
            await on_step(step_name, "done")

    return state
