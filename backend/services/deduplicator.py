"""Deduplication service — embedding similarity search and variant grouping."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from backend.config import get_settings
from backend.models.tables import Activity, Project, WorkExperience
from backend.services.embedder import embed_text
from backend.utils import extract_bullet_texts


@dataclass
class DeduplicationResult:
    action: str  # "new", "variant", "near_duplicate"
    existing_id: uuid.UUID | None
    similarity_score: float
    variant_group_id: uuid.UUID


async def _find_similar(
    db: AsyncSession,
    table_name: str,
    embedding: list[float],
    threshold: float,
) -> list[tuple[uuid.UUID, uuid.UUID | None, float]]:
    """Find rows in *table_name* with cosine similarity above threshold.

    Returns list of (id, variant_group_id, similarity_score).
    """
    stmt = text(f"""
        SELECT id, variant_group_id,
               1 - (embedding <=> :embedding) as similarity
        FROM {table_name}
        WHERE embedding IS NOT NULL
          AND 1 - (embedding <=> :embedding) > :threshold
        ORDER BY similarity DESC
        LIMIT 5
    """).bindparams(bindparam("embedding", type_=Vector))
    result = await db.execute(
        stmt,
        {"embedding": embedding, "threshold": threshold},
    )
    return [(row[0], row[1], row[2]) for row in result.fetchall()]


def _classify(
    similar: list[tuple[uuid.UUID, uuid.UUID | None, float]],
    item,
    near_threshold: float,
) -> DeduplicationResult:
    """Classify an item as new / variant / near_duplicate based on similarity results."""
    if not similar:
        group_id = getattr(item, "variant_group_id", None) or uuid.uuid4()
        item.variant_group_id = group_id
        item.is_primary_variant = True
        return DeduplicationResult(
            action="new", existing_id=None, similarity_score=0.0, variant_group_id=group_id,
        )

    best_match_id, best_group_id, best_score = similar[0]
    group_id = best_group_id or uuid.uuid4()
    item.variant_group_id = group_id
    item.is_primary_variant = False
    if hasattr(item, "similarity_score"):
        item.similarity_score = best_score

    action = "near_duplicate" if best_score > near_threshold else "variant"
    return DeduplicationResult(
        action=action,
        existing_id=best_match_id,
        similarity_score=best_score,
        variant_group_id=group_id,
    )


async def deduplicate_experience(
    db: AsyncSession,
    experience: WorkExperience,
) -> DeduplicationResult:
    """Check if a work experience is a duplicate/variant of an existing one."""
    settings = get_settings()
    bullet_texts = extract_bullet_texts(experience.bullets)
    embed_input = f"{experience.company or ''} {experience.role_title or ''} " + " ".join(bullet_texts)

    embedding = await embed_text(embed_input)
    experience.embedding = embedding

    similar = await _find_similar(db, "work_experiences", embedding, settings.variant_threshold)
    return _classify(similar, experience, settings.near_duplicate_threshold)


async def deduplicate_project(
    db: AsyncSession,
    project: Project,
) -> DeduplicationResult:
    """Check if a project is a duplicate/variant of an existing one."""
    settings = get_settings()
    bullet_texts = extract_bullet_texts(project.bullets)
    embed_input = f"{project.name or ''} {project.description or ''} " + " ".join(bullet_texts)

    embedding = await embed_text(embed_input)
    project.embedding = embedding

    similar = await _find_similar(db, "projects", embedding, settings.variant_threshold)
    return _classify(similar, project, settings.near_duplicate_threshold)


async def deduplicate_activity(
    db: AsyncSession,
    activity: Activity,
) -> DeduplicationResult:
    """Check if an activity is a duplicate/variant of an existing one."""
    settings = get_settings()
    bullet_texts = extract_bullet_texts(activity.bullets)
    embed_input = f"{activity.organization or ''} {activity.role_title or ''} " + " ".join(bullet_texts)

    embedding = await embed_text(embed_input)
    activity.embedding = embedding

    similar = await _find_similar(db, "activities", embedding, settings.variant_threshold)
    return _classify(similar, activity, settings.near_duplicate_threshold)
