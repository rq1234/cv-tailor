"""Agent: Check ATS compliance of the assembled tailored CV."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.clients import get_openai_client
from backend.config import get_settings
from backend.utils import retry_openai


class AtsWarning(BaseModel):
    field: str
    issue: str
    suggestion: str


class AtsCheckResult(BaseModel):
    warnings: list[AtsWarning] = Field(default_factory=list)
    ats_score: int = Field(ge=0, le=100)


SYSTEM_PROMPT = """\
You are an ATS (Applicant Tracking System) compliance checker for CVs/resumes.

Analyze the provided CV JSON and check for issues that could cause ATS systems to misparse or reject the CV.

Check for and flag:
1. Non-standard section headings (should use: Experience, Education, Skills, Projects)
2. Missing standard sections (Experience, Education, Skills are mandatory)
3. Inconsistent date formats (should all use the same format, e.g., "Jan 2023" or "2023-01")
4. Special characters that ATS systems commonly misread (fancy quotes, em-dashes, bullets other than •)
5. Bullet points exceeding ~150 characters (too long for ATS parsing — roughly 2 lines)
6. Skills section absent or buried below other sections
7. Missing contact information (name, email, phone)
8. Excessive formatting indicators that suggest complex layouts

Return a list of specific, actionable warnings and an overall ATS score (0-100).
A score of 90+ means highly ATS-compatible. Below 70 needs significant fixes.
"""


@retry_openai()
async def check_ats_compliance(cv_json: dict) -> AtsCheckResult:
    """Check ATS compliance of a CV JSON structure using GPT-4o."""
    import json

    cv_text = json.dumps(cv_json, indent=2, default=str)

    client = get_openai_client()
    settings = get_settings()
    response = await client.beta.chat.completions.parse(
        model=settings.model_name,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Check this CV for ATS compliance:\n\n{cv_text}"},
        ],
        response_format=AtsCheckResult,
        temperature=settings.temp_parsing,
    )

    return response.choices[0].message.parsed
