"""CRUD routes for the experience pool."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.models.database import get_db
from backend.models.tables import Activity, CvVersion, Education, Project, Skill, UnclassifiedBlock, WorkExperience
from backend.schemas.pydantic import ActivityOut, ActivityUpdate, WorkExperienceOut, WorkExperienceUpdate
from backend.services.deduplicator import deduplicate_activity

router = APIRouter(prefix="/api/experiences", tags=["experiences"])


@router.put("/{experience_id}", response_model=WorkExperienceOut)
async def update_experience(
    experience_id: uuid.UUID,
    update: WorkExperienceUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Update a parsed work experience (user correction)."""
    result = await db.execute(
        select(WorkExperience).where(
            WorkExperience.id == experience_id,
            WorkExperience.user_id == user_id,
        )
    )
    exp = result.scalar_one_or_none()
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(exp, field, value)

    exp.is_reviewed = True
    exp.needs_review = False
    await db.commit()
    await db.refresh(exp)

    return WorkExperienceOut(
        id=exp.id, company=exp.company, role_title=exp.role_title, location=exp.location,
        date_start=exp.date_start, date_end=exp.date_end, is_current=exp.is_current,
        bullets=exp.bullets, domain_tags=exp.domain_tags, skill_tags=exp.skill_tags,
        variant_group_id=exp.variant_group_id, is_primary_variant=exp.is_primary_variant,
        needs_review=exp.needs_review, review_reason=exp.review_reason,
    )


@router.delete("/{experience_id}")
async def delete_experience(
    experience_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Delete a work experience."""
    result = await db.execute(
        select(WorkExperience).where(
            WorkExperience.id == experience_id,
            WorkExperience.user_id == user_id,
        )
    )
    exp = result.scalar_one_or_none()
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")

    await db.delete(exp)
    await db.commit()
    return {"status": "deleted"}


@router.put("/activities/{activity_id}", response_model=ActivityOut)
async def update_activity(
    activity_id: uuid.UUID,
    update: ActivityUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Update a parsed activity (user correction)."""
    result = await db.execute(
        select(Activity).where(
            Activity.id == activity_id,
            Activity.user_id == user_id,
        )
    )
    act = result.scalar_one_or_none()
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(act, field, value)

    act.is_reviewed = True
    act.needs_review = False
    await db.commit()
    await db.refresh(act)

    return ActivityOut(
        id=act.id, organization=act.organization, role_title=act.role_title, location=act.location,
        date_start=act.date_start, date_end=act.date_end, is_current=act.is_current,
        bullets=act.bullets, domain_tags=act.domain_tags, skill_tags=act.skill_tags,
        variant_group_id=act.variant_group_id, is_primary_variant=act.is_primary_variant,
        needs_review=act.needs_review, review_reason=act.review_reason,
    )


@router.delete("/activities/{activity_id}")
async def delete_activity(
    activity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Delete an activity."""
    result = await db.execute(
        select(Activity).where(
            Activity.id == activity_id,
            Activity.user_id == user_id,
        )
    )
    act = result.scalar_one_or_none()
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")

    await db.delete(act)
    await db.commit()
    return {"status": "deleted"}


@router.delete("/education/{education_id}")
async def delete_education(
    education_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Delete an education entry."""
    result = await db.execute(
        select(Education).where(
            Education.id == education_id,
            Education.user_id == user_id,
        )
    )
    edu = result.scalar_one_or_none()
    if not edu:
        raise HTTPException(status_code=404, detail="Education not found")

    await db.delete(edu)
    await db.commit()
    return {"status": "deleted"}


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Delete a project."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
        )
    )
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    await db.delete(proj)
    await db.commit()
    return {"status": "deleted"}


@router.delete("/skills/{skill_id}")
async def delete_skill(
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Delete a skill."""
    result = await db.execute(
        select(Skill).where(
            Skill.id == skill_id,
            Skill.user_id == user_id,
        )
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    await db.delete(skill)
    await db.commit()
    return {"status": "deleted"}


class ReclassifyRequest(BaseModel):
    experience_ids: list[str]


@router.post("/reclassify")
async def reclassify_to_activities(
    body: ReclassifyRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Move work experience entries to the activities table."""
    new_activity_ids: list[str] = []

    for exp_id_str in body.experience_ids:
        exp_id = uuid.UUID(exp_id_str)
        result = await db.execute(
            select(WorkExperience).where(
                WorkExperience.id == exp_id,
                WorkExperience.user_id == user_id,
            )
        )
        exp = result.scalar_one_or_none()
        if not exp:
            continue

        # Create Activity from WorkExperience
        activity = Activity(
            user_id=user_id,
            upload_source_id=exp.upload_source_id,
            organization=exp.company,
            role_title=exp.role_title,
            location=exp.location,
            date_start=exp.date_start,
            date_end=exp.date_end,
            is_current=exp.is_current,
            organization_confidence=exp.company_confidence,
            dates_confidence=exp.dates_confidence,
            bullets=exp.bullets,
            raw_block=exp.raw_block,
            domain_tags=exp.domain_tags,
            skill_tags=exp.skill_tags,
            embedding=exp.embedding,
            is_reviewed=exp.is_reviewed,
            needs_review=exp.needs_review,
            review_reason=exp.review_reason,
            user_corrections=exp.user_corrections,
        )
        db.add(activity)
        await db.flush()

        # Deduplicate within activities namespace
        await deduplicate_activity(db, activity, user_id)

        # Update any CvVersion rows referencing the old experience ID
        cv_result = await db.execute(
            select(CvVersion).where(CvVersion.user_id == user_id)
        )
        for cv in cv_result.scalars():
            if cv.selected_experiences and exp_id in cv.selected_experiences:
                cv.selected_experiences = [
                    eid for eid in cv.selected_experiences if eid != exp_id
                ]
                if not cv.selected_activities:
                    cv.selected_activities = []
                cv.selected_activities = cv.selected_activities + [activity.id]

        # Delete original work experience
        await db.delete(exp)
        new_activity_ids.append(str(activity.id))

    await db.commit()
    return {"status": "reclassified", "new_activity_ids": new_activity_ids}


@router.post("/{block_id}/resolve-unclassified")
async def resolve_unclassified(
    block_id: uuid.UUID,
    resolved_as: str,
    db: AsyncSession = Depends(get_db),
):
    """User classifies an unclassified block."""
    result = await db.execute(
        select(UnclassifiedBlock).where(UnclassifiedBlock.id == block_id)
    )
    block = result.scalar_one_or_none()
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")

    block.user_resolved = True
    block.resolved_as = resolved_as
    await db.commit()
    return {"status": "resolved", "resolved_as": resolved_as}
