"""GPT-4o CV structuring service — parses raw text into structured CV data."""

from __future__ import annotations

from backend.clients import get_openai_client
from backend.config import get_settings
from backend.utils import retry_openai
from backend.schemas.pydantic import StructuredCvParse

SYSTEM_PROMPT = """\
You are a CV/resume parser. Given raw text extracted from a CV document, extract all structured information.

Section name mapping — treat these as equivalent:
- work_experiences: "Work Experience", "Professional Experience", "Employment"
- activities: "Leadership", "Leadership Experience", "Extracurricular", "Extracurricular Activities", "Volunteering", "Volunteer Experience", "Activities", "Positions of Responsibility"
- education: "Education", "Academic Background", "Qualifications"
- projects: "Projects", "Personal Projects", "Academic Projects", "Research"
- skills: "Skills", "Skills & Interests", "Technical Skills", "Core Competencies", "Certifications", "Certifications & Skills", "Languages"

IMPORTANT: Do NOT put items in unclassified_blocks if they clearly fit one of the above categories. Only use unclassified_blocks for genuinely ambiguous content.

Rules:
- Extract every field you can identify. For fields you're uncertain about, still include them but set the confidence score lower.
- Confidence scores are 0-1. Use 1.0 for clearly extracted fields, lower for ambiguous ones.
- For dates, use ISO format (YYYY-MM-DD). If only month/year, use the 1st of the month. If only year, use Jan 1.
- If a date says "Present" or "Current", set is_current=true and leave date_end as null.
- Keep raw_block as the exact original text for each section — never modify it.
- For bullets, extract each bullet point as a separate item with its text.
- Classify skills into categories: technical, language, tool, soft, other, certification, framework, interest.
- For "Skills & Interests" or "Additional Information" sections: extract skills as skills, languages as category "language", and hobbies/interests (e.g. Taekwondo, Hiking, Volunteering, Calligraphy) as skills with category "interest".
- For "Interests", "Hobbies", "Hobbies & Interests" sections: extract each interest as a skill with category "interest".
- If a block of text doesn't fit any category, put it in unclassified_blocks with your best guess.
- For education entries: extract relevant coursework, modules, and honors/awards. Put coursework and module lists into the "modules" field. Put achievements, honors, GPA, awards, thesis titles, and other notable items into the "achievements" field. If the education section has bullet points, extract them as achievements.
- Domain tags: assign MULTIPLE granular tags per experience. Use specific sub-domains, not just broad categories. Examples: ["asset management", "fintech"], ["management consulting", "strategy"], ["quantitative trading", "finance"], ["machine learning", "healthcare"]. An experience can span multiple domains.
- Skill tags should capture specific technical skills and technologies mentioned in each experience, project, and activity. For projects especially, extract the tech stack (e.g. ["Python", "Flask", "React", "PostgreSQL"]) into skill_tags.
- Activities use the same field names as work_experiences (company = organization name, role_title = role/position). Each activity entry within a section (e.g. multiple clubs under "Leadership") should be a SEPARATE activity item.
"""


@retry_openai()
async def structure_cv_text(raw_text: str) -> StructuredCvParse:
    """Call GPT-4o with structured output to parse CV text into structured data."""
    client = get_openai_client()
    settings = get_settings()
    response = await client.beta.chat.completions.parse(
        model=settings.model_name,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this CV:\n\n{raw_text}"},
        ],
        response_format=StructuredCvParse,
        temperature=settings.temp_parsing,
    )

    return response.choices[0].message.parsed
