"""Tailoring rules CRUD routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_db
from backend.models.tables import TailoringRule
from backend.schemas.pydantic import TailoringRuleCreate, TailoringRuleOut, TailoringRuleUpdate

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("", response_model=list[TailoringRuleOut])
async def get_rules(db: AsyncSession = Depends(get_db)):
    """Get all tailoring rules."""
    result = await db.execute(select(TailoringRule).order_by(TailoringRule.created_at.desc()))
    return [
        TailoringRuleOut(
            id=r.id, rule_text=r.rule_text, is_active=r.is_active, created_at=r.created_at,
        )
        for r in result.scalars().all()
    ]


@router.post("", response_model=TailoringRuleOut)
async def create_rule(body: TailoringRuleCreate, db: AsyncSession = Depends(get_db)):
    """Add a new tailoring rule."""
    rule = TailoringRule(rule_text=body.rule_text)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return TailoringRuleOut(
        id=rule.id, rule_text=rule.rule_text, is_active=rule.is_active, created_at=rule.created_at,
    )


@router.put("/{rule_id}", response_model=TailoringRuleOut)
async def update_rule(
    rule_id: uuid.UUID, body: TailoringRuleUpdate, db: AsyncSession = Depends(get_db),
):
    """Update a tailoring rule."""
    result = await db.execute(select(TailoringRule).where(TailoringRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)
    await db.commit()
    await db.refresh(rule)
    return TailoringRuleOut(
        id=rule.id, rule_text=rule.rule_text, is_active=rule.is_active, created_at=rule.created_at,
    )


@router.delete("/{rule_id}")
async def delete_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a tailoring rule."""
    result = await db.execute(select(TailoringRule).where(TailoringRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
    return {"status": "deleted"}
