"""Agent: Select best experiences from the pool based on JD match."""

from __future__ import annotations

import logging
import uuid

from pydantic import BaseModel, Field
from sqlalchemy import bindparam, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from backend.models.tables import Activity, Education, Project, Skill, WorkExperience
from backend.services.embedder import embed_text

logger = logging.getLogger(__name__)


class SelectedExperience(BaseModel):
    id: str
    relevance_score: float
    reason: str


class SelectionResult(BaseModel):
    selected_experiences: list[SelectedExperience] = Field(default_factory=list)
    selected_education: list[str] = Field(default_factory=list)
    selected_projects: list[str] = Field(default_factory=list)
    selected_activities: list[str] = Field(default_factory=list)
    selected_skills: list[str] = Field(default_factory=list)


async def select_experiences(
    db: AsyncSession,
    jd_parsed: dict,
) -> SelectionResult:
    """Select the most relevant experiences from the pool based on parsed JD.

    1. Embed the JD requirements
    2. Run cosine similarity against work_experiences.embedding via pgvector
    3. For each variant group, select the best variant based on domain match
    4. Return top 6-8 most relevant experiences
    """
    # Build JD text for embedding
    jd_text_parts = []
    for field in ["required_skills", "nice_to_have_skills", "keywords"]:
        if field in jd_parsed and jd_parsed[field]:
            jd_text_parts.extend(jd_parsed[field])
    if jd_parsed.get("role_summary"):
        jd_text_parts.append(jd_parsed["role_summary"])
    if jd_parsed.get("domain"):
        jd_text_parts.append(jd_parsed["domain"])

    jd_embed_text = " ".join(jd_text_parts)
    jd_embedding = await embed_text(jd_embed_text)

    # Domain-aware section selection: always include both, adjust emphasis
    domain = (jd_parsed.get("domain") or "").lower()
    role_summary = (jd_parsed.get("role_summary") or "").lower()
    all_keywords = " ".join(jd_parsed.get("keywords", [])).lower()
    domain_context = f"{domain} {role_summary} {all_keywords}"

    is_tech = any(kw in domain_context for kw in ("tech", "software", "engineer", "data", "quant", "trading", "fintech", "machine learning", "developer", "analytics"))
    is_consulting = any(kw in domain_context for kw in ("consult", "strategy", "advisory"))
    is_finance = any(kw in domain_context for kw in ("financ", "bank", "investment", "equity", "asset", "wealth", "portfolio"))

    if is_tech:
        # Tech/quant/trading: projects only, strict 1-page
        project_limit, activity_limit = 3, 0
    elif is_consulting or is_finance:
        # Consulting/finance/asset management: leadership only, strict 1-page
        project_limit, activity_limit = 0, 3
    else:
        # Default: projects focused
        project_limit, activity_limit = 2, 1

    logger.info("Domain-aware selection: domain=%r tech=%s consulting=%s finance=%s → projects=%d activities=%d",
                domain, is_tech, is_consulting, is_finance, project_limit, activity_limit)

    # Build domain keywords for boosting experiences with matching domain_tags
    domain_keywords: set[str] = set()
    if domain:
        domain_keywords.add(domain)
    # Also add parsed JD domain-related terms
    for kw in ("tech", "software", "engineer", "data", "quant", "trading", "fintech",
                "consult", "strategy", "finance", "bank", "investment"):
        if kw in domain:
            domain_keywords.add(kw)

    # Search for similar work experiences using pgvector
    # Fetch domain_tags so we can apply a domain-match boost
    experience_stmt = text("""
        SELECT id, company, role_title, variant_group_id, domain_tags,
               1 - (embedding <=> :embedding) as similarity
        FROM work_experiences
        WHERE embedding IS NOT NULL
        ORDER BY similarity DESC
        LIMIT 30
    """).bindparams(bindparam("embedding", type_=Vector))
    result = await db.execute(
        experience_stmt,
        {"embedding": jd_embedding},
    )
    rows = result.fetchall()

    # Apply domain-tag boost and re-rank
    DOMAIN_BOOST = 0.08
    scored_rows = []
    for row in rows:
        exp_id, company, role_title, variant_group_id, exp_domain_tags, similarity = row
        boosted = float(similarity)
        if exp_domain_tags and domain_keywords:
            # Boost if any domain_tag overlaps with JD domain keywords
            tags_lower = {t.lower() for t in exp_domain_tags}
            if tags_lower & domain_keywords:
                boosted += DOMAIN_BOOST
        scored_rows.append((exp_id, company, role_title, variant_group_id, boosted))

    # Sort by boosted score descending
    scored_rows.sort(key=lambda r: r[4], reverse=True)

    # Deduplicate: by variant_group_id AND by company+role overlap
    # (catches duplicates even when variant grouping missed them)
    seen_groups: dict[str, str] = {}  # group_key -> company
    seen_company_roles: set[tuple[str, str]] = set()  # (company_tokens, role_prefix) for fuzzy dedup
    selected: list[SelectedExperience] = []

    def _company_tokens(company: str) -> frozenset[str]:
        """Extract normalized tokens from company name for fuzzy matching."""
        if not company:
            return frozenset()
        return frozenset(company.lower().strip().split())

    for exp_id, company, role_title, variant_group_id, score in scored_rows:
        group_key = str(variant_group_id) if variant_group_id else str(exp_id)

        if group_key in seen_groups:
            prev_company = seen_groups[group_key]
            if prev_company and company and prev_company.lower() == company.lower():
                continue
        seen_groups[group_key] = company or ""

        # Additional dedup: skip if same company + similar role title already selected
        # NOTE: Fuzzy matching can have false positives/negatives. This is intentional:
        # - FALSE POSITIVES (skip valid entries): "Intern" matches "Investment Intern" substring
        #   (user can create new app or manually select if this is wrong)
        # - FALSE NEGATIVES (keep duplicates): "Consulting" vs "Strategy Consulting" may not match
        #   (edge case, low threshold prevents most duplicates)
        # Examples: "Intelligence Admin Assistant (Corporal)" & "Intelligence Admin Assistant (NS)"
        # Or: "GAO Capital" vs "GAO Capital Singapore"
        company_lower = (company or "").lower().strip()
        company_tokens = _company_tokens(company or "")  # Tokenize: "GAO Capital" → {"gao", "capital"}
        role_lower = (role_title or "").lower().strip()
        # Use first 20 chars of role as a fuzzy key (catches variants like "Role (variant A)" vs "Role (variant B)")
        role_prefix = role_lower[:20] if role_lower else ""
        
        # Check if we've seen this company+role combination before (with token-based fuzzy matching)
        skip_this = False
        if company_lower and role_prefix:
            for seen_company_tokens, seen_role_prefix in seen_company_roles:
                # If companies share core tokens (e.g. both have "gao" and "capital") and roles are similar
                shared_tokens = company_tokens & seen_company_tokens
                if shared_tokens and (shared_tokens == company_tokens or shared_tokens == seen_company_tokens):
                    # Companies are similar (one is subset of other or they share all tokens)
                    # Check if roles are similar: exact match OR one is substring of other (e.g. "Intern" in "Investment Intern")
                    roles_similar = (
                        seen_role_prefix == role_prefix or
                        role_prefix in seen_role_prefix or
                        seen_role_prefix in role_prefix
                    )
                    if roles_similar:
                        logger.info("Skipping duplicate: %s at %s (already have similar role at similar company)", role_title, company)
                        skip_this = True
                        break
        
        if skip_this:
            continue
            
        if company_lower and role_prefix:
            seen_company_roles.add((company_tokens, role_prefix))

        selected.append(SelectedExperience(
            id=str(exp_id),
            relevance_score=round(score, 3),
            reason=f"Matched with {score:.0%} similarity — {company or 'Unknown'}, {role_title or 'Unknown role'}",
        ))

        if len(selected) >= 4:
            break

    if not selected:
        raise ValueError("No experiences with embeddings found. Run /api/cv/re-embed to generate embeddings.")

    # Select education: prefer university-level, most recent entry
    edu_result = await db.execute(
        select(Education).order_by(
            Education.date_end.desc().nullslast(),
            Education.date_start.desc().nullslast(),
        )
    )
    education_rows = edu_result.scalars().all()

    def is_university_level(edu: Education) -> bool:
        text = f"{edu.institution or ''} {edu.degree or ''}".lower()
        return any(
            k in text
            for k in (
                "university",
                "college",
                "bachelor",
                "master",
                "phd",
                "mba",
                "msc",
                "bsc",
                "ba",
                "bs",
            )
        )
    
    def count_education_content(edu: Education) -> int:
        """Count total bullets/modules in an education entry to prefer richer entries."""
        count = 0
        if edu.achievements:
            if isinstance(edu.achievements, list):
                count += len(edu.achievements)
            elif isinstance(edu.achievements, dict):
                count += len(edu.achievements.get("items", []))
        if edu.modules:
            if isinstance(edu.modules, list):
                count += len(edu.modules)
            elif isinstance(edu.modules, dict):
                count += len(edu.modules.get("items", []))
        return count

    selected_education = []
    if education_rows:
        preferred = [e for e in education_rows if is_university_level(e)]
        candidates = preferred if preferred else education_rows
        # Among candidates with same dates, prefer the one with most content
        chosen = max(candidates, key=count_education_content)
        selected_education = [str(chosen.id)]

    # Select relevant projects via embedding similarity (domain-aware limit)
    # Fetch extra candidates so we can deduplicate by name/variant_group
    project_stmt = text("""
        SELECT id, name, variant_group_id FROM projects
        WHERE embedding IS NOT NULL
        ORDER BY 1 - (embedding <=> :embedding) DESC
        LIMIT :lim
    """).bindparams(bindparam("embedding", type_=Vector), bindparam("lim"))
    proj_result = await db.execute(
        project_stmt,
        {"embedding": jd_embedding, "lim": project_limit * 3},
    )
    # Deduplicate projects by name and variant_group_id
    selected_projects: list[str] = []
    seen_proj_names: set[str] = set()
    seen_proj_groups: set[str] = set()
    for row in proj_result.fetchall():
        proj_id, proj_name, proj_variant_group = row
        # Skip if same variant group already selected
        group_key = str(proj_variant_group) if proj_variant_group else str(proj_id)
        if group_key in seen_proj_groups:
            continue
        # Skip if same name already selected (case-insensitive)
        name_lower = (proj_name or "").strip().lower()
        if name_lower and name_lower in seen_proj_names:
            logger.info("Skipping duplicate project: %s", proj_name)
            continue
        seen_proj_groups.add(group_key)
        if name_lower:
            seen_proj_names.add(name_lower)
        selected_projects.append(str(proj_id))
        if len(selected_projects) >= project_limit:
            break

    # If no projects with embeddings, get all up to limit
    if not selected_projects:
        proj_all = await db.execute(select(Project.id, Project.name).limit(project_limit * 3))
        for row in proj_all.fetchall():
            name_lower = (row[1] or "").strip().lower()
            if name_lower and name_lower in seen_proj_names:
                continue
            if name_lower:
                seen_proj_names.add(name_lower)
            selected_projects.append(str(row[0]))
            if len(selected_projects) >= project_limit:
                break

    # Select relevant activities via embedding similarity (domain-aware limit)
    activity_stmt = text("""
        SELECT id, organization, role_title, variant_group_id FROM activities
        WHERE embedding IS NOT NULL
        ORDER BY 1 - (embedding <=> :embedding) DESC
        LIMIT :lim
    """).bindparams(bindparam("embedding", type_=Vector), bindparam("lim"))
    act_result = await db.execute(
        activity_stmt,
        {"embedding": jd_embedding, "lim": activity_limit * 3},
    )
    # Deduplicate activities by organization+role and variant_group_id
    selected_activities: list[str] = []
    seen_act_keys: set[str] = set()
    seen_act_groups: set[str] = set()
    for row in act_result.fetchall():
        act_id, org, role_title, act_variant_group = row
        group_key = str(act_variant_group) if act_variant_group else str(act_id)
        if group_key in seen_act_groups:
            continue
        dedup_key = f"{(org or '').strip().lower()}|{(role_title or '').strip().lower()[:20]}"
        if dedup_key in seen_act_keys and (org or "").strip():
            logger.info("Skipping duplicate activity: %s at %s", role_title, org)
            continue
        seen_act_groups.add(group_key)
        if (org or "").strip():
            seen_act_keys.add(dedup_key)
        selected_activities.append(str(act_id))
        if len(selected_activities) >= activity_limit:
            break

    # If no activities with embeddings, get all up to limit
    if not selected_activities:
        act_all = await db.execute(select(Activity.id).limit(activity_limit))
        selected_activities = [str(row[0]) for row in act_all.fetchall()]

    # ---- 1-page line budget ----
    # Letter paper with 10-11pt font fits ~34 content lines after header/edu/skills/section-title overhead.
    # Long bullets (>80 chars) wrap to 2 rendered lines. Strict 1-page: never exceed budget.
    MAX_RENDERED_LINES = 34

    from backend.utils import extract_bullet_texts

    def _estimate_rendered_lines(bullet_texts: list[str]) -> int:
        """Estimate how many rendered lines bullets will take (long bullets wrap).

        After tailoring, bullets target 120-170 chars which typically wrap to 2 lines.
        """
        lines = 0
        for b in bullet_texts:
            text = b if isinstance(b, str) else (b.get("text", "") if isinstance(b, dict) else str(b))
            char_len = len(text)
            if char_len > 170:
                lines += 3
            elif char_len > 85:
                lines += 2
            else:
                lines += 1
        return lines

    # Count rendered lines for selected experiences
    bullet_counts: dict[str, int] = {}
    if selected:
        exp_uuids = [uuid.UUID(e.id) for e in selected]
        bc_result = await db.execute(
            select(WorkExperience.id, WorkExperience.bullets)
            .where(WorkExperience.id.in_(exp_uuids))
        )
        for row in bc_result:
            bullets = row[1] or []
            if isinstance(bullets, list):
                bullet_counts[str(row[0])] = _estimate_rendered_lines(bullets)
            else:
                bullet_counts[str(row[0])] = 0

    # Count rendered lines for projects
    proj_bullet_counts: dict[str, int] = {}
    if selected_projects:
        proj_uuids = [uuid.UUID(p) for p in selected_projects]
        pbc_result = await db.execute(
            select(Project.id, Project.bullets)
            .where(Project.id.in_(proj_uuids))
        )
        for row in pbc_result:
            bullets = row[1] or []
            if isinstance(bullets, list):
                proj_bullet_counts[str(row[0])] = _estimate_rendered_lines(bullets)
            else:
                proj_bullet_counts[str(row[0])] = 0

    # Count rendered lines for activities
    act_bullet_counts: dict[str, int] = {}
    if selected_activities:
        act_uuids = [uuid.UUID(a) for a in selected_activities]
        abc_result = await db.execute(
            select(Activity.id, Activity.bullets)
            .where(Activity.id.in_(act_uuids))
        )
        for row in abc_result:
            bullets = row[1] or []
            if isinstance(bullets, list):
                act_bullet_counts[str(row[0])] = _estimate_rendered_lines(bullets)
            else:
                act_bullet_counts[str(row[0])] = 0

    # Total rendered lines: each entry = 1 header line + rendered bullet lines
    total_lines = 0
    for e in selected:
        total_lines += 1 + bullet_counts.get(e.id, 3)
    for p in selected_projects:
        total_lines += 1 + proj_bullet_counts.get(p, 2)
    for a in selected_activities:
        total_lines += 1 + act_bullet_counts.get(a, 3)

    # Trim from lowest-relevance entries if over budget
    if total_lines > MAX_RENDERED_LINES:
        logger.info("Over 1-page budget: %d rendered lines > %d. Trimming.", total_lines, MAX_RENDERED_LINES)

        # Trim order depends on role type:
        # Tech/quant → trim activities first (keep projects)
        # Finance/consulting → trim projects first (keep leadership)
        if is_tech:
            trim_order = [
                (selected_activities, act_bullet_counts, 3),
                (selected_projects, proj_bullet_counts, 2),
            ]
        else:
            trim_order = [
                (selected_projects, proj_bullet_counts, 2),
                (selected_activities, act_bullet_counts, 3),
            ]

        for section_list, counts_map, default_lines in trim_order:
            while total_lines > MAX_RENDERED_LINES and section_list:
                removed = section_list.pop()
                total_lines -= 1 + counts_map.get(removed, default_lines)

        # Last resort: trim experiences (keep min 3)
        while total_lines > MAX_RENDERED_LINES and len(selected) > 3:
            removed = selected.pop()
            total_lines -= 1 + bullet_counts.get(removed.id, 3)

        logger.info("After trimming: %d rendered lines, %d exp, %d proj, %d act",
                     total_lines, len(selected), len(selected_projects), len(selected_activities))

    # Select skills: JD-relevant first, then fill with remaining up to a cap
    skill_result = await db.execute(
        select(Skill.id, Skill.name, Skill.category).where(Skill.is_duplicate_of.is_(None))
    )
    skill_rows = skill_result.fetchall()

    # Build a set of JD terms to match against (lowercase for comparison)
    jd_terms = set()
    for field in ["required_skills", "nice_to_have_skills", "tools_and_technologies", "keywords"]:
        for term in jd_parsed.get(field, []):
            jd_terms.add(term.lower())

    # Partition: JD-matching skills vs non-matching
    # Deduplicate by lowercase name as we go
    jd_matched = []
    non_matched = []
    seen_skill_names: set[str] = set()
    
    for row in skill_rows:
        skill_id, skill_name, skill_category = row
        name_lower = (skill_name or "").strip().lower()
        
        # Skip if we've already seen this skill name
        if name_lower in seen_skill_names or not name_lower:
            continue
        seen_skill_names.add(name_lower)
        
        # Skip "Tool" category since we removed it from the template
        if (skill_category or "").lower() == "tool":
            continue
        
        is_match = any(
            name_lower == term or name_lower in term or term in name_lower
            for term in jd_terms
        )
        if is_match:
            jd_matched.append(row)
        else:
            non_matched.append(row)

    # Always include JD-matched skills; fill remaining slots with non-matched
    # Cap total to keep the skills section compact (1-2 lines per category)
    MAX_SKILLS = 25
    selected_skill_rows = jd_matched[:MAX_SKILLS]
    remaining_slots = MAX_SKILLS - len(selected_skill_rows)
    if remaining_slots > 0:
        selected_skill_rows.extend(non_matched[:remaining_slots])

    selected_skills = [str(row[0]) for row in selected_skill_rows]

    logger.info("Skills: %d JD-matched, %d total selected (cap %d)",
                len(jd_matched), len(selected_skills), MAX_SKILLS)

    return SelectionResult(
        selected_experiences=selected,
        selected_education=selected_education,
        selected_projects=selected_projects,
        selected_activities=selected_activities,
        selected_skills=selected_skills,
    )
