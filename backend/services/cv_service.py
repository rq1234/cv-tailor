"""CV upload business logic — parse, store, deduplicate, embed."""

from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.tables import (
    Activity,
    CvProfile,
    CvUpload,
    Education,
    Project,
    Skill,
    UnclassifiedBlock,
    WorkExperience,
)
from backend.schemas.pydantic import (
    DuplicateGroup,
    DuplicateItem,
    ParseSummary,
    ReviewItem,
    UnclassifiedBlockOut,
)
from backend.config import get_settings
from backend.services.cv_structurer import structure_cv_text
from backend.services.deduplicator import deduplicate_activity, deduplicate_experience, deduplicate_project
from backend.services.embedder import embed_text
from backend.services.pdf_parser import extract_docx_text, extract_pdf_text
from backend.utils import extract_bullet_texts

logger = logging.getLogger(__name__)

VALID_SKILL_CATEGORIES = {"technical", "language", "tool", "soft", "other", "certification", "framework", "interest"}


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


async def parse_and_store_cv(
    db: AsyncSession,
    file_bytes: bytes,
    filename: str,
    file_type: str,
    user_id: uuid.UUID,
) -> ParseSummary:
    """Full CV upload pipeline: extract text, structure with GPT-4o, store & deduplicate.

    Args:
        db: Database session.
        file_bytes: Raw file content.
        filename: Original filename.
        file_type: "pdf" or "docx".

    Returns:
        ParseSummary with upload results.
    """
    # Extract text
    if file_type == "pdf":
        raw_text, quality = extract_pdf_text(file_bytes)
    else:
        raw_text, quality = extract_docx_text(file_bytes)

    if not raw_text.strip():
        raise ValueError("Could not extract text from the file")

    # Store raw upload
    upload = CvUpload(
        user_id=user_id,
        original_filename=filename,
        file_type=file_type,
        raw_text=raw_text,
        raw_text_quality=quality,
        parsing_status="pending",
    )
    db.add(upload)
    await db.flush()

    # Structure with GPT-4o
    try:
        parsed = await structure_cv_text(raw_text, db)
        upload.parsing_status = "complete"
    except Exception as e:
        upload.parsing_status = "failed"
        upload.parsing_notes = str(e)
        await db.commit()
        raise RuntimeError(f"CV parsing failed: {e}") from e

    if not parsed.is_cv:
        upload.parsing_status = "failed"
        upload.parsing_notes = parsed.rejection_reason or "Not a CV"
        await db.commit()
        raise ValueError(parsed.rejection_reason or "The uploaded file does not appear to be a CV or resume.")

    review_items: list[ReviewItem] = []
    duplicate_groups: dict[str, list[DuplicateItem]] = {}
    cleanly_parsed_count = 0

    # Store profile
    _threshold = get_settings().confidence_review_threshold

    profile = CvProfile(
        user_id=user_id,
        full_name=parsed.profile.full_name,
        email=parsed.profile.email,
        phone=parsed.profile.phone,
        location=parsed.profile.location,
        linkedin_url=parsed.profile.linkedin_url,
        portfolio_url=parsed.profile.portfolio_url,
        summary=parsed.profile.summary,
        name_confidence=parsed.profile.name_confidence,
        contact_confidence=parsed.profile.contact_confidence,
    )
    db.add(profile)

    if parsed.profile.name_confidence < _threshold:
        review_items.append(ReviewItem(
            id=profile.id, table="cv_profiles", field="full_name",
            current_value=parsed.profile.full_name,
            confidence=parsed.profile.name_confidence,
            review_reason="Low confidence on name extraction",
        ))

    if parsed.profile.contact_confidence < _threshold:
        review_items.append(ReviewItem(
            id=profile.id, table="cv_profiles", field="email",
            current_value=parsed.profile.email,
            confidence=parsed.profile.contact_confidence,
            review_reason="Low confidence on contact info extraction",
        ))

    # Store work experiences
    for exp in parsed.work_experiences:
        needs_review = False
        reasons = []
        if exp.company_confidence < _threshold:
            needs_review = True
            reasons.append(f"Low company confidence: {exp.company_confidence}")
        if exp.dates_confidence < _threshold:
            needs_review = True
            reasons.append(f"Low dates confidence: {exp.dates_confidence}")

        work_exp = WorkExperience(
            user_id=user_id,
            upload_source_id=upload.id,
            company=exp.company,
            role_title=exp.role_title,
            location=exp.location,
            date_start=_parse_date(exp.date_start),
            date_end=_parse_date(exp.date_end),
            is_current=exp.is_current,
            company_confidence=exp.company_confidence,
            dates_confidence=exp.dates_confidence,
            bullets=[{"text": b.text, "domain_tags": b.domain_tags} for b in exp.bullets],
            raw_block=exp.raw_block,
            domain_tags=exp.domain_tags,
            skill_tags=exp.skill_tags,
            needs_review=needs_review,
            review_reason="; ".join(reasons) if reasons else None,
        )
        db.add(work_exp)
        await db.flush()

        try:
            dedup_result = await deduplicate_experience(db, work_exp, user_id)
            if dedup_result.action in ("near_duplicate", "variant"):
                duplicate_groups.setdefault(str(dedup_result.variant_group_id), [])
                duplicate_groups[str(dedup_result.variant_group_id)].append(
                    DuplicateItem(
                        id=work_exp.id, company=exp.company, role_title=exp.role_title,
                        similarity_score=dedup_result.similarity_score,
                        is_primary_variant=work_exp.is_primary_variant,
                    )
                )
        except Exception:
            logger.exception("Deduplication failed for experience %s at %s", exp.role_title, exp.company)
            work_exp.variant_group_id = uuid.uuid4()
            work_exp.is_primary_variant = True

        if needs_review:
            for reason in reasons:
                field = "company" if "company" in reason else "dates"
                conf = exp.company_confidence if field == "company" else exp.dates_confidence
                review_items.append(ReviewItem(
                    id=work_exp.id, table="work_experiences", field=field,
                    current_value=exp.company if field == "company" else f"{exp.date_start} - {exp.date_end}",
                    confidence=conf, review_reason=reason,
                ))
        else:
            cleanly_parsed_count += 1

    # Store education
    for edu in parsed.education:
        needs_review = edu.institution_confidence < _threshold or edu.dates_confidence < _threshold
        review_reason = None
        if needs_review:
            parts = []
            if edu.institution_confidence < 0.75:
                parts.append(f"Low institution confidence: {edu.institution_confidence}")
            if edu.dates_confidence < 0.75:
                parts.append(f"Low dates confidence: {edu.dates_confidence}")
            review_reason = "; ".join(parts)

        education = Education(
            user_id=user_id,
            upload_source_id=upload.id,
            institution=edu.institution, degree=edu.degree, grade=edu.grade,
            date_start=_parse_date(edu.date_start), date_end=_parse_date(edu.date_end),
            location=edu.location, achievements=edu.achievements, modules=edu.modules,
            raw_block=edu.raw_block, dates_confidence=edu.dates_confidence,
            institution_confidence=edu.institution_confidence, needs_review=needs_review,
        )
        db.add(education)
        await db.flush()

        if needs_review:
            review_items.append(ReviewItem(
                id=education.id, table="education", field="institution",
                current_value=edu.institution,
                confidence=min(edu.institution_confidence, edu.dates_confidence),
                review_reason=review_reason,
            ))
        else:
            cleanly_parsed_count += 1

    # Store projects
    for proj in parsed.projects:
        project = Project(
            user_id=user_id,
            upload_source_id=upload.id,
            name=proj.name, description=proj.description,
            date_start=_parse_date(proj.date_start), date_end=_parse_date(proj.date_end),
            url=proj.url,
            bullets=[{"text": b.text, "domain_tags": b.domain_tags} for b in proj.bullets] if proj.bullets else None,
            raw_block=proj.raw_block, domain_tags=proj.domain_tags, skill_tags=proj.skill_tags,
        )
        db.add(project)
        await db.flush()

        try:
            await deduplicate_project(db, project, user_id)
        except Exception:
            logger.exception("Deduplication failed for project %s", proj.name)
            project.variant_group_id = uuid.uuid4()
            project.is_primary_variant = True

        cleanly_parsed_count += 1

    # Store activities
    for act in parsed.activities:
        needs_review = False
        reasons = []
        if act.company_confidence < _threshold:
            needs_review = True
            reasons.append(f"Low organization confidence: {act.company_confidence}")
        if act.dates_confidence < _threshold:
            needs_review = True
            reasons.append(f"Low dates confidence: {act.dates_confidence}")

        activity = Activity(
            user_id=user_id,
            upload_source_id=upload.id,
            organization=act.company, role_title=act.role_title, location=act.location,
            date_start=_parse_date(act.date_start), date_end=_parse_date(act.date_end),
            is_current=act.is_current, organization_confidence=act.company_confidence,
            dates_confidence=act.dates_confidence,
            bullets=[{"text": b.text, "domain_tags": b.domain_tags} for b in act.bullets],
            raw_block=act.raw_block, domain_tags=act.domain_tags, skill_tags=act.skill_tags,
            needs_review=needs_review, review_reason="; ".join(reasons) if reasons else None,
        )
        db.add(activity)
        await db.flush()

        try:
            dedup_result = await deduplicate_activity(db, activity, user_id)
            if dedup_result.action in ("near_duplicate", "variant"):
                duplicate_groups.setdefault(str(dedup_result.variant_group_id), [])
                duplicate_groups[str(dedup_result.variant_group_id)].append(
                    DuplicateItem(
                        id=activity.id, company=act.company, role_title=act.role_title,
                        similarity_score=dedup_result.similarity_score,
                        is_primary_variant=activity.is_primary_variant,
                    )
                )
        except Exception:
            logger.exception("Deduplication failed for activity %s at %s", act.role_title, act.company)
            activity.variant_group_id = uuid.uuid4()
            activity.is_primary_variant = True

        if needs_review:
            for reason in reasons:
                field = "organization" if "organization" in reason else "dates"
                conf = act.company_confidence if field == "organization" else act.dates_confidence
                review_items.append(ReviewItem(
                    id=activity.id, table="activities", field=field,
                    current_value=act.company if field == "organization" else f"{act.date_start} - {act.date_end}",
                    confidence=conf, review_reason=reason,
                ))
        else:
            cleanly_parsed_count += 1

    # Store skills (deduplicate by lowercase name)
    seen_skill_names: set[str] = set()
    for skill in parsed.skills:
        name_lower = skill.name.strip().lower()
        if name_lower in seen_skill_names:
            continue
        seen_skill_names.add(name_lower)
        category = skill.category
        if category and category not in VALID_SKILL_CATEGORIES:
            category = "other"
        db.add(Skill(
            user_id=user_id,
            name=skill.name,
            canonical_name=skill.name,
            category=category,
            proficiency=skill.proficiency,
        ))
        cleanly_parsed_count += 1

    # Store unclassified blocks
    unclassified_out: list[UnclassifiedBlockOut] = []
    for block in parsed.unclassified_blocks:
        ub = UnclassifiedBlock(
            user_id=user_id,
            upload_source_id=upload.id,
            raw_text=block.raw_text,
            gpt_category_guess=block.category_guess,
            gpt_confidence=block.confidence,
        )
        db.add(ub)
        await db.flush()
        unclassified_out.append(UnclassifiedBlockOut(
            id=ub.id, raw_text=block.raw_text,
            gpt_category_guess=block.category_guess, gpt_confidence=block.confidence,
        ))

    await db.commit()

    return ParseSummary(
        upload_id=upload.id,
        cleanly_parsed_count=cleanly_parsed_count,
        needs_review=review_items,
        unclassified_blocks=unclassified_out,
        duplicates=[
            DuplicateGroup(variant_group_id=uuid.UUID(gid), items=items)
            for gid, items in duplicate_groups.items()
        ],
    )


async def re_embed_all(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Re-generate embeddings for all records with NULL embeddings."""
    counts = {}

    for model, name_field, label in [
        (WorkExperience, "company", "experiences"),
        (Project, "name", "projects"),
        (Activity, "organization", "activities"),
    ]:
        result = await db.execute(
            select(model).where(
                model.embedding.is_(None),
                model.user_id == user_id,
            )
        )
        items = result.scalars().all()
        count = 0
        for item in items:
            bullet_texts = extract_bullet_texts(getattr(item, "bullets", None))
            name = getattr(item, name_field, "") or ""
            role = getattr(item, "role_title", "") or getattr(item, "description", "") or ""
            embed_input = f"{name} {role} " + " ".join(bullet_texts)
            try:
                item.embedding = await embed_text(embed_input)
                count += 1
            except Exception:
                logger.exception("Failed to embed %s %s", label, item.id)
        counts[f"{label}_embedded"] = count

    await db.commit()
    return {"status": "complete", **counts}
