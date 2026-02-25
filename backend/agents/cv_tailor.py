"""Agent: Tailor selected experiences to the job description."""

from __future__ import annotations

from difflib import SequenceMatcher

from pydantic import BaseModel, Field

from backend.clients import get_openai_client
from backend.config import get_settings
from backend.utils import extract_bullet_texts, split_description_to_bullets

# ---------------------------------------------------------------------------
# Domain-specific tailoring guidance
# Distilled from strong real-world CVs per industry.
# ---------------------------------------------------------------------------

DOMAIN_GUIDANCE: dict[str, str] = {
    "tech": """\
## Domain-Specific Norms: Technology / Software Engineering
Apply these norms on top of the general rules above.

**Action Verbs (prefer):** Architected, Engineered, Built, Implemented, Deployed, Automated, Designed, Launched, Shipped, Migrated, Integrated, Optimised

**Lead with:** Specific named technologies + quantified scale/impact
- Pattern: "[Verb] [system/tool] using [Tech A, Tech B], [reducing/achieving/improving] [metric]"
- Good: "Engineered high-performance CLI tool in Go, cutting logging infrastructure cost by 50% with a self-updating binary"
- Good: "Implemented dataset using Scala and Apache Beam APIs, achieving 60% compression vs raw metadata source"
- Good: "Developed scalable event-driven AWS pipeline (CDK, API Gateway, Lambda, SQS), serving 500,000+ events daily while reducing AWS costs by 50%"

**Always embed tech names inline** — never appended at the end as a list. ATS systems and recruiters Ctrl+F for exact tech names.

**Preferred scale language:** "500,000+ events daily", "over 200 students", "1.88 million records", "reducing latency by X%", "99.9% uptime", "X% compression"

**Quantified outcome formats to use:**
- Cost: "reducing AWS costs by 50%", "cutting infrastructure cost by 50%"
- Speed: "improving data refresh rates by 50%", "reducing metric reporting time by 95%"
- Scale: "serving 500,000+ events daily", "automating 100% of the backend API test suite"
- Accuracy: "reaching an accuracy of 83%"
- Efficiency: "reduced customer time-to-analysis by 75%", "reduced manual testing efforts by 80%"

**Avoid:** vague statements without tech specifics; "responsible for"; listing tech at the end of the bullet instead of inline in the action.
""",

    "finance": """\
## Domain-Specific Norms: Finance / Investment Banking
Apply these norms on top of the general rules above.

**Action Verbs (prefer):** Advised, Executed, Modeled, Analyzed, Prepared, Coordinated, Originated, Evaluated, Structured, Supported, Performed, Constructed

**Lead with:** Deal size ($XXXm / $XXXBn) or transaction type when the original mentions a deal
- Pattern: "Member of deal team on $[X]B [transaction type] advising [Target/Acquirer]"
- Pattern: "[Verb] [financial analysis type] for [deal context/client tier]"
- Good: "Member of deal team on $3.2 billion acquisition of a publicly traded company by a large-cap private equity firm"
- Good: "Built dynamic LBO model with multiple operating and pro forma capital structure scenarios to determine private equity sponsor affordability based on projected IRR and LCFV Yield"
- Good: "Prepared CIM and pitch book for $700MM debt financing transaction in the energy sector"

**Finance vocabulary — use naturally where truthful:**
- Documents: CIM (Confidential Information Memorandum), pitch book, information memorandum, teaser, management presentation
- Analysis types: LBO (Leveraged Buyout), M&A, DCF (Discounted Cash Flow), precedent transactions, comparable companies (comps), accretion/dilution analysis, pro forma, sensitivity analysis, operating model, 3-statement model
- Financial metrics: IRR, EBITDA, EBITDA margins, revenue, COGS, capital structure, debt drawdown, covenant compliance
- Modeling verbs: built, constructed, prepared, performed, ran

**Tools — reference only if truthful:** Bloomberg, CapitalIQ, Excel (financial modeling), PowerPoint (pitch materials)

**Outcome proxies when % metrics are not available:**
- Deal size: "$700MM transaction", "$3.2 billion acquisition"
- Deal status: "Closed July 2020", "Active", "Pending"
- Client/counterparty tier: "publicly traded company", "Fortune 500", "PE sponsor"
- Geographic scope: "across Americas, Europe and Asia-Pacific", "across 37 product lines"

**Avoid:** Technology-style % efficiency metrics where not applicable to the work described; starting bullets with "Responsible for" — always reframe to active voice ("Prepared" instead of "Responsible for preparing").
""",

    "consulting": """\
## Domain-Specific Norms: Management Consulting
Apply these norms on top of the general rules above.

**Action Verbs (prefer):** Advised, Delivered, Structured, Synthesised, Developed, Presented, Facilitated, Coordinated, Diagnosed, Recommended, Designed, Led

**Lead with:** Client impact or business outcome
- Pattern: "[Verb] [deliverable type] for [client context], [resulting in/enabling] [business outcome]"
- Good: "Structured go-to-market diagnostic for a PE-backed retail client, identifying $4m cost reduction opportunity"
- Good: "Developed recommendations across 5 workstreams for a Fortune 500 consumer goods client, enabling $12m annual savings"

**Consulting vocabulary — use naturally where truthful:**
- Structure terms: workstream, deliverable, MECE framework, top-down, structured problem-solving, hypothesis-driven
- Process terms: diagnostic, discovery phase, client engagement, stakeholder alignment, steering committee, executive presentation
- Output terms: recommendations, board deck, business case, implementation roadmap

**Outcome formats to prefer:**
- "$Xm cost reduction", "X% efficiency gain", "X new markets entered", "X% improvement in [metric]"
- Team/scope: "across [X] business units", "for [Fortune 500 / PE-backed / government] client", "in [X] countries"

**Avoid:** Tech-heavy descriptions (unless in tech consulting); "responsible for"; bullets with no outcome or scope signal.
""",

    "quant": """\
## Domain-Specific Norms: Quantitative Finance / Algorithmic Trading
Apply these norms on top of the general rules above.

**Action Verbs (prefer):** Developed, Researched, Implemented, Backtested, Deployed, Optimised, Modeled, Calibrated, Engineered, Built, Analysed

**Lead with:** Strategy/model performance OR technical achievement — whichever is stronger
- Pattern (research): "[Verb] [strategy/model type] using [method/tech], achieving [performance metric]"
- Pattern (engineering): "[Verb] [system component] in [language], achieving [latency/throughput metric]"
- Good: "Developed mean-reversion equity strategy using Python and scikit-learn, achieving 1.4 Sharpe ratio over 3-year backtest"
- Good: "Built cross-sectional factor model on 1,000+ US equities using XGBoost and SHAP, generating [X]% annualised alpha"
- Good: "Implemented low-latency order execution engine in C++, achieving <50μs round-trip latency on co-located infrastructure"
- Good: "Backtested momentum strategy on 10 years of tick data, achieving Sharpe of 1.8 with max drawdown of 12%"

**Quant vocabulary — use naturally where truthful:**
- Strategy types: alpha generation, signal research, momentum, mean reversion, statistical arbitrage (stat arb), pairs trading, market making, execution optimisation, delta hedging
- Model types: factor model, covariance matrix estimation, regime detection, volatility surface, Monte Carlo simulation, GARCH, PCA, Kalman filter
- Performance metrics: Sharpe ratio, Sortino ratio, information ratio, maximum drawdown, annualised alpha/return, P&L, hit rate, win/loss ratio, turnover
- Data: tick data, order book (L2/L3), OHLCV, alternative data, sentiment data, corporate actions
- Execution: FIX protocol, market impact, TWAP/VWAP, slippage, co-location, latency (μs/ms)

**Tools — reference only if truthful:** Python (pandas, numpy, scipy, statsmodels, scikit-learn), C++, R, MATLAB, kdb+/q, Bloomberg, Refinitiv/Eikon, QuantLib, Julia

**Performance outcome formats (highest priority — use these when available):**
- Strategy: "achieving 1.4 Sharpe ratio over [X]-year backtest", "generating [X]% annualised alpha", "with maximum drawdown of [X]%"
- System: "<50μs round-trip latency", "processing 10M+ ticks/day", "[X]% reduction in slippage"
- Deployment: "deployed to production managing $[X]m in AUM", "live since [date]"
- Competition/selection: "1 of 80 students selected for Citadel Trading Invitational", "finalist in Jane Street ETC"

**Avoid:** Generic IB vocabulary (pitchbooks, CIM) where not applicable; technology-style cost/user metrics as the primary outcome — quant bullets are judged on financial performance first, engineering scale second.
""",
}


def _get_domain_guidance(domain: str) -> str:
    """Map a JD domain string to domain-specific tailoring guidance.

    Uses keyword matching so "investment banking" → finance, "algorithmic trading" → quant, etc.
    Returns an empty string for unrecognised domains (graceful fallback).
    Quant is checked FIRST because "quantitative finance" is more specific than "finance".
    """
    if not domain:
        return ""
    d = domain.lower()
    # Quant / Trading — check BEFORE finance; "quantitative finance" → quant not generic finance
    if any(
        kw in d
        for kw in (
            "quant",
            "algorithmic",
            "algo trading",
            "prop trading",
            "trading",
            "market making",
            "systematic",
            "high frequency",
            "hft",
            "statistical arbitrage",
        )
    ):
        return DOMAIN_GUIDANCE["quant"]
    # Finance / IB — check before tech because "financial technology" should → finance
    if any(
        kw in d
        for kw in (
            "finance",
            "banking",
            "investment",
            "financial services",
            "capital markets",
            "private equity",
            "asset management",
            "hedge fund",
            "venture capital",
            "wealth management",
        )
    ):
        return DOMAIN_GUIDANCE["finance"]
    # Consulting
    if any(
        kw in d
        for kw in (
            "consulting",
            "advisory",
            "management consulting",
        )
    ):
        return DOMAIN_GUIDANCE["consulting"]
    # Tech / Software
    if any(
        kw in d
        for kw in (
            "tech",
            "software",
            "engineering",
            "data",
            "machine learning",
            " ai",
            "artificial intelligence",
            "saas",
            "cloud",
            "cybersecurity",
            "security",
            "product",
        )
    ):
        return DOMAIN_GUIDANCE["tech"]
    return ""


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
        model=_settings.model_name,
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
    
    LaTeX CV with \small font fits ~90-100 chars per line. Bullets 105-145 chars
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
        model=_settings.model_name,
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
        model=_settings.model_name,
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


def _build_bullet_briefs(
    bullets: list[str],
    gap_analysis: dict | None,
    jd_parsed: dict,
) -> list[str]:
    """For each bullet, build a short tailoring brief: which JD themes to surface.

    Uses gap analysis mappings (evidence + suggested_framing) when available,
    otherwise falls back to simple keyword overlap from jd_parsed.
    """
    # Collect JD keywords and requirements for fallback matching
    jd_keywords = set()
    for kw in jd_parsed.get("keywords", []):
        jd_keywords.add(kw.lower())
    for skill in jd_parsed.get("required_skills", []):
        jd_keywords.add(skill.lower())
    for resp in jd_parsed.get("key_responsibilities", []):
        jd_keywords.add(resp.lower())
    outcome_signals = jd_parsed.get("outcome_signals", [])

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
                    # Check if this mapping's evidence references this bullet
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

    briefs = []
    for bullet in bullets:
        # Use gap analysis framings if available
        if bullet in bullet_to_framings:
            themes = bullet_to_framings[bullet]
            briefs.append(
                f"  → Tailoring brief: Reframe to surface these JD themes: {'; '.join(themes)}"
            )
        else:
            # Fallback: find keyword overlaps
            bullet_lower = bullet.lower()
            matching_keywords = [
                kw for kw in jd_keywords if kw in bullet_lower
            ]
            matching_outcomes = [
                sig for sig in outcome_signals if sig.lower() in bullet_lower
            ]
            if matching_keywords or matching_outcomes:
                all_themes = matching_keywords + matching_outcomes
                briefs.append(
                    f"  → Tailoring brief: This bullet touches JD themes: {', '.join(all_themes[:4])}. Lead with the most relevant one."
                )
            else:
                briefs.append(
                    "  → Tailoring brief: No exact JD keyword found. Check whether any of the Key Responsibilities above describe the same type of work. If so, reframe the bullet to lead with that responsibility theme. If genuinely unrelated, return verbatim."
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

    # Build JD summary for context
    key_responsibilities = jd_parsed.get('key_responsibilities', [])
    jd_summary = f"""
Role: {jd_parsed.get('role_summary', 'N/A')}
Domain: {jd_parsed.get('domain', 'N/A')}
Seniority: {jd_parsed.get('seniority_level', 'N/A')}
Key Responsibilities: {'; '.join(key_responsibilities) if key_responsibilities else 'N/A'}
Required Skills: {', '.join(jd_parsed.get('required_skills', []))}
Nice to Have: {', '.join(jd_parsed.get('nice_to_have_skills', []))}
Keywords: {', '.join(jd_parsed.get('keywords', []))}
Outcome Signals: {', '.join(jd_parsed.get('outcome_signals', []))}
"""

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

    # Enforce length by trimming just-over-line / expanding short / trimming long bullets
    for te in tailored:
        for i, (orig, suggested) in enumerate(
            zip(te.original_bullets, te.suggested_bullets)
        ):
            # First: optimize bullets that waste half a line (95-135 chars)
            if 95 <= len(suggested.text) <= 135:
                te.suggested_bullets[i] = await _trim_just_over_line(
                    orig, suggested, jd_summary,
                )
            # Then: expand short bullets (after potential trim)
            elif len(te.suggested_bullets[i].text) < 100:
                te.suggested_bullets[i] = await _expand_short_bullet(
                    orig, te.suggested_bullets[i], jd_summary,
                )
            # Finally: trim very long bullets (after potential expansions)
            elif len(te.suggested_bullets[i].text) > 200:
                te.suggested_bullets[i] = await _trim_long_bullet(
                    orig, te.suggested_bullets[i], jd_summary,
                )

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

    # Build JD summary
    key_responsibilities = jd_parsed.get('key_responsibilities', [])
    jd_summary = f"""
Role: {jd_parsed.get('role_summary', 'N/A')}
Domain: {jd_parsed.get('domain', 'N/A')}
Seniority: {jd_parsed.get('seniority_level', 'N/A')}
Key Responsibilities: {'; '.join(key_responsibilities) if key_responsibilities else 'N/A'}
Required Skills: {', '.join(jd_parsed.get('required_skills', []))}
Nice to Have: {', '.join(jd_parsed.get('nice_to_have_skills', []))}
Keywords: {', '.join(jd_parsed.get('keywords', []))}
Outcome Signals: {', '.join(jd_parsed.get('outcome_signals', []))}
"""

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
                    text=orig,
                    has_placeholder=False,
                    outcome_type=suggested.outcome_type,
                )

    # Enforce length by trimming just-over-line / expanding short / trimming long bullets
    for tp in tailored:
        for i, (orig, suggested) in enumerate(
            zip(tp.original_bullets, tp.suggested_bullets)
        ):
            # First: optimize bullets that waste half a line (105-145 chars)
            if 105 <= len(suggested.text) <= 145:
                tp.suggested_bullets[i] = await _trim_just_over_line(
                    orig, suggested, jd_summary,
                )
            # Then: expand short bullets (after potential trim)
            elif len(tp.suggested_bullets[i].text) < 100:
                tp.suggested_bullets[i] = await _expand_short_bullet(
                    orig, tp.suggested_bullets[i], jd_summary,
                )
            # Finally: trim very long bullets (after potential expansions)
            elif len(tp.suggested_bullets[i].text) > 200:
                tp.suggested_bullets[i] = await _trim_long_bullet(
                    orig, tp.suggested_bullets[i], jd_summary,
                )

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

    # Build JD summary
    jd_summary = f"""
Role: {jd_parsed.get('role_summary', 'N/A')}
Domain: {jd_parsed.get('domain', 'N/A')}
Seniority: {jd_parsed.get('seniority_level', 'N/A')}
Required Skills: {', '.join(jd_parsed.get('required_skills', []))}
Nice to Have: {', '.join(jd_parsed.get('nice_to_have_skills', []))}
Keywords: {', '.join(jd_parsed.get('keywords', []))}
"""

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
                    text=orig,
                    has_placeholder=False,
                    outcome_type=suggested.outcome_type,
                )

    # Enforce length by trimming just-over-line / expanding short / trimming long bullets
    for ta in tailored:
        for i, (orig, suggested) in enumerate(
            zip(ta.original_bullets, ta.suggested_bullets)
        ):
            # First: optimize bullets that waste half a line (95-135 chars)
            if 95 <= len(suggested.text) <= 135:
                ta.suggested_bullets[i] = await _trim_just_over_line(
                    orig, suggested, jd_summary,
                )
            # Then: expand short bullets (after potential trim)
            elif len(ta.suggested_bullets[i].text) < 100:
                ta.suggested_bullets[i] = await _expand_short_bullet(
                    orig, ta.suggested_bullets[i], jd_summary,
                )
            # Finally: trim very long bullets (after potential expansions)
            elif len(ta.suggested_bullets[i].text) > 200:
                ta.suggested_bullets[i] = await _trim_long_bullet(
                    orig, ta.suggested_bullets[i], jd_summary,
                )

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
