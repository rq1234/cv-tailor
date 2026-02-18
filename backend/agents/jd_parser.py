"""Agent: Parse job description into structured data using GPT-4o."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.clients import get_openai_client
from backend.config import get_settings
from backend.utils import retry_openai


class ParsedJD(BaseModel):
    """Structured job description output."""

    required_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    tools_and_technologies: list[str] = Field(
        default_factory=list,
        description="Specific tools, platforms, languages, frameworks mentioned (e.g. Python, Tableau, AWS, SQL)",
    )
    key_responsibilities: list[str] = Field(
        default_factory=list,
        description="Core responsibilities/duties listed in the JD, as concise phrases",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="ATS-critical keywords: exact phrases a recruiter/ATS would search for",
    )
    outcome_signals: list[str] = Field(
        default_factory=list,
        description="Implied measurable outcomes the role cares about (e.g. 'revenue growth', 'cost reduction', 'time-to-market', 'user retention')",
    )
    seniority_level: str = ""
    domain: str = ""
    company_values_mentioned: list[str] = Field(default_factory=list)
    role_summary: str = ""


SYSTEM_PROMPT = """\
You are a job description parser specializing in ATS keyword extraction. Given a raw job description, extract structured information optimized for resume tailoring.

Rules:
- required_skills: Skills explicitly listed as required or mandatory.
- nice_to_have_skills: Skills listed as preferred, nice-to-have, or bonus.
- tools_and_technologies: Every specific tool, platform, programming language, framework, or software mentioned. Use the EXACT phrasing from the JD (e.g. "Microsoft Excel" not just "Excel", "Power BI" not "PowerBI").
- key_responsibilities: The 5-8 most important duties/responsibilities. Phrase as concise action statements.
- keywords: The 5-8 most ATS-critical phrases — terms a recruiter would search for. Use the JD's exact wording. Include both technical terms and domain phrases (e.g. "cross-functional collaboration", "stakeholder management", "data-driven decision making").
- outcome_signals: Read between the lines — what measurable outcomes does this role care about? Look for implicit performance metrics (e.g. if the JD says "optimize processes" → "cost reduction" or "efficiency gains"; if it says "grow the team" → "team scaling"; if it says "drive adoption" → "user adoption rate"). List 3-5 outcome themes.
- seniority_level: One of: internship, entry, mid, senior, lead, director, executive.
- domain: The industry/field (e.g., finance, technology, healthcare, consulting).
- company_values_mentioned: Any company values, culture aspects, or soft requirements mentioned.
- role_summary: A single sentence plain English summary of what the role actually does day-to-day.
"""


@retry_openai()
async def parse_jd(raw_jd_text: str) -> ParsedJD:
    """Parse a raw job description into structured data using GPT-4o."""
    client = get_openai_client()
    settings = get_settings()
    response = await client.beta.chat.completions.parse(
        model=settings.model_name,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this job description:\n\n{raw_jd_text}"},
        ],
        response_format=ParsedJD,
        temperature=settings.temp_parsing,
    )
    return response.choices[0].message.parsed
