"""Agent: Tailor selected experiences to the job description."""

from __future__ import annotations

import asyncio
import re
from difflib import SequenceMatcher

_NUMBER_RE = re.compile(
    r"\b\d[\d,]*(?:\.\d+)?(?:\+|[kKMB]|%|x)?\b"  # 10,000+ / 25% / 8x / $800K
    r"|\btop\s+\d+\b"                               # top 5
    r"|\b\d+\s+of\s+\d+\b",                         # 1 of 80
    re.IGNORECASE,
)

_BANNED_PHRASE_RE = re.compile(
    r"\b(?:showcasing|demonstrating|highlighting|leveraging expertise in)\s+\w",
    re.IGNORECASE,
)


def _extract_numbers(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(text))


def _has_hallucinated_numbers(original: str, suggested: str) -> bool:
    """True if suggested introduces numbers not present in original."""
    return bool(_extract_numbers(suggested) - _extract_numbers(original))

from pydantic import BaseModel, Field

from backend.clients import get_openai_client
from backend.config import get_settings
from backend.utils import extract_bullet_texts, split_description_to_bullets

from .domain_guidance import _get_domain_guidance


class TailoredBullet(BaseModel):
    text: str = Field(description="The rewritten bullet point")
    has_placeholder: bool = Field(
        default=False,
        description="True if this bullet contains a [X] placeholder the user should fill in",
    )
    outcome_type: str = Field(
        default="",
        description="Type of outcome framed: 'quantified', 'placeholder', 'qualitative', or 'process' (no outcome)",
    )


class TailoredExperience(BaseModel):
    experience_id: str
    original_bullets: list[str]
    suggested_bullets: list[TailoredBullet]
    changes_made: list[str]
    confidence: float = Field(ge=0, le=1)
    requirements_addressed: list[str] = Field(
        default_factory=list,
        description="Which JD requirements this experience now addresses",
    )
    coaching_note: str = Field(
        default="",
        description=(
            "One short sentence of editing guidance for the user. "
            "Strong match: confirm and say what to preserve, e.g. 'Strong match — keep the deal sizes and client names in every bullet.' "
            "Partial match: say how to strengthen, e.g. 'Partial match — frame the Python work toward data pipeline requirements.' "
            "Gap: be honest, e.g. 'Gap area — JD wants stakeholder management; surface any cross-team work if truthful.' "
            "Max 100 characters. No filler."
        ),
    )


class TailorOutput(BaseModel):
    tailored_experiences: list[TailoredExperience]


class TailoredProject(BaseModel):
    project_id: str
    original_bullets: list[str]
    suggested_bullets: list[TailoredBullet]
    changes_made: list[str]
    confidence: float = Field(ge=0, le=1)
    requirements_addressed: list[str] = Field(
        default_factory=list,
        description="Which JD requirements this project now addresses",
    )
    coaching_note: str = Field(
        default="",
        description=(
            "One short sentence of editing guidance for the user. "
            "Strong match: confirm and say what to preserve. "
            "Partial match: say how to strengthen it. "
            "Gap: be honest about what's missing. "
            "Max 100 characters. No filler."
        ),
    )


class TailorProjectsOutput(BaseModel):
    tailored_projects: list[TailoredProject]


async def _expand_short_bullet(
    original: str,
    suggested: TailoredBullet,
    jd_summary: str,
) -> TailoredBullet:
    """Expand bullets under 100 chars by restoring detail from the original."""
    if len(suggested.text) >= 100:
        return suggested

    if suggested.has_placeholder and "[X]" not in suggested.text:
        return suggested

    system_prompt = (
        "You expand a CV bullet to 120-170 characters. "
        "Restore important details from the original bullet that were lost (especially technologies, metrics, achievements, and scope). "
        "Do not invent new facts. "
        "If the bullet contains [X], keep it. "
        "Return only the revised bullet text."
    )
    user_message = (
        "Original bullet (may have important details that were dropped):\n"
        f"{original}\n\n"
        "Current bullet (too short — missing detail):\n"
        f"{suggested.text}\n\n"
        "Job context:\n"
        f"{jd_summary}\n\n"
        "Expand the current bullet to 120-170 characters, restoring important technologies, metrics, and achievements from the original."
    )

    _client = get_openai_client()
    _settings = get_settings()
    response = await _client.chat.completions.create(
        model=_settings.model_mini,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=_settings.temp_gap_analysis,
    )

    text = (response.choices[0].message.content or "").strip().replace("\n", " ")
    if not text:
        return suggested

    # Accept anything in the 100-200 range
    if len(text) < 100 or len(text) > 200:
        return suggested

    if suggested.has_placeholder and "[X]" not in text:
        return suggested

    return TailoredBullet(
        text=text,
        has_placeholder="[X]" in text,
        outcome_type=suggested.outcome_type,
    )


async def _trim_just_over_line(
    original: str,
    suggested: TailoredBullet,
    jd_summary: str,
    target_length: int = 95,
) -> TailoredBullet:
    """Optimize bullets that are just slightly over one line (105-145 chars).
    
    LaTeX CV with \\small font fits ~90-100 chars per line. Bullets 105-145 chars
    waste half a line. Try to trim them to fit on one line without losing key info.
    """
    text_len = len(suggested.text)
    if text_len < 95 or text_len > 135:
        return suggested

    system_prompt = (
        f"You optimize a CV bullet to fit on ONE line (~{target_length} chars max). "
        "The bullet currently wastes half a line. Try to trim it smartly to ~95-100 chars. "
        "RULES: "
        "1. NEVER remove named technologies (e.g. AWS S3, React, PostgreSQL, XGBoost). "
        "2. NEVER remove numbers, percentages, or metrics (e.g. 10,000+, 40%, $800K). "
        "3. NEVER remove outcomes (e.g. 'reducing by 30%', 'improving accuracy'). "
        "4. Cut ONLY filler words: 'utilized'→'used', 'in order to'→'to', 'leveraging'→'via'. "
        "5. Collapse phrases: 'built and deployed'→'deployed', 'developed and implemented'→'implemented'. "
        "6. If the bullet contains [X], keep it. "
        "7. If you can't trim it safely without losing key info, return it UNCHANGED. "
        "Return only the revised bullet text."
    )
    user_message = (
        "Original bullet:\n"
        f"{original}\n\n"
        "Current bullet (wasting half a line — slightly too long):\n"
        f"{suggested.text}\n\n"
        f"Length: {text_len} chars (target: ~95 to fit one line)\n\n"
        "Job context:\n"
        f"{jd_summary}\n\n"
        f"Trim to ~95 characters if possible. Keep ALL technologies, numbers, and outcomes. "
        "If you can't trim safely, return the bullet UNCHANGED."
    )

    _client = get_openai_client()
    _settings = get_settings()
    response = await _client.chat.completions.create(
        model=_settings.model_mini,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=_settings.temp_gap_analysis,
    )

    text = (response.choices[0].message.content or "").strip().replace("\n", " ")
    if not text:
        return suggested

    # Accept if it's shorter and still reasonable (80+ chars), or if model returned unchanged
    if text == suggested.text:
        return suggested
    if len(text) < 80 or len(text) > 140:
        return suggested

    if suggested.has_placeholder and "[X]" not in text:
        return suggested

    return TailoredBullet(
        text=text,
        has_placeholder="[X]" in text,
        outcome_type=suggested.outcome_type,
    )


async def _trim_long_bullet(
    original: str,
    suggested: TailoredBullet,
    jd_summary: str,
) -> TailoredBullet:
    """Condense a bullet that exceeds 200 characters. Only trims truly long bullets."""
    if len(suggested.text) <= 200:
        return suggested

    system_prompt = (
        "You condense a CV bullet to 140-190 characters. "
        "RULES: "
        "1. NEVER remove named technologies (e.g. AWS S3, React, PostgreSQL, XGBoost). "
        "2. NEVER remove numbers, percentages, or metrics (e.g. 10,000+, 40%, $800K). "
        "3. NEVER remove achievements or outcomes (e.g. 'achieved top 5', 'reducing by 30%'). "
        "4. Cut ONLY filler words: 'utilized'→'used', 'in order to'→'to', 'leveraged'→'used'. "
        "5. If the bullet contains [X], keep it. "
        "Return only the revised bullet text."
    )
    user_message = (
        "Original bullet:\n"
        f"{original}\n\n"
        "Current bullet (too long, needs trimming):\n"
        f"{suggested.text}\n\n"
        "Job context:\n"
        f"{jd_summary}\n\n"
        "Condense to 140-190 characters. Keep ALL technologies, numbers, and achievements."
    )

    _client = get_openai_client()
    _settings = get_settings()
    response = await _client.chat.completions.create(
        model=_settings.model_mini,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=_settings.temp_gap_analysis,
    )

    text = (response.choices[0].message.content or "").strip().replace("\n", " ")
    if not text:
        return suggested

    # Accept anything in the 100-200 range
    if len(text) < 100 or len(text) > 200:
        return suggested

    if suggested.has_placeholder and "[X]" not in text:
        return suggested

    return TailoredBullet(
        text=text,
        has_placeholder="[X]" in text,
        outcome_type=suggested.outcome_type,
    )


def _build_jd_summary(jd_parsed: dict) -> str:
    """Build a compact JD context string used in all tailoring prompts."""
    key_responsibilities = jd_parsed.get("key_responsibilities", [])
    return f"""
Role: {jd_parsed.get('role_summary', 'N/A')}
Domain: {jd_parsed.get('domain', 'N/A')}
Seniority: {jd_parsed.get('seniority_level', 'N/A')}
Key Responsibilities: {'; '.join(key_responsibilities) if key_responsibilities else 'N/A'}
Required Skills: {', '.join(jd_parsed.get('required_skills', []))}
Nice to Have: {', '.join(jd_parsed.get('nice_to_have_skills', []))}
Keywords: {', '.join(jd_parsed.get('keywords', []))}
Outcome Signals: {', '.join(jd_parsed.get('outcome_signals', []))}
"""


async def _apply_length_refinements(
    tailored_list: list,
    jd_summary: str,
    trim_low: int = 95,
    trim_high: int = 135,
) -> None:
    """Run trim/expand corrections on all bullets in parallel, updating in-place."""
    pending: list[tuple[int, int, object]] = []
    for ei, entry in enumerate(tailored_list):
        for bi, (orig, suggested) in enumerate(
            zip(entry.original_bullets, entry.suggested_bullets)
        ):
            if trim_low <= len(suggested.text) <= trim_high:
                coro = _trim_just_over_line(orig, suggested, jd_summary)
            elif len(suggested.text) < 100:
                coro = _expand_short_bullet(orig, suggested, jd_summary)
            elif len(suggested.text) > 200:
                coro = _trim_long_bullet(orig, suggested, jd_summary)
            else:
                continue
            pending.append((ei, bi, coro))

    if not pending:
        return

    results = await asyncio.gather(*[t[2] for t in pending])
    for (ei, bi, _), result in zip(pending, results):
        tailored_list[ei].suggested_bullets[bi] = result


SYSTEM_PROMPT = """\
You are a CV bullet point tailoring expert who writes achievement-oriented, ATS-friendly bullets.

## Core Philosophy
Every bullet should answer: "What did I do, and what was the result?" Recruiters skim the top third of a CV in 6 seconds — front-load impact.

## Bullet Structure (use one of these patterns)
1. QUANTIFIED: "[Action verb] [what you did], resulting in [metric]." — Use when the original has numbers.
2. PLACEHOLDER: "[Action verb] [what you did], achieving [X]% [outcome type]." — Use when the original describes impactful work but lacks numbers. Mark has_placeholder=true so the user can fill in real figures.
3. QUALITATIVE: "[Action verb] [what you did], enabling [business outcome]." — Use when the work is strategic/soft and numbers don't apply.
4. PROCESS (last resort): "[Action verb] [what you did] for/across [scope]." — Only when no outcome can be reasonably inferred.

## NEVER-DROP Rules (highest priority)
These elements must NEVER be removed from a bullet during tailoring, even if the bullet runs long:
- **Quantified outcomes**: Any number, percentage, dollar amount, or scale metric (e.g. "10,000+ documents", "40%", "$800K", "500 personnel"). NEVER drop a number.
- **Named technologies and tools**: Specific tech names like "AWS S3", "React", "PostgreSQL", "RAG", "XGBoost", "SHAP", "Bloomberg API". These are what ATS systems and recruiters Ctrl+F for. You can abbreviate ("retrieval-augmented generation" → "RAG") but NEVER delete a technology.
- **Scope indicators**: Team sizes, user counts, geographic reach (e.g. "across EMEA", "3 new markets").
- If keeping all these makes the bullet 130-140 chars, that is ACCEPTABLE. A slightly long bullet that preserves keywords is far better than a short bullet that lost them.

## Keyword Integration Rules (Anti-Stuffing)
- Each keyword should appear at MOST 2-3 times across ALL bullets combined.
- Integrate keywords where they naturally describe what was done, NOT as appended lists.
- NEVER add a keyword that doesn't relate to what the person actually did in that role.
- Prefer synonyms and natural variations over exact repetition (e.g. alternate between "stakeholder management" and "partnered with cross-functional stakeholders").
- If a keyword doesn't fit ANY experience, do NOT force it in. Flag it in changes_made as "keyword X: no natural fit found."

## BANNED Phrases (Highest Priority — Never Use These)
You are a senior CV reviewer with 15 years of experience. These phrases INSTANTLY mark a bullet as AI-generated and unnatural. NEVER append or include:
- "showcasing [skill]", "demonstrating [skill]", "highlighting [skill]"
- "leveraging expertise in [X]", "showcasing proficiency in [X]"
- "showcasing strong [X] skills", "demonstrating solid [X] abilities"
- "aligning with [X] objectives", "contributing to [X] goals"
- Any phrase that TELLS the reader about a skill rather than SHOWING it through action

Instead of TELLING ("demonstrating quantitative analysis skills"), SHOW by embedding the skill into the action:
- BAD: "Selected as 1 of 80 students for Citadel's Trading Invitational, demonstrating quantitative analysis skills"
- GOOD: "Selected as 1 of 80 students for Citadel's European Trading Invitational" (already strong — leave it alone)
- BAD: "Engineered an automated data pipeline with PostgreSQL, showcasing Python expertise"
- GOOD: "Built an automated data pipeline in Python using PostgreSQL, AWS S3, and OpenAI embeddings to vectorise 10,000+ documents"

The rule is simple: if you can delete the ending clause and the bullet still makes sense, the clause was filler. Real tailoring changes the FRAMING of the action, not tacking praise onto the end.

## Action Verb Rules
- NEVER start more than 2 bullets across the ENTIRE CV with the same verb. If you've already used "Developed" twice, use a synonym: Built, Engineered, Created, Designed, Implemented, Automated, Architected, Launched.
- Vary verb strength by seniority: entry (built, developed, analyzed, created) → senior (architected, spearheaded, drove) → lead (defined, established, transformed).

## Truthfulness Rules
- NEVER invent metrics, outcomes, or responsibilities not implied by the original bullet.
- When adding a placeholder [X], choose a plausible outcome type based on the work described (e.g. cost savings, efficiency gain, user growth, error reduction).
- If the original bullet describes process work with no clear outcome, it's OK to leave it as a process bullet rather than fabricate impact.
- Preserve the original scope and seniority — don't inflate "assisted with" into "led" or "managed."

## Seniority Calibration
- Entry/Mid: Focus on execution, learning velocity, tools used. "Built X using Y, reducing Z by [X]%."
- Senior: Focus on ownership, cross-team impact, decisions made. "Designed and led X, driving [X]% improvement in Y."
- Lead/Director: Focus on strategy, team outcomes, business impact. "Defined strategy for X across N teams, resulting in [X]% Y."

## What "Tailoring" Actually Means
Tailoring is NOT paraphrasing or shortening. Tailoring means:
1. REFRAME the bullet to lead with the theme the JD cares about (e.g. if JD says "data pipelines", lead with the pipeline aspect, not the deployment aspect).
2. ADD JD-relevant framing language (e.g. add "for real-time analytics" if the JD emphasizes real-time systems), but ONLY if truthful.
3. KEEP all existing technical details — they are the substance of the bullet.
4. Return VERBATIM only if the bullet ALREADY leads with the most JD-critical theme AND already uses the key JD vocabulary naturally. If the content is relevant but the JD theme is buried mid-sentence or absent, reframe the opening even if the rest stays the same. A cosmetic synonym swap ("Built"→"Developed") is NOT tailoring — only reframe when it meaningfully shifts emphasis toward a JD priority.

## Length Guideline
- TARGET: 120-170 characters per bullet. This keeps bullets detailed and substantive.
- ACCEPTABLE: 100-200 characters. Longer bullets that preserve all details are ALWAYS better than shorter bullets that lost information.
- NEVER sacrifice a technology name, metric, scope, or achievement to shorten a bullet.
- If a bullet must be shortened, cut filler words ("utilized"→"used", "in order to"→"to", "leveraged"→"used") — NEVER cut named technologies, numbers, or outcomes.

## coaching_note
Write one short, honest, action-oriented sentence for the user who will review your suggestions.
- Strong match (confidence ≥ 0.85): confirm it and say what to preserve. e.g. "Strong match — keep the deal sizes and client names in every bullet."
- Partial match (0.65–0.84): say how to strengthen. e.g. "Partial match — frame the Python work toward data pipeline requirements."
- Weak match (< 0.65): be honest. e.g. "Gap area — JD wants stakeholder management; surface any cross-team work if truthful."
- Max 100 characters. No filler phrases. Write it directly to the user (no "Note:" prefix).

## Examples: Paraphrasing vs. Real Tailoring
These examples show the difference between useless paraphrasing and meaningful tailoring.

### Example 1 — JD emphasizes "real-time analytics" and "data pipelines"
Original: "Built batch ETL pipelines using Airflow to process 10K+ daily records into PostgreSQL"
BAD (paraphrasing): "Developed ETL pipelines utilizing Airflow to handle 10K+ daily records in PostgreSQL" ← synonym swap ("Built"→"Developed", "using"→"utilizing"), no JD alignment
GOOD (tailoring): "Built real-time data pipelines using Airflow, processing 10K+ daily records into PostgreSQL for analytics" ← leads with "real-time data pipelines" (JD theme), adds "for analytics" (JD context), keeps all tech and metrics

### Example 2 — JD emphasizes "stakeholder communication" and "cross-functional collaboration"
Original: "Analyzed sales data and created weekly Tableau dashboards for the marketing team"
BAD (paraphrasing): "Developed Tableau dashboards by analyzing sales data for marketing" ← reworded but no JD theme surfaced
GOOD (tailoring): "Partnered with cross-functional stakeholders to design Tableau dashboards from sales data, driving data-informed marketing decisions" ← leads with "cross-functional stakeholders" (JD theme), adds "data-informed decisions" (JD outcome signal)

### Example 3 — Bullet already matches JD well
Original: "Designed and deployed ML pipeline using XGBoost and SHAP, reducing churn by 15%"
GOOD: Return VERBATIM — this bullet already has strong action verb, named tech, and quantified outcome. Do not touch it.

### Example 4 — JD emphasizes "Python" and "quantitative analysis" (ANTI-PATTERN)
Original: "Selected as 1 of 80 students across EMEA for Citadel's European Trading Invitational"
BAD (appended filler): "Selected as 1 of 80 students for Citadel's European Trading Invitational, demonstrating quantitative analysis skills" ← "demonstrating X skills" is empty filler a recruiter will ignore
GOOD: Return VERBATIM — "1 of 80 students" and "Trading Invitational" already imply quantitative ability. Adding "demonstrating quantitative analysis skills" adds zero information and sounds AI-generated.

## Output Rules
- CRITICAL: Do NOT make cosmetic changes like spelling normalization (e.g. "visualise"→"visualize"), minor word reordering, or synonym swaps that don't add JD keywords. A change must either: (a) reframe the opening to lead with a JD Key Responsibility theme, (b) add a JD-relevant outcome signal or framing context, or (c) meaningfully surface a hidden keyword. If none of (a)/(b)/(c) apply, copy the bullet verbatim.
- CRITICAL: Return EXACTLY the same number of suggested_bullets as original_bullets — one per original bullet. Never split a bullet into two. Never merge two into one.
- For each change, document what you changed and why in changes_made. If you shortened a bullet, explain what you removed and why it was safe to remove.
- In requirements_addressed, list which JD requirements this experience's bullets now cover.
- Set confidence based on how well the rewrite matches the JD (0.5 = minimal, 1.0 = strong match).

{domain_section}

{gap_analysis_section}

{rules_section}
"""


def _score_keyword_fit(keyword: str, bullet: str) -> int:
    """Score how naturally a keyword fits a bullet (higher = better fit).

    Uses word-level overlap so multi-word keywords score proportionally.
    """
    kw_words = set(keyword.lower().split())
    bullet_words = set(bullet.lower().split())
    return len(kw_words & bullet_words)


def _assign_keywords_to_bullets(
    bullets: list[str],
    priority_keywords: list[str],
) -> dict[int, list[str]]:
    """Exclusively assign each keyword to the single bullet where it fits best.

    Each keyword goes to exactly one bullet — prevents the same keyword being
    suggested for every bullet (keyword stuffing).
    """
    assignment: dict[int, list[str]] = {i: [] for i in range(len(bullets))}
    for kw in priority_keywords:
        kw_lower = kw.lower()
        # Skip if already present in any bullet (no need to inject)
        if any(kw_lower in b.lower() for b in bullets):
            continue
        # Find the bullet with the best word-overlap fit
        scores = [_score_keyword_fit(kw, b) for b in bullets]
        best_idx = max(range(len(scores)), key=lambda i: scores[i])
        assignment[best_idx].append(kw)
    return assignment


def _build_bullet_briefs(
    bullets: list[str],
    gap_analysis: dict | None,
    jd_parsed: dict,
) -> list[str]:
    """For each bullet, build a short tailoring brief: which JD themes to surface.

    Uses gap analysis mappings (evidence + suggested_framing) when available,
    otherwise assigns each missing JD keyword exclusively to the bullet where
    it fits best — avoiding keyword repetition across sibling bullets.
    """
    # Priority-ordered keywords: required skills first, then general keywords
    priority_keywords = (
        jd_parsed.get("required_skills", []) + jd_parsed.get("keywords", [])
    )

    # Build a mapping from bullet text → relevant gap analysis entries
    bullet_to_framings: dict[str, list[str]] = {}
    if gap_analysis:
        for mapping in gap_analysis.get("mappings", []):
            evidence = mapping.get("evidence", "").lower()
            framing = mapping.get("suggested_framing", "")
            requirement = mapping.get("requirement", "")
            status = mapping.get("status", "")
            if status in ("strong_match", "partial_match") and evidence:
                for bullet in bullets:
                    if _similarity(evidence, bullet.lower()) > 0.4 or any(
                        word in evidence for word in bullet.lower().split()[:5]
                    ):
                        bullet_to_framings.setdefault(bullet, [])
                        if framing:
                            bullet_to_framings[bullet].append(
                                f"{requirement} — {framing}"
                            )
                        else:
                            bullet_to_framings[bullet].append(requirement)

    # Pre-assign missing keywords exclusively to best-fit bullets
    keyword_assignment = _assign_keywords_to_bullets(bullets, priority_keywords[:12])

    # Build sibling context: which keywords are already covered across all bullets
    covered_keywords = [
        kw for kw in priority_keywords if any(kw.lower() in b.lower() for b in bullets)
    ][:4]

    briefs = []
    for idx, bullet in enumerate(bullets):
        # Use gap analysis framings if available (highest quality)
        if bullet in bullet_to_framings:
            themes = bullet_to_framings[bullet]
            briefs.append(
                f"  → Tailoring brief: Reframe to surface these JD themes: {'; '.join(themes)}"
            )
        else:
            # Fallback: use exclusively-assigned keywords for this bullet
            bullet_lower = bullet.lower()
            assigned_missing = keyword_assignment.get(idx, [])
            present_keywords = [
                kw for kw in priority_keywords if kw.lower() in bullet_lower
            ][:2]
            sibling_note = (
                f" (Other bullets in this experience already cover: {', '.join(covered_keywords)} — do not repeat.)"
                if covered_keywords else ""
            )
            if assigned_missing:
                present_note = (
                    f" Already in this bullet: {', '.join(present_keywords)}." if present_keywords else ""
                )
                briefs.append(
                    f"  → Tailoring brief: This bullet is the best place to inject: {', '.join(assigned_missing)}."
                    f"{present_note}{sibling_note}"
                )
            elif present_keywords:
                briefs.append(
                    f"  → Tailoring brief: Bullet already covers: {', '.join(present_keywords[:3])}. "
                    f"Reframe to lead with the most JD-critical one.{sibling_note} Return verbatim if already optimal."
                )
            else:
                briefs.append(
                    f"  → Tailoring brief: No direct JD keyword match. Check Key Responsibilities above for the same type of work and reframe to lead with that theme.{sibling_note} Return verbatim if genuinely unrelated."
                )
    return briefs


async def tailor_experiences(
    experiences: list[dict],
    jd_parsed: dict,
    gap_analysis: dict | None = None,
    rules_text: str = "",
) -> list[TailoredExperience]:
    """Tailor selected experiences to match the JD using GPT-4o.

    Args:
        experiences: List of dicts with keys: id, company, role_title, bullets.
        jd_parsed: Parsed JD dict.
        gap_analysis: Optional gap analysis dict.
        rules_text: Pre-formatted tailoring rules string.
    """

    # Build gap analysis context for the prompt
    gap_section = ""
    if gap_analysis:
        mappings = gap_analysis.get("mappings", [])
        gaps = [m for m in mappings if m.get("status") == "gap"]
        partial = [m for m in mappings if m.get("status") == "partial_match"]
        warnings = gap_analysis.get("keyword_density_warnings", [])

        parts = []
        if partial:
            parts.append("## Partial Matches to Strengthen\nThese requirements have adjacent experience — reframe bullets to surface relevance:")
            for m in partial:
                parts.append(f"- {m['requirement']}: {m.get('suggested_framing', '')}")
        if gaps:
            parts.append("## Gaps (Do NOT fabricate experience for these)\nThe candidate lacks direct experience here. Do NOT try to address these in bullet rewrites:")
            for m in gaps:
                parts.append(f"- {m['requirement']}")
        if warnings:
            parts.append("## Keyword Density Warnings\nThese keywords risk looking unnatural if overused:")
            for w in warnings:
                parts.append(f"- {w}")
        gap_section = "\n".join(parts)

    domain_section = _get_domain_guidance(jd_parsed.get("domain", ""))
    system_prompt = SYSTEM_PROMPT.format(
        domain_section=domain_section,
        rules_section=rules_text,
        gap_analysis_section=gap_section,
    )

    # Build experience descriptions for GPT-4o
    exp_descriptions = []
    for exp in experiences:
        bullets = extract_bullet_texts(exp.get("bullets", []))
        exp_descriptions.append({
            "experience_id": str(exp["id"]),
            "company": exp.get("company") or "Unknown",
            "role": exp.get("role_title") or "Unknown",
            "bullets": bullets,
        })

    jd_summary = _build_jd_summary(jd_parsed)

    user_message = f"""Target Job Description:
{jd_summary}

Experiences to tailor:
"""
    for ed in exp_descriptions:
        user_message += f"\n--- Experience: {ed['company']} - {ed['role']} (ID: {ed['experience_id']}) ---\n"
        briefs = _build_bullet_briefs(ed["bullets"], gap_analysis, jd_parsed)
        for i, (bullet, brief) in enumerate(zip(ed["bullets"], briefs)):
            user_message += f"  {i+1}. {bullet}\n{brief}\n"

    user_message += """
For each bullet, follow this process:
1. Read the tailoring brief above the bullet — it tells you which JD themes to surface.
2. Decide the lead theme: which JD priority should this bullet open with?
3. Reframe the bullet to lead with that theme, keeping ALL existing tech details and metrics.
4. If the bullet already leads with the right theme and matches the JD well, return it VERBATIM — do NOT make cosmetic synonym swaps.
5. A good tailoring change reframes emphasis and adds JD-relevant context. A bad change just swaps synonyms.

Return all experiences."""

    _client = get_openai_client()
    _settings = get_settings()
    response = await _client.beta.chat.completions.parse(
        model=_settings.model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format=TailorOutput,
        temperature=_settings.temp_tailoring,
    )

    tailored = response.choices[0].message.parsed.tailored_experiences

    # Enforce 1-to-1: if bullet count drifts, fall back to originals for that experience
    for te in tailored:
        if len(te.suggested_bullets) != len(te.original_bullets):
            te.suggested_bullets = [
                TailoredBullet(text=b, has_placeholder=False, outcome_type="process")
                for b in te.original_bullets
            ]

    # Post-process: revert trivial changes where the model barely edited the bullet
    for te in tailored:
        for i, (orig, suggested) in enumerate(
            zip(te.original_bullets, te.suggested_bullets)
        ):
            # Normalize for comparison: lowercase, strip whitespace/punctuation
            orig_norm = orig.lower().strip().rstrip(".")
            sugg_norm = suggested.text.lower().strip().rstrip(".")
            # If the only difference is casing, spelling, or trailing punctuation,
            # revert to the original
            if orig_norm == sugg_norm or _similarity(orig_norm, sugg_norm) > 0.95:
                te.suggested_bullets[i] = TailoredBullet(
                    text=orig,
                    has_placeholder=False,
                    outcome_type=suggested.outcome_type,
                )
            elif _has_hallucinated_numbers(orig, suggested.text):
                te.suggested_bullets[i] = TailoredBullet(
                    text=orig,
                    has_placeholder=False,
                    outcome_type=suggested.outcome_type,
                )
            elif _BANNED_PHRASE_RE.search(suggested.text):
                te.suggested_bullets[i] = TailoredBullet(
                    text=orig,
                    has_placeholder=False,
                    outcome_type=suggested.outcome_type,
                )

    # Enforce length by trimming just-over-line / expanding short / trimming long bullets
    await _apply_length_refinements(tailored, jd_summary, trim_low=95, trim_high=135)

    _clean_changes_made(tailored)

    return tailored


PROJECT_SYSTEM_PROMPT = """\
You are a CV bullet point tailoring expert. You are tailoring bullets for projects and leadership activities.

## Core Philosophy
Project/leadership bullets should highlight initiative, technical depth, and transferable skills relevant to the target role.

## Bullet Structure (use one of these patterns)
1. QUANTIFIED: "[Action verb] [what you did], resulting in [metric]." — Use when the original has numbers.
2. PLACEHOLDER: "[Action verb] [what you did], achieving [X]% [outcome type]." — Use when impactful but lacks numbers. Mark has_placeholder=true.
3. QUALITATIVE: "[Action verb] [what you did], enabling [outcome]." — Use when numbers don't apply.
4. PROCESS (last resort): "[Action verb] [what you did] for/across [scope]." — Only when no outcome can be inferred.

## NEVER-DROP Rules (highest priority)
- **Quantified outcomes**: NEVER remove numbers, percentages, dollar amounts, or scale metrics.
- **Named technologies and tools**: NEVER remove specific tech names. Abbreviate if needed but never delete.
- **Scope indicators**: Team sizes, user counts, competition rankings (e.g. "Top 5", "500 projects").
- A 135-char bullet that preserves keywords is better than a 115-char bullet that lost them.

## Keyword Integration Rules
- Integrate JD keywords naturally where they describe what was actually done.
- NEVER add keywords that don't relate to the actual project work.
- Prefer natural variations over exact repetition.

## BANNED Phrases (Never Use)
NEVER append filler like "showcasing [skill]", "demonstrating [skill]", "highlighting [skill]", "leveraging expertise in [X]". These instantly mark a bullet as AI-generated. If the ending clause can be deleted and the bullet still makes sense, it was filler. Embed keywords into the ACTION, don't tack praise onto the end.

## Action Verb Rules
- NEVER start more than 2 bullets across ALL projects/activities with the same verb.
- Vary verbs: Built, Implemented, Designed, Created, Engineered, Launched, Automated, Led.

## Truthfulness Rules
- NEVER invent metrics, outcomes, or responsibilities not implied by the original bullet.
- Preserve the original scope — don't inflate contributions.

## What "Tailoring" Actually Means
- REFRAME to lead with the theme the JD cares about.
- ADD JD-relevant framing (e.g. "for real-time analytics") only if truthful.
- KEEP all existing tech details and metrics.
- Return VERBATIM only if the bullet ALREADY leads with the most JD-critical theme AND already uses the key JD vocabulary naturally. If the content is relevant but the JD theme is buried mid-sentence, reframe the opening. Cosmetic synonym swaps are NOT tailoring.

## Length Guideline
- TARGET: 120-170 characters. ACCEPTABLE: 100-200 characters.
- Longer bullets that preserve all details are ALWAYS better than shorter bullets that lost information.
- NEVER sacrifice a technology name, metric, achievement, or scope to shorten a bullet.
- Cut filler words first ("utilized"→"used", "in order to"→"to"), NEVER named technologies, numbers, or outcomes.

## coaching_note
Write one short, honest sentence for the user reviewing your suggestions.
- Strong match: confirm it and say what to preserve. e.g. "Strong match — keep the tech stack and metrics in every bullet."
- Partial match: say how to strengthen. e.g. "Partial match — lean into the ML angle to align with the JD."
- Weak match: be honest. e.g. "Gap area — JD wants production systems experience; highlight any deployed work."
- Max 100 characters. No filler. Write directly to the user.

## Examples: Paraphrasing vs. Real Tailoring
### Example 1 — JD emphasizes "machine learning" and "production systems"
Original: "Built a sentiment analysis tool using BERT and Flask, processing 5K reviews"
BAD (paraphrasing): "Developed a sentiment analysis application utilizing BERT and Flask for 5K reviews" ← synonym swap, no JD alignment
GOOD (tailoring): "Built production sentiment analysis pipeline using BERT and Flask, processing 5K reviews for ML-driven insights" ← leads with "production" (JD theme), adds "ML-driven" context

### Example 2 — Bullet already matches JD well
Original: "Led a team of 4 to build a real-time dashboard using React and D3.js, winning 2nd place"
GOOD: Return VERBATIM — already has leadership, tech stack, and quantified outcome.

## Output Rules
- CRITICAL: If a bullet already matches the JD well, return it EXACTLY as-is. Do NOT make cosmetic changes.
- For each change, document what you changed and why in changes_made.

{domain_section}

{rules_section}
"""


async def tailor_projects(
    projects: list[dict],
    jd_parsed: dict,
    rules_text: str = "",
) -> list[TailoredProject]:
    """Tailor selected projects/leadership to match the JD using GPT-4o.

    Args:
        projects: List of dicts with keys: id, name, description, bullets.
        jd_parsed: Parsed JD dict.
        rules_text: Pre-formatted tailoring rules string.
    """
    if not projects:
        return []

    domain_section = _get_domain_guidance(jd_parsed.get("domain", ""))
    system_prompt = PROJECT_SYSTEM_PROMPT.format(
        domain_section=domain_section,
        rules_section=rules_text,
    )

    # Build project descriptions
    proj_descriptions = []
    for proj in projects:
        bullets = extract_bullet_texts(proj.get("bullets", []))
        # If no structured bullets, split description into sentences as bullets
        if not bullets:
            bullets = split_description_to_bullets(proj.get("description") or "")
        if not bullets:
            continue

        proj_descriptions.append({
            "project_id": str(proj["id"]),
            "name": proj.get("name") or "Unknown",
            "description": proj.get("description") or "",
            "bullets": bullets,
        })

    if not proj_descriptions:
        return []

    jd_summary = _build_jd_summary(jd_parsed)

    user_message = f"""Target Job Description:
{jd_summary}

Projects/Leadership to tailor:
"""
    for pd in proj_descriptions:
        user_message += f"\n--- Project: {pd['name']} (ID: {pd['project_id']}) ---\n"
        if pd["description"]:
            user_message += f"  Description: {pd['description']}\n"
        briefs = _build_bullet_briefs(pd["bullets"], None, jd_parsed)
        for i, (bullet, brief) in enumerate(zip(pd["bullets"], briefs)):
            user_message += f"  {i+1}. {bullet}\n{brief}\n"

    user_message += """
For each bullet, follow this process:
1. Read the tailoring brief above the bullet — it tells you which JD themes to surface.
2. Decide the lead theme: which JD priority should this bullet open with?
3. Reframe the bullet to lead with that theme, keeping ALL existing tech details and metrics.
4. If the bullet already leads with the right theme and matches the JD well, return it VERBATIM — do NOT make cosmetic synonym swaps.
5. A good tailoring change reframes emphasis and adds JD-relevant context. A bad change just swaps synonyms.

Return all projects."""

    _client = get_openai_client()
    _settings = get_settings()
    response = await _client.beta.chat.completions.parse(
        model=_settings.model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format=TailorProjectsOutput,
        temperature=_settings.temp_tailoring,
    )

    tailored = response.choices[0].message.parsed.tailored_projects

    # Enforce 1-to-1: if bullet count drifts, fall back to originals for that project
    for tp in tailored:
        if len(tp.suggested_bullets) != len(tp.original_bullets):
            tp.suggested_bullets = [
                TailoredBullet(text=b, has_placeholder=False, outcome_type="process")
                for b in tp.original_bullets
            ]

    # Post-process: revert trivial changes
    for tp in tailored:
        for i, (orig, suggested) in enumerate(
            zip(tp.original_bullets, tp.suggested_bullets)
        ):
            orig_norm = orig.lower().strip().rstrip(".")
            sugg_norm = suggested.text.lower().strip().rstrip(".")
            if orig_norm == sugg_norm or _similarity(orig_norm, sugg_norm) > 0.95:
                tp.suggested_bullets[i] = TailoredBullet(
                    text=orig, has_placeholder=False, outcome_type=suggested.outcome_type,
                )
            elif _has_hallucinated_numbers(orig, suggested.text):
                tp.suggested_bullets[i] = TailoredBullet(
                    text=orig, has_placeholder=False, outcome_type=suggested.outcome_type,
                )
            elif _BANNED_PHRASE_RE.search(suggested.text):
                tp.suggested_bullets[i] = TailoredBullet(
                    text=orig, has_placeholder=False, outcome_type=suggested.outcome_type,
                )

    # Enforce length by trimming just-over-line / expanding short / trimming long bullets
    await _apply_length_refinements(tailored, jd_summary, trim_low=105, trim_high=145)

    _clean_changes_made(tailored)

    return tailored


class TailoredActivity(BaseModel):
    activity_id: str
    original_bullets: list[str]
    suggested_bullets: list[TailoredBullet]
    changes_made: list[str]
    confidence: float = Field(ge=0, le=1)
    requirements_addressed: list[str] = Field(
        default_factory=list,
        description="Which JD requirements this activity now addresses",
    )


class TailorActivitiesOutput(BaseModel):
    tailored_activities: list[TailoredActivity]


async def tailor_activities(
    activities: list[dict],
    jd_parsed: dict,
    rules_text: str = "",
) -> list[TailoredActivity]:
    """Tailor selected activities (leadership/extracurricular) to match the JD using GPT-4o.

    Args:
        activities: List of dicts with keys: id, organization, role_title, bullets.
        jd_parsed: Parsed JD dict.
        rules_text: Pre-formatted tailoring rules string.
    """
    if not activities:
        return []

    domain_section = _get_domain_guidance(jd_parsed.get("domain", ""))
    system_prompt = PROJECT_SYSTEM_PROMPT.format(
        domain_section=domain_section,
        rules_section=rules_text,
    )

    # Build activity descriptions
    act_descriptions = []
    for act in activities:
        bullets = extract_bullet_texts(act.get("bullets", []))
        if not bullets:
            continue

        act_descriptions.append({
            "activity_id": str(act["id"]),
            "organization": act.get("organization") or "Unknown",
            "role_title": act.get("role_title") or "",
            "bullets": bullets,
        })

    if not act_descriptions:
        return []

    jd_summary = _build_jd_summary(jd_parsed)

    user_message = f"""Target Job Description:
{jd_summary}

Activities/Leadership to tailor:
"""
    for ad in act_descriptions:
        user_message += f"\n--- {ad['role_title']} at {ad['organization']} (ID: {ad['activity_id']}) ---\n"
        briefs = _build_bullet_briefs(ad["bullets"], None, jd_parsed)
        for i, (bullet, brief) in enumerate(zip(ad["bullets"], briefs)):
            user_message += f"  {i+1}. {bullet}\n{brief}\n"

    user_message += """
For each bullet, follow this process:
1. Read the tailoring brief above the bullet — it tells you which JD themes to surface.
2. Decide the lead theme: which JD priority should this bullet open with?
3. Reframe the bullet to lead with that theme, keeping ALL existing tech details and metrics.
4. If the bullet already leads with the right theme and matches the JD well, return it VERBATIM — do NOT make cosmetic synonym swaps.
5. A good tailoring change reframes emphasis and adds JD-relevant context. A bad change just swaps synonyms.

Return all activities."""

    _client = get_openai_client()
    _settings = get_settings()
    response = await _client.beta.chat.completions.parse(
        model=_settings.model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format=TailorActivitiesOutput,
        temperature=_settings.temp_tailoring,
    )

    tailored = response.choices[0].message.parsed.tailored_activities

    # Post-process: revert trivial changes
    for ta in tailored:
        for i, (orig, suggested) in enumerate(
            zip(ta.original_bullets, ta.suggested_bullets)
        ):
            orig_norm = orig.lower().strip().rstrip(".")
            sugg_norm = suggested.text.lower().strip().rstrip(".")
            if orig_norm == sugg_norm or _similarity(orig_norm, sugg_norm) > 0.95:
                ta.suggested_bullets[i] = TailoredBullet(
                    text=orig, has_placeholder=False, outcome_type=suggested.outcome_type,
                )
            elif _has_hallucinated_numbers(orig, suggested.text):
                ta.suggested_bullets[i] = TailoredBullet(
                    text=orig, has_placeholder=False, outcome_type=suggested.outcome_type,
                )
            elif _BANNED_PHRASE_RE.search(suggested.text):
                ta.suggested_bullets[i] = TailoredBullet(
                    text=orig, has_placeholder=False, outcome_type=suggested.outcome_type,
                )

    # Enforce length by trimming just-over-line / expanding short / trimming long bullets
    await _apply_length_refinements(tailored, jd_summary, trim_low=95, trim_high=135)

    _clean_changes_made(tailored)

    return tailored


_ORDINAL_WORDS = {0: "first", 1: "second", 2: "third", 3: "fourth", 4: "fifth", 5: "sixth"}


def _clean_changes_made(entries: list) -> None:
    """After reverting trivial changes, update changes_made to match reality.

    Removes misleading change descriptions for bullets that were reverted to verbatim,
    and adds accurate notes instead.
    """
    for entry in entries:
        unchanged_indices: list[int] = []
        for i, (orig, suggested) in enumerate(
            zip(entry.original_bullets, entry.suggested_bullets)
        ):
            if orig.strip() == suggested.text.strip():
                unchanged_indices.append(i)

        if not unchanged_indices:
            continue

        if len(unchanged_indices) == len(entry.original_bullets):
            entry.changes_made = [
                "All bullets returned verbatim as they already match the JD well."
            ]
            continue

        # Filter out misleading entries that reference reverted bullets
        filtered: list[str] = []
        for change in entry.changes_made:
            change_lower = change.lower()
            is_about_reverted = False
            for idx in unchanged_indices:
                ordinal = _ORDINAL_WORDS.get(idx, f"{idx + 1}th")
                if ordinal in change_lower or f"bullet {idx + 1}" in change_lower:
                    is_about_reverted = True
                    break
            if not is_about_reverted:
                filtered.append(change)

        for idx in unchanged_indices:
            ordinal = _ORDINAL_WORDS.get(idx, f"{idx + 1}th")
            filtered.append(
                f"The {ordinal} bullet was returned verbatim as it already matches the JD well."
            )

        entry.changes_made = filtered


def _similarity(a: str, b: str) -> float:
    """Similarity ratio (0-1) using SequenceMatcher for accurate comparison."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()
