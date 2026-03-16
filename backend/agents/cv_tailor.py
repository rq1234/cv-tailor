"""Agent: Tailor selected experiences to the job description."""

from __future__ import annotations

import asyncio
import re
from difflib import SequenceMatcher
from typing import NamedTuple

_NUMBER_RE = re.compile(
    r"\b\d[\d,]*(?:\.\d+)?(?:\+|[kKMB]|%|x)?\b"  # 10,000+ / 25% / 8x / $800K
    r"|\btop\s+\d+\b"                               # top 5
    r"|\b\d+\s+of\s+\d+\b",                         # 1 of 80
    re.IGNORECASE,
)

def _extract_numbers(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(text))


def _has_hallucinated_numbers(original: str, suggested: str) -> bool:
    """True if suggested introduces numbers not present in original."""
    return bool(_extract_numbers(suggested) - _extract_numbers(original))


from pydantic import BaseModel, Field

from backend.agents.domain_guidance import _get_domain_guidance
from backend.clients import get_openai_client
from backend.config import get_settings
from backend.utils import extract_bullet_texts, split_description_to_bullets


BULLET_SYSTEM = (
    "You are a CV editor. Rewrite the given bullet to better target the specified job requirement.\n\n"
    "Format: [Strong action verb] [what you did/built] [tools or context] [measurable result]. "
    "Stop at the result. One concise line.\n\n"
    "Examples:\n"
    "  BAD:  'Worked on data pipelines leveraging strong Python skills to support business objectives'\n"
    "  GOOD: 'Built Python ETL pipeline ingesting 50 GB daily, reducing reporting latency by 40%'\n\n"
    "  BAD:  'Led cross-functional projects showcasing leadership and technical expertise'\n"
    "  GOOD: 'Led 5-person team delivering 3 product releases on schedule'\n\n"
    "Rules:\n"
    "- Never introduce numbers not in the original\n"
    "- Never remove named technologies, tools, or frameworks\n"
    "- Never end with meta-commentary: no 'showcasing', 'demonstrating', 'highlighting', 'leveraging expertise', "
    "'to support objectives', 'aligning with', 'akin to'\n"
    "- Never invent achievements or facts\n"
    "- If a bullet has an outcome but no number, add a [X%] or [X] placeholder where the metric would go — the user will fill it in\n"
    "- Output only the rewritten bullet, nothing else"
)


class BulletBrief(NamedTuple):
    """Structured brief passed to the LLM for a single bullet rewrite."""
    requirement: str   # the specific JD requirement this bullet should target
    approach: str      # what to change and why, in natural editor voice
    keep_original: bool = False  # Tier 1 — no JD relevance, return unchanged
    exp_context: str = ""  # e.g. "Software Engineer at Google" — shown to LLM for context


async def _tailor_one_bullet(
    original: str,
    brief: BulletBrief,
    role_context: str,
    client,
    settings,
    priority_keywords: list[str] | None = None,
    domain_guidance: str = "",
    seniority_note: str = "",
) -> str:
    """Tailor a single bullet — one specific JD requirement, one bullet, one API call.

    Generates 2 candidates per attempt and picks the one with better JD keyword
    prominence in the first 6 words (first-6-words scoring). Falls back to original
    if all candidates fail quality checks after 3 attempts.
    """
    if brief.keep_original:
        return original

    # Build system prompt: base rules + seniority hint + domain norms
    system_parts = [BULLET_SYSTEM]
    if seniority_note:
        system_parts.append(f"\n{seniority_note}")
    if domain_guidance:
        system_parts.append(f"\n{domain_guidance}")
    system = "\n".join(system_parts)

    # Build user prompt — include experience context if available
    bullet_label = (
        f"Candidate's bullet (from: {brief.exp_context}):\n{original}"
        if brief.exp_context
        else f"Candidate's bullet:\n{original}"
    )
    prompt = (
        f"Role: {role_context}\n\n"
        f"Job requirement to target:\n{brief.requirement}\n\n"
        f"{bullet_label}\n\n"
        f"{brief.approach}"
    )

    kws = priority_keywords or []

    try:
        response = await client.chat.completions.create(
            model=settings.model_name,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            n=2,
            temperature=settings.temp_tailoring,
            max_tokens=220,
        )

        candidates = [
            (choice.message.content or "").strip().strip("\"'").lstrip("- ").strip()
            for choice in response.choices
        ]
        valid = [r for r in candidates if r and not _has_hallucinated_numbers(original, r)]
        if valid:
            return max(valid, key=lambda t: _score_bullet_candidate(t, kws))

    except Exception:
        pass

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
        # Rank bullets by word-overlap fit; only assign if there's actual overlap.
        # A fit score of 0 means no word in the keyword appears in the bullet — forcing
        # it in would fabricate domain context the user doesn't have.
        scores = [_score_keyword_fit(kw, b) for b in bullets]
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        for idx in ranked[:max_bullets_per_kw]:
            if scores[idx] >= 2:  # require ≥2 shared words to avoid false-positive injection
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


_APR_RESULT_PHRASES = (
    "reduc", "improv", "increas", "sav", "enabl", "result",
    "achiev", "deliv", "lead", "cut", "grew", "boost",
    "accelerat", "generat", "optim",
)

def _diagnose_apr(bullet: str) -> dict[str, bool]:
    """Check which APR components a bullet has: action verb, scope/what, result/impact."""
    b = bullet.strip()
    b_lower = b.lower()
    words = b_lower.split()
    if not words:
        return {"action_verb": False, "scope": False, "result": False}
    has_action_verb = (
        not any(b_lower.startswith(w) for w in _WEAK_STARTS)
        and words[0] not in _WEAK_VERBS
        and len(words[0]) > 3
    )
    has_scope = len(b) >= 70
    has_result = bool(_NUMBER_RE.search(b)) or any(phrase in b_lower for phrase in _APR_RESULT_PHRASES)
    return {"action_verb": has_action_verb, "scope": has_scope, "result": has_result}


def _get_seniority_note(seniority: str) -> str:
    """Return seniority-appropriate verb guidance for the tailoring system prompt."""
    s = seniority.lower()
    if s in ("director", "executive", "lead", "vp", "head"):
        return (
            "Seniority: Director/Lead — prefer strategic verbs: "
            "Architected, Led, Drove, Defined, Shaped, Spearheaded, Oversaw, Established."
        )
    if s == "senior":
        return (
            "Seniority: Senior — prefer ownership verbs: "
            "Designed, Owned, Championed, Delivered, Scaled, Directed, Orchestrated."
        )
    if s in ("internship", "entry", "junior", "graduate"):
        return (
            "Seniority: Entry/Intern — prefer hands-on verbs: "
            "Built, Implemented, Developed, Created, Wrote, Automated, Analysed, Deployed."
        )
    return ""  # mid-level — no specific verb guidance


def _score_bullet_candidate(text: str, priority_keywords: list[str]) -> float:
    """Score a bullet candidate — higher is better.

    Rewards JD keywords in first 6 words (recruiter eye-tracking research shows
    this is what gets read), keywords anywhere, quantified results, and good length.
    """
    if not text:
        return -1.0
    first_six = " ".join(text.split()[:6]).lower()
    text_lower = text.lower()
    first_six_score = sum(2.0 for kw in priority_keywords if _keyword_in_text(kw, first_six))
    rest_score = sum(
        0.5 for kw in priority_keywords
        if _keyword_in_text(kw, text_lower) and not _keyword_in_text(kw, first_six)
    )
    has_result = 1.0 if _NUMBER_RE.search(text) else 0.0
    has_placeholder = 0.5 if "[X]" in text or "[x]" in text else 0.0
    good_length = 1.0 if 80 <= len(text) <= 180 else 0.0
    return first_six_score + rest_score + has_result + has_placeholder + good_length


def _compute_experience_focus(
    experiences: list[dict],
    jd_parsed: dict,
) -> dict[str, list[str]]:
    """Assign JD key responsibilities to the experience best able to cover each.

    Returns {exp_id: [requirements this experience should focus on]}.
    Prevents all experiences from converging on the same top keywords.
    With a single experience, all requirements are returned (no-op).
    """
    key_resps = jd_parsed.get("key_responsibilities", [])
    if not key_resps or len(experiences) <= 1:
        return {str(exp["id"]): key_resps[:] for exp in experiences}

    # Score each experience against each requirement using bullet similarity
    exp_scores: dict[str, dict[str, float]] = {}
    for exp in experiences:
        bullets = extract_bullet_texts(exp.get("bullets", []))
        exp_id = str(exp["id"])
        exp_scores[exp_id] = {
            req: max(
                (_similarity(b.lower(), req.lower()) for b in bullets),
                default=0.0,
            )
            for req in key_resps
        }

    # Assign each requirement to the experience that best covers it
    ownership: dict[str, list[str]] = {str(exp["id"]): [] for exp in experiences}
    for req in key_resps:
        best_id = max(exp_scores, key=lambda eid: exp_scores[eid].get(req, 0.0))
        ownership[best_id].append(req)

    # Experiences with no assignments fall back to all requirements
    for exp_id, owned in ownership.items():
        if not owned:
            ownership[exp_id] = key_resps[:]

    return ownership


def _jd_relevance_score(bullet: str, jd_parsed: dict) -> float:
    """Score how relevant a bullet is to the JD (0–1, keyword overlap ratio).

    Uses required_skills + keywords as the pool.
    """
    pool = jd_parsed.get("required_skills", []) + jd_parsed.get("keywords", [])
    if not pool:
        return 0.5  # no keywords to judge against — assume neutral
    matched = sum(1 for kw in pool if _keyword_in_text(kw, bullet))
    return matched / len(pool)


def _best_req(jd_parsed: dict, bullet: str = "", focus: list[str] | None = None) -> str:
    """Return the single JD key responsibility most relevant to the bullet (or the first).

    If focus is provided, picks from that restricted list instead of all key_responsibilities.
    Used for tiers where a specific requirement must be named (Tier 1b, 2, 3).
    """
    key_resps = focus if focus else jd_parsed.get("key_responsibilities", [])
    if not key_resps:
        return jd_parsed.get("role_summary", "the role requirements")
    if not bullet:
        return key_resps[0]
    return max(key_resps, key=lambda r: _similarity(bullet.lower(), r.lower()))


def _req_list(jd_parsed: dict, focus: list[str] | None = None) -> str:
    """Format key responsibilities as a numbered list for the LLM to choose from.

    Used for Tier 4 and Tier 5 where the LLM should pick the most relevant
    requirement itself — more accurate than SequenceMatcher pre-selection.
    Falls back to role_summary if no responsibilities are available.
    """
    resps = focus if focus else jd_parsed.get("key_responsibilities", [])
    if not resps:
        return jd_parsed.get("role_summary", "the role requirements")
    return "\n".join(f"{i+1}. {r}" for i, r in enumerate(resps))


def _build_bullet_briefs(
    bullets: list[str],
    gap_analysis: dict | None,
    jd_parsed: dict,
    rules_text: str = "",
    focus_requirements: list[str] | None = None,
    exp_context: str = "",
) -> list[BulletBrief]:
    """For each bullet, build a structured BulletBrief (requirement + approach).

    Mirrors real ChatGPT tailoring workflow:
      1. Score = 0  → keep original (no honest reframe possible).
      2. Redundant  → rewrite to cover a different requirement.
      3. Weak       → rewrite, diagnose which APR component is missing.
      4. Gap match  → reframe using gap-analysis framing + evidence quote.
      5. Missing kw → restructure to naturally lead with the missing keyword.
      6. Present kw → light reframe so the right keyword opens the sentence.
    """
    priority_keywords = (
        jd_parsed.get("required_skills", []) + jd_parsed.get("keywords", [])
    )

    # Gap analysis: assign each mapping to its single best-matching bullet.
    # Store as (requirement, framing, evidence_quote) so evidence can anchor the rewrite.
    bullet_to_framings: dict[str, list[tuple[str, str, str]]] = {}
    if gap_analysis:
        for mapping in gap_analysis.get("mappings", []):
            evidence_lc = mapping.get("evidence", "").lower()
            evidence_quote = mapping.get("evidence", "")
            framing = mapping.get("suggested_framing", "")
            requirement = mapping.get("requirement", "")
            status = mapping.get("status", "")
            if status in ("strong_match", "partial_match") and evidence_lc:
                best_idx = max(
                    range(len(bullets)),
                    key=lambda i: _similarity(evidence_lc, bullets[i].lower()),
                )
                if _similarity(evidence_lc, bullets[best_idx].lower()) > 0.25:
                    b = bullets[best_idx]
                    bullet_to_framings.setdefault(b, [])
                    bullet_to_framings[b].append((requirement, framing, evidence_quote))

    keyword_assignment = _assign_keywords_to_bullets(bullets, priority_keywords[:12])
    weakness_map = {i: _bullet_weakness(b) for i, b in enumerate(bullets)}
    apr_map = {i: _diagnose_apr(b) for i, b in enumerate(bullets)}
    redundant_map = _find_redundant_pairs(bullets)

    rules_suffix = f"\n\nUser rules:\n{rules_text.strip()}" if rules_text.strip() else ""

    # When focus_requirements is provided, restrict _best_req to those requirements
    req_pool = focus_requirements if focus_requirements else None

    briefs: list[BulletBrief] = []
    for idx, bullet in enumerate(bullets):
        weakness = weakness_map.get(idx)
        apr = apr_map.get(idx, {})
        redundant_of = redundant_map.get(idx)

        sibling_covered = [
            kw for kw in priority_keywords
            if not _keyword_in_text(kw, bullet)
            and any(_keyword_in_text(kw, b) for j, b in enumerate(bullets) if j != idx)
        ][:4]
        sibling_note = (
            f" Siblings already cover: {', '.join(sibling_covered)} — choose a different angle."
            if sibling_covered else ""
        )

        # ── Tier 1b: Redundant ────────────────────────────────────────────────
        if redundant_of is not None:
            req = _best_req(jd_parsed, bullet, focus=req_pool)
            approach = (
                f"This bullet covers the same ground as bullet #{redundant_of + 1}. "
                f"Rewrite to address a completely different JD requirement.{sibling_note}"
                + rules_suffix
            )
            briefs.append(BulletBrief(requirement=req, approach=approach, exp_context=exp_context))

        # ── Tier 2: Weak structure ────────────────────────────────────────────
        elif weakness:
            req = _best_req(jd_parsed, bullet, focus=req_pool)
            # Diagnose which APR components are missing for precise instruction
            missing_apr = []
            if not apr.get("action_verb"):
                missing_apr.append("strong action verb")
            if not apr.get("scope"):
                missing_apr.append("what you did/built")
            if not apr.get("result"):
                missing_apr.append("outcome/result — add [X%] placeholder if metric unknown")
            apr_note = f" Missing: {', '.join(missing_apr)}." if missing_apr else ""

            missing_kws = [kw for kw in priority_keywords[:8] if not _keyword_in_text(kw, bullet)][:3]
            missing_kw_note = f" Weave in naturally: {', '.join(missing_kws)}." if missing_kws else ""
            approach = (
                f"This bullet has weak structure ({weakness}).{apr_note} "
                f"Rewrite from scratch — strong action verb, achievement-oriented.{missing_kw_note}{sibling_note}"
                + rules_suffix
            )
            briefs.append(BulletBrief(requirement=req, approach=approach, exp_context=exp_context))

        # ── Tier 3: Gap-analysis framing ─────────────────────────────────────
        elif bullet in bullet_to_framings:
            req, framing, evidence_quote = bullet_to_framings[bullet][0]
            evidence_note = (
                f"\nEvidence identified in your CV: \"{evidence_quote.strip()}\""
                if evidence_quote and 20 < len(evidence_quote) < 250
                else ""
            )
            approach = (
                (framing if framing else f"Reframe to surface: {req}.")
                + evidence_note
                + f"{sibling_note}" + rules_suffix
            )
            briefs.append(BulletBrief(requirement=req, approach=approach, exp_context=exp_context))

        # ── Tier 4: Keyword injection ─────────────────────────────────────────
        elif keyword_assignment.get(idx):
            assigned = keyword_assignment[idx]
            req = _req_list(jd_parsed, focus=req_pool)
            present = [kw for kw in priority_keywords if _keyword_in_text(kw, bullet)][:2]
            keep_note = f" Keep: {', '.join(present)}." if present else ""
            approach = (
                f"The bullet is missing: {', '.join(assigned)}. "
                f"Restructure so these appear naturally in the action or outcome.{keep_note} "
                f"Target whichever requirement above this bullet addresses most honestly.{sibling_note}"
                + rules_suffix
            )
            briefs.append(BulletBrief(requirement=req, approach=approach, exp_context=exp_context))

        # ── Tier 5: Strengthen for target role ────────────────────────────────
        else:
            req = _req_list(jd_parsed, focus=req_pool)
            approach = (
                f"Rewrite as a strong CV bullet targeting whichever requirement above this bullet "
                f"addresses most honestly. Structure: action verb → what you did → tools/context → result. "
                f"Make the impact concrete. Add [X%] placeholder if an outcome is implied but unquantified. "
                f"Do not invent technologies or achievements not in the original."
                f"{sibling_note}" + rules_suffix
            )
            briefs.append(BulletBrief(requirement=req, approach=approach, exp_context=exp_context))

    return briefs


async def _tailor_experience_bullets(
    exp: dict,
    role_context: str,
    gap_analysis: dict | None,
    jd_parsed: dict,
    client,
    settings,
    rules_text: str = "",
    focus_requirements: list[str] | None = None,
    domain_guidance: str = "",
    seniority_note: str = "",
) -> TailoredExperience:
    """Tailor each bullet with its own focused call — one bullet, one JD target."""
    bullets = extract_bullet_texts(exp.get("bullets", []))
    exp_id = str(exp["id"])
    # Build experience context string: "Software Engineer at Google"
    role = exp.get("role_title") or ""
    company = exp.get("company") or ""
    exp_context = f"{role} at {company}".strip(" at").strip() if role or company else ""

    if not bullets:
        return TailoredExperience(
            experience_id=exp_id, original_bullets=[],
            suggested_bullets=[], changes_made=[], confidence=0.5,
        )

    priority_keywords = jd_parsed.get("required_skills", []) + jd_parsed.get("keywords", [])
    briefs = _build_bullet_briefs(bullets, gap_analysis, jd_parsed, rules_text, focus_requirements, exp_context)

    rewritten = list(await asyncio.gather(*[
        _tailor_one_bullet(bullet, brief, role_context, client, settings, priority_keywords, domain_guidance, seniority_note)
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
    role_context = f"{jd_parsed.get('role_summary', 'N/A')} ({jd_parsed.get('domain', 'N/A')})"
    domain_guidance = _get_domain_guidance(jd_parsed.get("domain", ""))
    seniority_note = _get_seniority_note(jd_parsed.get("seniority_level", ""))
    coverage = _compute_experience_focus(experiences, jd_parsed)
    _client = get_openai_client()
    _settings = get_settings()

    return list(await asyncio.gather(*[
        _tailor_experience_bullets(
            exp, role_context, gap_analysis, jd_parsed, _client, _settings, rules_text,
            focus_requirements=coverage.get(str(exp["id"])),
            domain_guidance=domain_guidance,
            seniority_note=seniority_note,
        )
        for exp in experiences
    ]))




async def _tailor_project_bullets(
    proj: dict,
    role_context: str,
    jd_parsed: dict,
    client,
    settings,
    rules_text: str = "",
    gap_analysis: dict | None = None,
    domain_guidance: str = "",
    seniority_note: str = "",
) -> TailoredProject | None:
    bullets = extract_bullet_texts(proj.get("bullets", []))
    if not bullets:
        bullets = split_description_to_bullets(proj.get("description") or "")
    if not bullets:
        return None

    proj_id = str(proj["id"])
    proj_context = proj.get("name", "")
    priority_keywords = jd_parsed.get("required_skills", []) + jd_parsed.get("keywords", [])
    briefs = _build_bullet_briefs(bullets, gap_analysis, jd_parsed, rules_text, exp_context=proj_context)

    rewritten = list(await asyncio.gather(*[
        _tailor_one_bullet(bullet, brief, role_context, client, settings, priority_keywords, domain_guidance, seniority_note)
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

    role_context = f"{jd_parsed.get('role_summary', 'N/A')} ({jd_parsed.get('domain', 'N/A')})"
    domain_guidance = _get_domain_guidance(jd_parsed.get("domain", ""))
    seniority_note = _get_seniority_note(jd_parsed.get("seniority_level", ""))
    _client = get_openai_client()
    _settings = get_settings()

    results = await asyncio.gather(*[
        _tailor_project_bullets(
            proj, role_context, jd_parsed, _client, _settings, rules_text, gap_analysis,
            domain_guidance=domain_guidance,
            seniority_note=seniority_note,
        )
        for proj in projects
    ])
    return [r for r in results if r is not None]


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
    role_context: str,
    jd_parsed: dict,
    client,
    settings,
    rules_text: str = "",
    gap_analysis: dict | None = None,
    domain_guidance: str = "",
    seniority_note: str = "",
) -> TailoredActivity | None:
    bullets = extract_bullet_texts(act.get("bullets", []))
    if not bullets:
        return None

    act_id = str(act["id"])
    role = act.get("role_title") or ""
    org = act.get("organization") or ""
    act_context = f"{role} at {org}".strip(" at").strip() if role or org else ""
    priority_keywords = jd_parsed.get("required_skills", []) + jd_parsed.get("keywords", [])
    briefs = _build_bullet_briefs(bullets, gap_analysis, jd_parsed, rules_text, exp_context=act_context)

    rewritten = list(await asyncio.gather(*[
        _tailor_one_bullet(bullet, brief, role_context, client, settings, priority_keywords, domain_guidance, seniority_note)
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

    role_context = f"{jd_parsed.get('role_summary', 'N/A')} ({jd_parsed.get('domain', 'N/A')})"
    domain_guidance = _get_domain_guidance(jd_parsed.get("domain", ""))
    seniority_note = _get_seniority_note(jd_parsed.get("seniority_level", ""))
    _client = get_openai_client()
    _settings = get_settings()

    results = await asyncio.gather(*[
        _tailor_activity_bullets(
            act, role_context, jd_parsed, _client, _settings, rules_text, gap_analysis,
            domain_guidance=domain_guidance,
            seniority_note=seniority_note,
        )
        for act in activities
    ])
    return [r for r in results if r is not None]




def _similarity(a: str, b: str) -> float:
    """Similarity ratio (0-1) using SequenceMatcher for accurate comparison."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()
