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
    r"\b(?:"
    r"showcasing|showcases"
    r"|demonstrating\s+(?:strong\s+)?(?:\w+\s+){0,3}(?:skills?|abilities?|expertise|proficiency|understanding|knowledge|capabilities?)"
    r"|highlighting\s+(?:\w+\s+){0,3}(?:skills?|abilities?|expertise|proficiency)"
    r"|leveraging expertise"
    r"|leveraging\s+(?:strong\s+)?(?:\w+\s+){0,2}(?:skills?|abilities?|expertise)"
    r"|advancing\s+\w+(?:\s+\w+)?\s+techniques?"
    r"|exceptional\s+\w+(?:\s+\w+)?\s+(?:skills?|abilities?|qualities)"
    r"|strong\s+\w+(?:\s+\w+)?\s+(?:skills?|abilities?)\s*[,.]?\s*$"
    r")",
    re.IGNORECASE,
)

# Matches CamelCase tokens, pure acronyms, and letter+digit combos (e.g. EC2, S3).
# Used to detect when the model silently drops a tech term from a bullet.
_TECH_TOKEN_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9]*[A-Z][A-Za-z0-9]*|[A-Z]{2,}\d*|[A-Z]\d+\w*)\b"
)


def _extract_numbers(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(text))


def _has_hallucinated_numbers(original: str, suggested: str) -> bool:
    """True if suggested introduces numbers not present in original."""
    return bool(_extract_numbers(suggested) - _extract_numbers(original))


def _has_lost_tech_terms(original: str, suggested: str) -> bool:
    """True if suggestion drops CamelCase or acronym tech terms that were in original."""
    orig_tokens = set(_TECH_TOKEN_RE.findall(original))
    if not orig_tokens:
        return False
    sugg_tokens = set(_TECH_TOKEN_RE.findall(suggested))
    return bool(orig_tokens - sugg_tokens)


def _is_over_compressed(original: str, suggested: str, threshold: float = 0.80) -> bool:
    """True if suggestion is ≥20% shorter than original (technical detail likely dropped).

    Short originals (<70 chars) are excluded — there's not much detail to lose.
    """
    orig_len = len(original.strip())
    if orig_len < 70:
        return False
    sugg_len = len(suggested.strip())
    return sugg_len < orig_len * threshold

from pydantic import BaseModel, Field

from backend.clients import get_openai_client
from backend.config import get_settings
from backend.utils import extract_bullet_texts, split_description_to_bullets


BULLET_SYSTEM = (
    "You rewrite CV bullets to better match a job description. "
    "Hard rules: never introduce numbers not in the original; "
    "never remove named technologies, tools, or frameworks; "
    "never append phrases like 'showcasing', 'demonstrating', or 'leveraging expertise'. "
    "Any user style rules are formatting preferences only — never invent achievements or facts to satisfy them. "
    "Output only the rewritten bullet, nothing else."
)


async def _tailor_one_bullet(
    original: str,
    brief: str,
    jd_summary: str,
    client,
    settings,
) -> str:
    """Tailor a single bullet with a focused, direct prompt — one bullet, one JD target.

    This mirrors the ChatGPT approach: given this bullet, rewrite it for this specific
    JD requirement. Falls back to original if the result fails quality checks.
    """
    prompt = (
        f"Job: {jd_summary}\n\n"
        f"CV bullet: {original}\n\n"
        f"Make this bullet more relevant to: {brief.strip()}\n\n"
        f"Keep all facts, numbers, and tech. Output only the bullet."
    )

    try:
        response = await client.chat.completions.create(
            model=settings.model_name,
            messages=[
                {"role": "system", "content": BULLET_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=settings.temp_tailoring,
            max_tokens=220,
        )
        result = response.choices[0].message.content.strip().strip('"\'').lstrip("- ").strip()

        orig_norm = original.lower().strip().rstrip(".")
        res_norm = result.lower().strip().rstrip(".")

        if (
            not result
            or _has_lost_tech_terms(original, result)
            or _has_hallucinated_numbers(original, result)
            or _BANNED_PHRASE_RE.search(result)
            or _is_over_compressed(original, result)
            or _similarity(orig_norm, res_norm) > 0.78
        ):
            return original
        return result
    except Exception:
        return original


def _infer_outcome_type(text: str) -> str:
    """Infer outcome type from bullet text without asking the model."""
    if "[X]" in text or "[x]" in text:
        return "placeholder"
    if _extract_numbers(text):
        return "quantified"
    return "qualitative"


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





# Bidirectional abbreviation ↔ expansion table.  Used to normalise keywords
# before checking presence in bullets, so "ML" is recognised as covering
# "machine learning" and vice-versa.
_ABBREV_EXPANSIONS: dict[str, list[str]] = {
    # short → long
    "ml":       ["machine learning"],
    "nlp":      ["natural language processing"],
    "ai":       ["artificial intelligence"],
    "dl":       ["deep learning"],
    "llm":      ["large language model"],
    "llms":     ["large language model", "large language models"],
    "rag":      ["retrieval augmented generation", "retrieval-augmented generation"],
    "k8s":      ["kubernetes"],
    "cv":       ["computer vision"],
    "ci/cd":    ["continuous integration", "continuous deployment"],
    "cicd":     ["continuous integration", "continuous deployment"],
    "oop":      ["object-oriented programming", "object oriented programming"],
    "apis":     ["api"],
    "etl":      ["extract transform load"],
    "bi":       ["business intelligence"],
    "saas":     ["software as a service"],
    # long → short
    "machine learning":                ["ml"],
    "natural language processing":     ["nlp"],
    "artificial intelligence":         ["ai"],
    "deep learning":                   ["dl"],
    "large language model":            ["llm"],
    "large language models":           ["llm", "llms"],
    "kubernetes":                      ["k8s"],
    "computer vision":                 ["cv"],
    "continuous integration":          ["ci/cd", "cicd"],
    "continuous deployment":           ["ci/cd", "cicd"],
    "business intelligence":           ["bi"],
    "software as a service":           ["saas"],
}


def _keyword_in_text(keyword: str, text: str) -> bool:
    """Return True if keyword (or a known abbreviation/expansion) appears in text.

    Handles:
    - case insensitivity
    - naive plurals (strips trailing 's')
    - bidirectional abbreviation lookup (ML ↔ machine learning)
    """
    kw = keyword.lower().strip()
    text_l = text.lower()

    if kw in text_l:
        return True
    # Naive plural: "APIs" → check "api"
    if kw.endswith("s") and kw[:-1] in text_l:
        return True

    for variant in _ABBREV_EXPANSIONS.get(kw, []):
        if variant in text_l:
            return True
    return False


def _score_keyword_fit(keyword: str, bullet: str) -> int:
    """Score how naturally a keyword fits a bullet (higher = better fit).

    Expands abbreviations to canonical forms before computing word overlap so
    that "ML models" and "machine learning models" score identically.
    """
    def _expand(text: str) -> str:
        t = text.lower()
        for abbrev, expansions in sorted(_ABBREV_EXPANSIONS.items(), key=lambda x: -len(x[0])):
            if expansions and f" {abbrev} " in f" {t} ":
                t = t.replace(abbrev, expansions[0])
        return t

    kw_words = set(_expand(keyword).split())
    bullet_words = set(_expand(bullet).split())
    return len(kw_words & bullet_words)


def _reorder_bullets_by_relevance(
    tailored_list: list,
    priority_keywords: list[str],
) -> None:
    """Sort bullet pairs within each entry by JD keyword match score (descending).

    Keeps original_bullets and suggested_bullets in sync so pairs stay intact.
    The most JD-relevant bullet moves to position 0, which is what ATS parsers
    and recruiters read first.
    """
    for entry in tailored_list:
        if len(entry.suggested_bullets) <= 1:
            continue
        scores = [
            sum(1 for kw in priority_keywords if _keyword_in_text(kw, sug.text))
            for sug in entry.suggested_bullets
        ]
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        entry.original_bullets = [entry.original_bullets[i] for i in order]
        entry.suggested_bullets = [entry.suggested_bullets[i] for i in order]


def _assign_keywords_to_bullets(
    bullets: list[str],
    priority_keywords: list[str],
    max_bullets_per_kw: int = 2,
) -> dict[int, list[str]]:
    """Assign each missing keyword to the top-N best-fitting bullets.

    A keyword can appear in up to `max_bullets_per_kw` bullets (those with the
    highest word-overlap fit), preventing both keyword stuffing (broadcasting
    to every bullet) and over-restriction (only 1 bullet allowed).
    """
    assignment: dict[int, list[str]] = {i: [] for i in range(len(bullets))}
    for kw in priority_keywords:
        # Skip if already present (or equivalent abbreviation) in any bullet
        if any(_keyword_in_text(kw, b) for b in bullets):
            continue
        # Rank bullets by word-overlap fit; assign to top N
        scores = [_score_keyword_fit(kw, b) for b in bullets]
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        for idx in ranked[:max_bullets_per_kw]:
            assignment[idx].append(kw)
    return assignment


_WEAK_STARTS = (
    "responsible for", "worked on", "assisted with", "assisted in",
    "helped with", "helped to", "participated in", "involved in",
    "contributed to", "supported the", "was part of", "tasked with",
    "duties included", "role involved",
)

_WEAK_VERBS = {"assist", "help", "support", "participate", "contribute", "involve"}


def _bullet_weakness(bullet: str) -> str | None:
    """Return a one-line weakness description, or None if the bullet is OK."""
    b = bullet.lower().strip()
    if len(bullet.strip()) < 60:
        return "too short / vague"
    if any(b.startswith(w) for w in _WEAK_STARTS):
        first = b.split()[0]
        return f"opens with passive/weak phrase ('{first}...')"
    first_word = b.split()[0].rstrip("eding")  # rough stem
    if first_word in _WEAK_VERBS:
        return f"weak opening verb ('{b.split()[0]}')"
    return None


def _find_redundant_pairs(bullets: list[str]) -> dict[int, int]:
    """Return {idx: duplicate_of_idx} for bullets that heavily overlap a preceding one."""
    redundant: dict[int, int] = {}
    for i in range(1, len(bullets)):
        for j in range(i):
            if j in redundant:
                continue  # don't chain off already-redundant bullets
            if _similarity(bullets[i].lower(), bullets[j].lower()) > 0.52:
                redundant[i] = j
                break
    return redundant


def _build_bullet_briefs(
    bullets: list[str],
    gap_analysis: dict | None,
    jd_parsed: dict,
    rules_text: str = "",
) -> list[str]:
    """For each bullet, build a short tailoring brief: which JD themes to surface.

    Detects weak bullets and redundant pairs so the model gets explicit strategic
    direction rather than a gentle nudge — weak/redundant bullets get a full rewrite
    mandate, not just a reframe instruction.
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

    # Pre-assign missing keywords to best-fit bullets
    keyword_assignment = _assign_keywords_to_bullets(bullets, priority_keywords[:12])

    # Detect quality issues up front so briefs can reflect them
    weakness_map = {i: _bullet_weakness(b) for i, b in enumerate(bullets)}
    redundant_map = _find_redundant_pairs(bullets)

    briefs = []
    for idx, bullet in enumerate(bullets):
        weakness = weakness_map.get(idx)
        redundant_of = redundant_map.get(idx)

        # Prefix for weak/redundant bullets — escalates the rewrite mandate
        prefix = ""
        if weakness:
            prefix = (
                f"  ⚠ WEAK BULLET ({weakness}). REWRITE FROM SCRATCH — "
                f"treat the original as raw notes, not a template. "
                f"Write a strong, achievement-oriented bullet that leads with what the JD values.\n"
            )
        if redundant_of is not None:
            prefix = (
                f"  ⚠ REDUNDANT with bullet #{redundant_of + 1} above (covers the same ground). "
                f"REWRITE to cover a completely different JD requirement — "
                f"do NOT repeat the same theme or skill.\n"
            )

        # Keywords covered by SIBLING bullets only — avoid repeating them
        sibling_covered = [
            kw for kw in priority_keywords
            if not _keyword_in_text(kw, bullet)
            and any(_keyword_in_text(kw, b) for j, b in enumerate(bullets) if j != idx)
        ][:4]
        sibling_note = (
            f" (Sibling bullets already cover: {', '.join(sibling_covered)} — don't repeat.)"
            if sibling_covered else ""
        )

        # Use gap analysis framings if available (highest quality)
        if bullet in bullet_to_framings:
            themes = bullet_to_framings[bullet]
            action = "REWRITE to naturally lead with" if weakness else "Reframe to surface"
            briefs.append(
                f"{prefix}  → Tailoring brief: {action} these JD themes: {'; '.join(themes)}."
                f" Embed the theme into the action — do NOT append it as a trailing phrase.{sibling_note}"
            )
        else:
            assigned_missing = keyword_assignment.get(idx, [])
            present_keywords = [
                kw for kw in priority_keywords if _keyword_in_text(kw, bullet)
            ][:2]
            if assigned_missing:
                present_note = (
                    f" (Keep present: {', '.join(present_keywords)}.)" if present_keywords else ""
                )
                action = "REWRITE from scratch so the bullet naturally centres on" if weakness else "RESTRUCTURE to lead with"
                briefs.append(
                    f"{prefix}  → Tailoring brief: {action}: {', '.join(assigned_missing)}."
                    f" This must be woven into the action itself — not added as a suffix.{present_note}{sibling_note}"
                )
            elif present_keywords:
                action = "REWRITE so" if weakness else "REFRAME so"
                briefs.append(
                    f"{prefix}  → Tailoring brief: {action} '{present_keywords[0]}' leads the sentence — "
                    f"it should be the first concept the reader sees.{sibling_note}"
                )
            else:
                if weakness:
                    briefs.append(
                        f"{prefix}  → Tailoring brief: Rewrite as a strong achievement bullet. "
                        f"Identify the closest JD theme and lead with it.{sibling_note}"
                    )
                else:
                    briefs.append(
                        f"  → Tailoring brief: Identify the closest JD Key Responsibility theme and reframe the opening to surface it.{sibling_note} "
                        f"Only leave unchanged if genuinely unrelated to every JD theme."
                    )
    if rules_text.strip():
        rules_section = f"\n\nUser rules to follow:\n{rules_text.strip()}"
        briefs = [b + rules_section for b in briefs]

    return briefs


async def _tailor_experience_bullets(
    exp: dict,
    jd_summary: str,
    gap_analysis: dict | None,
    jd_parsed: dict,
    client,
    settings,
    rules_text: str = "",
) -> TailoredExperience:
    """Tailor each bullet with its own focused call — one bullet, one JD target."""
    bullets = extract_bullet_texts(exp.get("bullets", []))
    exp_id = str(exp["id"])

    if not bullets:
        return TailoredExperience(
            experience_id=exp_id, original_bullets=[],
            suggested_bullets=[], changes_made=[], confidence=0.5,
        )

    briefs = _build_bullet_briefs(bullets, gap_analysis, jd_parsed, rules_text)

    rewritten = list(await asyncio.gather(*[
        _tailor_one_bullet(bullet, brief, jd_summary, client, settings)
        for bullet, brief in zip(bullets, briefs)
    ]))

    suggested = [
        TailoredBullet(
            text=text,
            has_placeholder="[X]" in text or "[x]" in text,
            outcome_type=_infer_outcome_type(text),
        )
        for text in rewritten
    ]
    changed = sum(1 for o, s in zip(bullets, suggested) if o != s.text)
    confidence = round(changed / len(bullets), 2) if bullets else 0.5

    return TailoredExperience(
        experience_id=exp_id,
        original_bullets=bullets,
        suggested_bullets=suggested,
        changes_made=[],
        confidence=confidence,
    )


async def tailor_experiences(
    experiences: list[dict],
    jd_parsed: dict,
    gap_analysis: dict | None = None,
    rules_text: str = "",
) -> list[TailoredExperience]:
    """Tailor experiences — one focused API call per bullet, all in parallel."""
    jd_summary = _build_jd_summary(jd_parsed)
    _client = get_openai_client()
    _settings = get_settings()

    tailored = list(await asyncio.gather(*[
        _tailor_experience_bullets(exp, jd_summary, gap_analysis, jd_parsed, _client, _settings, rules_text)
        for exp in experiences
    ]))

    await _apply_length_refinements(tailored, jd_summary, trim_low=95, trim_high=135)

    priority_keywords = jd_parsed.get("required_skills", []) + jd_parsed.get("keywords", [])
    _reorder_bullets_by_relevance(tailored, priority_keywords)

    return tailored




async def _tailor_project_bullets(
    proj: dict,
    jd_summary: str,
    jd_parsed: dict,
    client,
    settings,
    rules_text: str = "",
    gap_analysis: dict | None = None,
) -> TailoredProject | None:
    bullets = extract_bullet_texts(proj.get("bullets", []))
    if not bullets:
        bullets = split_description_to_bullets(proj.get("description") or "")
    if not bullets:
        return None

    proj_id = str(proj["id"])
    briefs = _build_bullet_briefs(bullets, gap_analysis, jd_parsed, rules_text)

    rewritten = list(await asyncio.gather(*[
        _tailor_one_bullet(bullet, brief, jd_summary, client, settings)
        for bullet, brief in zip(bullets, briefs)
    ]))

    suggested = [
        TailoredBullet(text=t, has_placeholder="[X]" in t or "[x]" in t, outcome_type=_infer_outcome_type(t))
        for t in rewritten
    ]
    changed = sum(1 for o, s in zip(bullets, suggested) if o != s.text)
    return TailoredProject(
        project_id=proj_id, original_bullets=bullets, suggested_bullets=suggested,
        changes_made=[], confidence=round(changed / len(bullets), 2) if bullets else 0.5,
    )


async def tailor_projects(
    projects: list[dict],
    jd_parsed: dict,
    rules_text: str = "",
    gap_analysis: dict | None = None,
) -> list[TailoredProject]:
    if not projects:
        return []

    jd_summary = _build_jd_summary(jd_parsed)
    _client = get_openai_client()
    _settings = get_settings()

    results = await asyncio.gather(*[
        _tailor_project_bullets(proj, jd_summary, jd_parsed, _client, _settings, rules_text, gap_analysis)
        for proj in projects
    ])
    tailored = [r for r in results if r is not None]

    if not tailored:
        return []

    await _apply_length_refinements(tailored, jd_summary, trim_low=105, trim_high=145)
    priority_keywords = jd_parsed.get("required_skills", []) + jd_parsed.get("keywords", [])
    _reorder_bullets_by_relevance(tailored, priority_keywords)
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


async def _tailor_activity_bullets(
    act: dict,
    jd_summary: str,
    jd_parsed: dict,
    client,
    settings,
    rules_text: str = "",
    gap_analysis: dict | None = None,
) -> TailoredActivity | None:
    bullets = extract_bullet_texts(act.get("bullets", []))
    if not bullets:
        return None

    act_id = str(act["id"])
    briefs = _build_bullet_briefs(bullets, gap_analysis, jd_parsed, rules_text)

    rewritten = list(await asyncio.gather(*[
        _tailor_one_bullet(bullet, brief, jd_summary, client, settings)
        for bullet, brief in zip(bullets, briefs)
    ]))

    suggested = [
        TailoredBullet(text=t, has_placeholder="[X]" in t or "[x]" in t, outcome_type=_infer_outcome_type(t))
        for t in rewritten
    ]
    changed = sum(1 for o, s in zip(bullets, suggested) if o != s.text)
    return TailoredActivity(
        activity_id=act_id, original_bullets=bullets, suggested_bullets=suggested,
        changes_made=[], confidence=round(changed / len(bullets), 2) if bullets else 0.5,
    )


async def tailor_activities(
    activities: list[dict],
    jd_parsed: dict,
    rules_text: str = "",
    gap_analysis: dict | None = None,
) -> list[TailoredActivity]:
    if not activities:
        return []

    jd_summary = _build_jd_summary(jd_parsed)
    _client = get_openai_client()
    _settings = get_settings()

    results = await asyncio.gather(*[
        _tailor_activity_bullets(act, jd_summary, jd_parsed, _client, _settings, rules_text, gap_analysis)
        for act in activities
    ])
    tailored = [r for r in results if r is not None]

    if not tailored:
        return []

    await _apply_length_refinements(tailored, jd_summary, trim_low=95, trim_high=135)
    priority_keywords = jd_parsed.get("required_skills", []) + jd_parsed.get("keywords", [])
    _reorder_bullets_by_relevance(tailored, priority_keywords)
    return tailored




def _similarity(a: str, b: str) -> float:
    """Similarity ratio (0-1) using SequenceMatcher for accurate comparison."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()
