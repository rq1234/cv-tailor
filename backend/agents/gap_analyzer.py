"""Agent: Map candidate experience to JD requirements and identify gaps."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.clients import get_openai_client
from backend.config import get_settings
from backend.utils import extract_bullet_texts, retry_openai


class RequirementMapping(BaseModel):
    requirement: str = Field(description="A skill or responsibility from the JD")
    status: str = Field(description="'strong_match', 'partial_match', or 'gap'")
    evidence: str = Field(
        description="Which experience/bullet supports this, or empty string if gap"
    )
    suggested_framing: str = Field(
        description="How to frame existing experience to address this requirement, even if partial. Empty if no relevant experience."
    )


class GapAnalysis(BaseModel):
    mappings: list[RequirementMapping] = Field(default_factory=list)
    transferable_strengths: list[str] = Field(
        default_factory=list,
        description="Candidate strengths not in JD but valuable to highlight (e.g. adjacent domain expertise)",
    )
    keyword_density_warnings: list[str] = Field(
        default_factory=list,
        description="Keywords that appear too frequently or would look unnatural if added",
    )


SYSTEM_PROMPT = """\
You are a career strategist mapping a candidate's experience to a job description.

Your job is to perform an honest gap analysis — NOT to help the candidate lie, but to find the strongest truthful framing of their existing experience.

For each JD requirement:
1. Search the candidate's experience bullets for direct or transferable evidence.
2. Classify as strong_match (direct experience), partial_match (transferable/adjacent), or gap (no relevant experience).
3. For partial matches, suggest how to reframe existing experience to surface relevance — but NEVER fabricate experience.
4. For gaps, leave evidence empty. The candidate needs to know what they're missing.

Also identify:
- transferable_strengths: Skills the candidate has that aren't in the JD but add value (e.g. multilingual, cross-functional experience, domain knowledge from an adjacent field).
- keyword_density_warnings: Flag any keywords that would look forced if repeated. ATS and recruiters detect unnatural repetition — a keyword used 2-3x is fine, 5+ is a red flag.

Be brutally honest about gaps. A candidate who knows their gaps can address them in the cover letter or interview prep.
"""


def _build_exp_text(experiences: list[dict], activities: list[dict] | None = None) -> str:
    """Build a plain-text summary of experiences and activities for the prompt."""
    parts = []
    for exp in experiences:
        bullets = extract_bullet_texts(exp.get("bullets", []))
        parts.append(f"\n--- {exp.get('company', 'Unknown')} — {exp.get('role_title', 'Unknown')} ---")
        for bullet in bullets:
            parts.append(f"  • {bullet}")
    for act in (activities or []):
        bullets = extract_bullet_texts(act.get("bullets", []))
        parts.append(f"\n--- {act.get('organization', 'Unknown')} — {act.get('role_title', 'Unknown')} (Activity) ---")
        for bullet in bullets:
            parts.append(f"  • {bullet}")
    return "\n".join(parts)


@retry_openai()
async def analyze_gaps(
    experiences: list[dict],
    jd_parsed: dict,
    activities: list[dict] | None = None,
) -> GapAnalysis:
    """Map candidate experience to JD requirements and identify gaps.

    Args:
        experiences: List of dicts with keys: company, role_title, bullets.
        jd_parsed: Parsed JD dict.
        activities: Optional list of dicts with keys: organization, role_title, bullets.
    """
    exp_text = _build_exp_text(experiences, activities)

    # Build requirements list from JD
    requirements = []
    requirements.extend(jd_parsed.get("required_skills", []))
    requirements.extend(jd_parsed.get("key_responsibilities", []))
    requirements.extend(jd_parsed.get("tools_and_technologies", []))

    user_message = f"""Job Description Requirements:
Role: {jd_parsed.get('role_summary', 'N/A')}
Domain: {jd_parsed.get('domain', 'N/A')}
Seniority: {jd_parsed.get('seniority_level', 'N/A')}

Requirements to map against:
{chr(10).join(f'- {r}' for r in requirements)}

Nice to have:
{chr(10).join(f'- {s}' for s in jd_parsed.get('nice_to_have_skills', []))}

ATS Keywords:
{', '.join(jd_parsed.get('keywords', []))}

Candidate's Experience:
{exp_text}

Map each requirement to the candidate's experience. Be honest about gaps."""

    client = get_openai_client()
    settings = get_settings()
    response = await client.beta.chat.completions.parse(
        model=settings.model_name,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        response_format=GapAnalysis,
        temperature=settings.temp_gap_analysis,
    )

    return response.choices[0].message.parsed
