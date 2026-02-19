"""Shared database helpers to eliminate boilerplate in route handlers."""

from __future__ import annotations

import uuid
from typing import Any, Type, TypeVar

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.tables import CvProfile

T = TypeVar("T")


async def get_or_404(
    db: AsyncSession,
    model: Type[T],
    obj_id: uuid.UUID,
    user_id: uuid.UUID,
    detail: str = "Not found",
) -> T:
    """Fetch a single row scoped to user_id, or raise HTTP 404."""
    result = await db.execute(
        select(model).where(
            model.id == obj_id,  # type: ignore[attr-defined]
            model.user_id == user_id,  # type: ignore[attr-defined]
        )
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail=detail)
    return obj  # type: ignore[return-value]


async def delete_or_404(
    db: AsyncSession,
    model: Type[Any],
    obj_id: uuid.UUID,
    user_id: uuid.UUID,
    detail: str = "Not found",
) -> dict:
    """Fetch and delete a row scoped to user_id, or raise HTTP 404."""
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
