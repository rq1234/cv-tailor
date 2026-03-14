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

from .domain_guidance import _get_domain_guidance


async def _retry_bullet(
    original: str,
    jd_summary: str,
    reason: str,
    client,
    settings,
) -> str:
    """Retry a single bullet that failed quality checks with a direct rewrite prompt.

    Used when the first pass was either too conservative (near-identical to original)
    or contained banned filler phrases. Falls back to original if retry also fails.
    """
    if reason == "too_similar":
        failure_note = (
            "Your previous rewrite was nearly identical to the original — just synonym swaps. "
            "That is NOT tailoring. Rewrite it with a different sentence structure."
        )
    else:
        failure_note = (
            "Your previous rewrite contained banned filler phrases like 'showcasing', "
            "'demonstrating expertise', 'leveraging expertise in', or similar. These are forbidden."
        )

    prompt = (
        f"{failure_note}\n\n"
        f"Rewrite this CV bullet so it naturally fits the target role. Rules:\n"
        f"- Keep every fact, number, and tech name from the original — do not invent anything\n"
        f"- Lead with what the job cares about most (see role context below)\n"
        f"- Write it the way a human would — no appended praise like 'showcasing X skills'\n"
        f"- A complete sentence restructure is encouraged — preserve facts, not words\n"
        f"- Output ONLY the bullet text, nothing else\n\n"
        f"Original: {original}\n\n"
        f"Role context:\n{jd_summary}"
    )

    try:
        response = await client.chat.completions.create(
            model=settings.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=220,
        )
        result = response.choices[0].message.content.strip().strip('"\'').lstrip("- ").strip()
        # Validate: if retry also drops tech or invents numbers, fall back to original
        if (
            _has_lost_tech_terms(original, result)
            or _has_hallucinated_numbers(original, result)
            or _BANNED_PHRASE_RE.search(result)
            or not result
        ):
            return original
        return result
    except Exception:
        return original


async def _apply_retry_pass(
    tailored: list,
    jd_summary: str,
    client,
    settings,
) -> None:
    """Replace silent reverts with targeted retries for recoverable failures.

    - too_similar / banned_phrase → retry with a direct rewrite prompt
    - over_compressed / lost_tech / hallucinated_numbers → revert to original (data safety)
    """
    retry_queue: list[tuple[int, int, str, str]] = []  # (entry_idx, bullet_idx, orig, reason)

    for entry_idx, entry in enumerate(tailored):
        for i, (orig, suggested) in enumerate(zip(entry.original_bullets, entry.suggested_bullets)):
            orig_norm = orig.lower().strip().rstrip(".")
            sugg_norm = suggested.text.lower().strip().rstrip(".")

            if orig_norm == sugg_norm or _similarity(orig_norm, sugg_norm) > 0.95:
                retry_queue.append((entry_idx, i, orig, "too_similar"))
            elif _is_over_compressed(orig, suggested.text):
                entry.suggested_bullets[i] = TailoredBullet(
                    text=orig, has_placeholder=False, outcome_type=suggested.outcome_type,
                )
            elif _has_lost_tech_terms(orig, suggested.text):
                entry.suggested_bullets[i] = TailoredBullet(
                    text=orig, has_placeholder=False, outcome_type=suggested.outcome_type,
                )
            elif _has_hallucinated_numbers(orig, suggested.text):
                entry.suggested_bullets[i] = TailoredBullet(
                    text=orig, has_placeholder=False, outcome_type=suggested.outcome_type,
                )
            elif _BANNED_PHRASE_RE.search(suggested.text):
                retry_queue.append((entry_idx, i, orig, "banned_phrase"))

    if not retry_queue:
        return

    retry_results = await asyncio.gather(*[
        _retry_bullet(orig, jd_summary, reason, client, settings)
        for _, _, orig, reason in retry_queue
    ])

    for (entry_idx, bullet_idx, _orig, _reason), new_text in zip(retry_queue, retry_results):
        entry = tailored[entry_idx]
        old = entry.suggested_bullets[bullet_idx]
        entry.suggested_bullets[bullet_idx] = TailoredBullet(
            text=new_text,
            has_placeholder=old.has_placeholder,
            outcome_type=old.outcome_type,
        )


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
- Within the SAME experience section, avoid starting consecutive bullets with the same verb. Using "Built" in one job and "Built" in another job is fine — repetition only looks bad when multiple bullets in the same role all open the same way.
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
Think of the original bullet as a **fact sheet**. The facts are fixed — every number, tech name, scope, and achievement must be preserved. But the framing, emphasis, and sentence structure should be **completely rebuilt** for this job.

Ask yourself: "If this candidate had written their CV knowing this exact job description, how would this bullet read?" Write that version.

1. **REWRITE from scratch**, leading with what the JD cares about most. The original sentence structure is a suggestion, not a constraint. A complete restructure is encouraged.
2. **EMBED JD language into the action itself** — "Built real-time data pipelines using Airflow" not "Built Airflow pipelines, supporting real-time analytics objectives." The JD theme goes IN the doing, not tacked on at the end.
3. **PRESERVE every fact**: tech names, numbers, scope, outcomes. These are non-negotiable.
4. A bullet that reads noticeably differently — with the same facts — is always better than one that barely changed.

The ONLY reason to leave a bullet close to unchanged is if it already perfectly leads with the right JD theme and no structural improvement is possible. That should be rare.

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

### Example 3 — Bullet already uses JD vocabulary but can lead stronger
Original: "Designed and deployed ML pipeline using XGBoost and SHAP, reducing churn by 15%"
JD emphasises: "predictive modelling" and "customer retention"
BAD (verbatim cop-out): return unchanged ← lazy
GOOD: "Built predictive ML pipeline (XGBoost, SHAP) to model customer churn, driving 15% retention improvement" ← reframes around "predictive modelling" and "customer retention", preserves all tech and metrics

### Example 4 — JD emphasizes "Python" and "quantitative analysis" (ANTI-PATTERN)
Original: "Selected as 1 of 80 students across EMEA for Citadel's European Trading Invitational"
BAD (appended filler): "Selected as 1 of 80 students for Citadel's European Trading Invitational, demonstrating quantitative analysis skills" ← "demonstrating X skills" is empty filler a recruiter will ignore
GOOD (no JD theme possible): Return unchanged ONLY when the brief says no JD theme can be truthfully added. "1 of 80" is already a strong signal; forced additions read as AI-generated.

## Output Rules
- CRITICAL: A change must either: (a) reframe the opening to lead with a JD Key Responsibility theme, (b) add a JD-relevant outcome signal or framing context, or (c) meaningfully surface a hidden keyword. Synonym swaps alone ("Built"→"Developed", "using"→"utilizing") are NOT improvements. A rewrite that is 95%+ similar to the original will be rejected — it must read noticeably differently.
- CRITICAL: Return EXACTLY the same number of suggested_bullets as original_bullets — one per original bullet. Never split a bullet into two. Never merge two into one.
- CRITICAL: NEVER remove technical terms, model names, framework names, or specific methods from the original bullet. Every tech term (XGBoost, SHAP, PostgreSQL, RAG, etc.) that appears in the original must appear in the rewrite. Dropping a tech term is always wrong.
- For each change, document what you changed and why in changes_made. If you shortened a bullet, explain what you removed and why it was safe to remove.
- In requirements_addressed, list which JD requirements this experience's bullets now cover.
- Set confidence based on how well the rewrite matches the JD (0.5 = minimal, 1.0 = strong match).

{domain_section}

{gap_analysis_section}

{rules_section}
"""

# Shared step-by-step instructions appended to every per-entry user message.
_BULLET_PROCESS_STEPS = """
For each bullet, follow this process:
1. Read the tailoring brief — it tells you exactly which JD theme to surface.
2. Identify the MOST JD-critical element in the bullet (a skill, outcome, or context the JD values).
3. Move that element to the FRONT. Restructure the sentence so the JD priority is the first thing read.
4. Add JD-specific framing context if truthful (e.g. "for real-time analytics", "supporting cross-functional stakeholders"). This adds meaning — it is NOT the same as "demonstrating X skills".
5. Do NOT just swap a synonym ("Built"→"Developed"). That is not improvement. Produce the best structural reframe you can."""


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
    return briefs


async def _tailor_one_experience(
    exp: dict,
    system_prompt: str,
    jd_summary: str,
    gap_analysis: dict | None,
    jd_parsed: dict,
    client,
    settings,
) -> TailoredExperience:
    """Fire a focused API call for a single experience's bullets."""
    bullets = extract_bullet_texts(exp.get("bullets", []))
    exp_id = str(exp["id"])

    if not bullets:
        return TailoredExperience(
            experience_id=exp_id, original_bullets=[],
            suggested_bullets=[], changes_made=[], confidence=0.5,
        )

    company = exp.get("company") or "Unknown"
    role = exp.get("role_title") or "Unknown"
    briefs = _build_bullet_briefs(bullets, gap_analysis, jd_parsed)

    user_message = (
        f"Target Job Description:\n{jd_summary}\n\n"
        f"Experience to tailor:\n"
        f"--- {company} — {role} (ID: {exp_id}) ---\n"
    )
    for i, (bullet, brief) in enumerate(zip(bullets, briefs)):
        user_message += f"  {i+1}. {bullet}\n{brief}\n"
    user_message += _BULLET_PROCESS_STEPS + "\nReturn this experience."

    response = await client.beta.chat.completions.parse(
        model=settings.model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format=TailorOutput,
        temperature=settings.temp_tailoring,
    )
    results = response.choices[0].message.parsed.tailored_experiences
    if results:
        return results[0]

    return TailoredExperience(
        experience_id=exp_id, original_bullets=bullets,
        suggested_bullets=[TailoredBullet(text=b, has_placeholder=False, outcome_type="process") for b in bullets],
        changes_made=[], confidence=0.5,
    )


async def tailor_experiences(
    experiences: list[dict],
    jd_parsed: dict,
    gap_analysis: dict | None = None,
    rules_text: str = "",
) -> list[TailoredExperience]:
    """Tailor selected experiences to match the JD using GPT-4o.

    Fires one focused API call per experience in parallel so the model
    gives full attention to each role's bullets rather than spreading
    attention across the entire CV at once.
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
    jd_summary = _build_jd_summary(jd_parsed)

    _client = get_openai_client()
    _settings = get_settings()

    # One focused call per experience, all fired in parallel
    tailored = list(await asyncio.gather(*[
        _tailor_one_experience(exp, system_prompt, jd_summary, gap_analysis, jd_parsed, _client, _settings)
        for exp in experiences
    ]))

    # Enforce 1-to-1: if bullet count drifts, fall back to originals for that experience
    for te in tailored:
        if len(te.suggested_bullets) != len(te.original_bullets):
            te.suggested_bullets = [
                TailoredBullet(text=b, has_placeholder=False, outcome_type="process")
                for b in te.original_bullets
            ]

    # Post-process: retry conservative/banned bullets; revert data-safety failures
    await _apply_retry_pass(tailored, jd_summary, _client, _settings)

    # Enforce length by trimming just-over-line / expanding short / trimming long bullets
    await _apply_length_refinements(tailored, jd_summary, trim_low=95, trim_high=135)

    _clean_changes_made(tailored)

    # Reorder bullets within each experience so the most JD-relevant comes first
    priority_keywords = jd_parsed.get("required_skills", []) + jd_parsed.get("keywords", [])
    _reorder_bullets_by_relevance(tailored, priority_keywords)

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
- Within the SAME project/activity, avoid starting consecutive bullets with the same verb. Cross-entry repetition is fine.
- Vary verbs: Built, Implemented, Designed, Created, Engineered, Launched, Automated, Led.

## Truthfulness Rules
- NEVER invent metrics, outcomes, or responsibilities not implied by the original bullet.
- Preserve the original scope — don't inflate contributions.

## What "Tailoring" Actually Means
- REFRAME to lead with the theme the JD cares about. Move the JD-critical element to the opening clause.
- ADD JD-relevant framing (e.g. "for real-time analytics") only if truthful.
- KEEP all existing tech details and metrics.
- Every bullet MUST be actively improved. Even a good bullet can be reframed to lead more strongly with the JD priority. Only leave a bullet unchanged if the tailoring brief says there is no JD theme that can be truthfully added.

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

### Example 2 — Bullet already uses JD vocab but can lead stronger
Original: "Led a team of 4 to build a real-time dashboard using React and D3.js, winning 2nd place"
JD emphasises: "data visualisation" and "cross-functional collaboration"
GOOD: "Spearheaded cross-functional team of 4 to deliver real-time data visualisation dashboard (React, D3.js), winning 2nd place" ← leads with "cross-functional" and "data visualisation" (JD themes), preserves all facts

## Output Rules
- CRITICAL: A rewrite must either: (a) reframe the opening to lead with a JD theme, (b) add JD-relevant framing context, or (c) surface a hidden keyword. Synonym swaps alone are NOT improvements. A rewrite 95%+ similar to the original will be rejected.
- CRITICAL: NEVER remove technical terms, model names, framework names, or specific methods. Every tech term in the original must appear in the rewrite. Dropping a tech term is always wrong.
- For each change, document what you changed and why in changes_made.

{domain_section}

{rules_section}
"""


async def _tailor_one_project(
    proj: dict,
    system_prompt: str,
    jd_summary: str,
    jd_parsed: dict,
    client,
    settings,
) -> TailoredProject | None:
    """Fire a focused API call for a single project's bullets. Returns None if no bullets."""
    bullets = extract_bullet_texts(proj.get("bullets", []))
    if not bullets:
        bullets = split_description_to_bullets(proj.get("description") or "")
    if not bullets:
        return None

    proj_id = str(proj["id"])
    name = proj.get("name") or "Unknown"
    description = proj.get("description") or ""
    briefs = _build_bullet_briefs(bullets, None, jd_parsed)

    user_message = (
        f"Target Job Description:\n{jd_summary}\n\n"
        f"Project to tailor:\n"
        f"--- {name} (ID: {proj_id}) ---\n"
    )
    if description:
        user_message += f"  Description: {description}\n"
    for i, (bullet, brief) in enumerate(zip(bullets, briefs)):
        user_message += f"  {i+1}. {bullet}\n{brief}\n"
    user_message += _BULLET_PROCESS_STEPS + "\nReturn this project."

    response = await client.beta.chat.completions.parse(
        model=settings.model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format=TailorProjectsOutput,
        temperature=settings.temp_tailoring,
    )
    results = response.choices[0].message.parsed.tailored_projects
    if results:
        return results[0]

    return TailoredProject(
        project_id=proj_id, original_bullets=bullets,
        suggested_bullets=[TailoredBullet(text=b, has_placeholder=False, outcome_type="process") for b in bullets],
        changes_made=[], confidence=0.5,
    )


async def tailor_projects(
    projects: list[dict],
    jd_parsed: dict,
    rules_text: str = "",
) -> list[TailoredProject]:
    """Tailor selected projects/leadership to match the JD using GPT-4o.

    Fires one focused API call per project in parallel.
    """
    if not projects:
        return []

    domain_section = _get_domain_guidance(jd_parsed.get("domain", ""))
    system_prompt = PROJECT_SYSTEM_PROMPT.format(
        domain_section=domain_section,
        rules_section=rules_text,
    )
    jd_summary = _build_jd_summary(jd_parsed)

    _client = get_openai_client()
    _settings = get_settings()

    results = await asyncio.gather(*[
        _tailor_one_project(proj, system_prompt, jd_summary, jd_parsed, _client, _settings)
        for proj in projects
    ])
    tailored = [r for r in results if r is not None]

    if not tailored:
        return []

    # Enforce 1-to-1: if bullet count drifts, fall back to originals for that project
    for tp in tailored:
        if len(tp.suggested_bullets) != len(tp.original_bullets):
            tp.suggested_bullets = [
                TailoredBullet(text=b, has_placeholder=False, outcome_type="process")
                for b in tp.original_bullets
            ]

    # Post-process: retry conservative/banned bullets; revert data-safety failures
    await _apply_retry_pass(tailored, jd_summary, _client, _settings)

    # Enforce length by trimming just-over-line / expanding short / trimming long bullets
    await _apply_length_refinements(tailored, jd_summary, trim_low=105, trim_high=145)

    _clean_changes_made(tailored)

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


async def _tailor_one_activity(
    act: dict,
    system_prompt: str,
    jd_summary: str,
    jd_parsed: dict,
    client,
    settings,
) -> TailoredActivity | None:
    """Fire a focused API call for a single activity's bullets. Returns None if no bullets."""
    bullets = extract_bullet_texts(act.get("bullets", []))
    if not bullets:
        return None

    act_id = str(act["id"])
    org = act.get("organization") or "Unknown"
    role = act.get("role_title") or ""
    briefs = _build_bullet_briefs(bullets, None, jd_parsed)

    user_message = (
        f"Target Job Description:\n{jd_summary}\n\n"
        f"Activity to tailor:\n"
        f"--- {role} at {org} (ID: {act_id}) ---\n"
    )
    for i, (bullet, brief) in enumerate(zip(bullets, briefs)):
        user_message += f"  {i+1}. {bullet}\n{brief}\n"
    user_message += _BULLET_PROCESS_STEPS + "\nReturn this activity."

    response = await client.beta.chat.completions.parse(
        model=settings.model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format=TailorActivitiesOutput,
        temperature=settings.temp_tailoring,
    )
    results = response.choices[0].message.parsed.tailored_activities
    if results:
        return results[0]

    return TailoredActivity(
        activity_id=act_id, original_bullets=bullets,
        suggested_bullets=[TailoredBullet(text=b, has_placeholder=False, outcome_type="process") for b in bullets],
        changes_made=[], confidence=0.5,
    )


async def tailor_activities(
    activities: list[dict],
    jd_parsed: dict,
    rules_text: str = "",
) -> list[TailoredActivity]:
    """Tailor selected activities (leadership/extracurricular) to match the JD using GPT-4o.

    Fires one focused API call per activity in parallel.
    """
    if not activities:
        return []

    domain_section = _get_domain_guidance(jd_parsed.get("domain", ""))
    system_prompt = PROJECT_SYSTEM_PROMPT.format(
        domain_section=domain_section,
        rules_section=rules_text,
    )
    jd_summary = _build_jd_summary(jd_parsed)

    _client = get_openai_client()
    _settings = get_settings()

    results = await asyncio.gather(*[
        _tailor_one_activity(act, system_prompt, jd_summary, jd_parsed, _client, _settings)
        for act in activities
    ])
    tailored = [r for r in results if r is not None]

    if not tailored:
        return []

    # Enforce 1-to-1: if bullet count drifts, fall back to originals for that activity
    for ta in tailored:
        if len(ta.suggested_bullets) != len(ta.original_bullets):
            ta.suggested_bullets = [
                TailoredBullet(text=b, has_placeholder=False, outcome_type="process")
                for b in ta.original_bullets
            ]

    # Post-process: retry conservative/banned bullets; revert data-safety failures
    await _apply_retry_pass(tailored, jd_summary, _client, _settings)

    # Enforce length by trimming just-over-line / expanding short / trimming long bullets
    await _apply_length_refinements(tailored, jd_summary, trim_low=95, trim_high=135)

    _clean_changes_made(tailored)

    priority_keywords = jd_parsed.get("required_skills", []) + jd_parsed.get("keywords", [])
    _reorder_bullets_by_relevance(tailored, priority_keywords)

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
