"""Tailoring rules CRUD routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.api.db_helpers import apply_update, delete_or_404, get_or_404
from backend.models.database import get_db
from backend.models.tables import TailoringRule
from backend.schemas.pydantic import TailoringRuleCreate, TailoringRuleOut, TailoringRuleUpdate

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("", response_model=list[TailoringRuleOut])
async def get_rules(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Get all tailoring rules."""
    result = await db.execute(
        select(TailoringRule)
        .where(TailoringRule.user_id == user_id)
        .order_by(TailoringRule.created_at.desc())
    )
    return [TailoringRuleOut.model_validate(r) for r in result.scalars().all()]


@router.post("", response_model=TailoringRuleOut)
async def create_rule(
    body: TailoringRuleCreate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Add a new tailoring rule."""
    rule = TailoringRule(rule_text=body.rule_text, user_id=user_id)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return TailoringRuleOut.model_validate(rule)


@router.put("/{rule_id}", response_model=TailoringRuleOut)
async def update_rule(
    rule_id: uuid.UUID,
    body: TailoringRuleUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Update a tailoring rule."""
    rule = await get_or_404(db, TailoringRule, rule_id, user_id, "Rule not found")
    apply_update(rule, body.model_dump(exclude_unset=True))
    await db.commit()
    await db.refresh(rule)
    return TailoringRuleOut.model_validate(rule)


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Delete a tailoring rule."""
    return await delete_or_404(db, TailoringRule, rule_id, user_id, "Rule not found")
