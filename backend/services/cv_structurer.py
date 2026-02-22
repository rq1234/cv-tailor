"""GPT-4o CV structuring service — parses raw text into structured CV data."""

from __future__ import annotations

import hashlib
import logging

from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.clients import get_openai_client
from backend.config import get_settings
from backend.utils import retry_openai
from backend.schemas.pydantic import StructuredCvParse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — kept above 1 024 tokens so OpenAI's automatic prompt
# caching activates and halves the cost of the prompt on repeated calls.
# https://platform.openai.com/docs/guides/prompt-caching
# ---------------------------------------------------------------------------
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

Date edge cases:
- "Summer 2022" → date_start: 2022-06-01, date_end: 2022-08-31
- "2021 – 2023" (year only) → date_start: 2021-01-01, date_end: 2023-01-01
- "Sep 2020 – Present" → date_start: 2020-09-01, date_end: null, is_current: true
- If start date is missing but end date is present, leave date_start as null.
- Never invent dates that are not present in the source text.

Multi-role positions:
- If a person held multiple roles at the same company sequentially (e.g. "Analyst → Associate"), create a SEPARATE work_experience entry for each role with its own dates, bullets, and title.
- Only merge them if no role-level dates or bullets are distinguishable.

Bullet extraction:
- Strip leading bullet characters (•, -, *, ·, –) before storing the text.
- Preserve the full sentence including any quantified outcomes (percentages, dollar figures, headcounts).
- If a paragraph has no bullet characters but reads as a list of achievements, split it on sentence boundaries and treat each sentence as a bullet.
- Do not fabricate or paraphrase bullet content — copy exactly as written.

Domain tag examples by industry:
- Banking / finance: "investment banking", "equity research", "fixed income", "derivatives", "wealth management", "risk management", "compliance", "fintech"
- Tech: "software engineering", "machine learning", "data engineering", "devops", "cloud infrastructure", "cybersecurity", "product management"
- Consulting: "management consulting", "strategy", "operations", "due diligence", "market entry"
- Healthcare: "clinical research", "pharmaceutical", "biotech", "health informatics", "medical devices"
- Law: "corporate law", "litigation", "intellectual property", "regulatory"

Output quality checklist — before returning verify:
- Every work_experience and activity has at least one bullet (if bullets exist in the source text).
- No raw_block field is empty — it must contain the original text segment.
- Dates are valid ISO strings or null; never empty strings.
- Confidence scores are numbers between 0.0 and 1.0, not strings.
- Domain tags and skill_tags are non-empty arrays where content exists.
"""


# ---------------------------------------------------------------------------
# Internal OpenAI caller — retry decorator lives here only
# ---------------------------------------------------------------------------

@retry_openai()
async def _call_openai_parse(raw_text: str) -> StructuredCvParse:
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def structure_cv_text(
    raw_text: str,
    db: AsyncSession | None = None,
) -> StructuredCvParse:
    """Parse CV text with GPT-4o, served from DB cache when the same text was seen before.

    The cache key is SHA-256(raw_text). Parsing is deterministic at temperature 0
    so caching is safe. Cache writes are non-fatal — a failure just means the next
    identical upload will call the API again.
    """
    if len(raw_text) > 150_000:
        raise ValueError(
            f"CV text is too long ({len(raw_text):,} chars). "
            "Please upload a shorter document (max ~150 000 characters)."
        )

    text_hash = hashlib.sha256(raw_text.encode()).hexdigest()

    # ── Cache read ──────────────────────────────────────────────────────────
    if db is not None:
        try:
            row = await db.execute(
                sql_text("SELECT parsed_json FROM cv_parse_cache WHERE text_hash = :h"),
                {"h": text_hash},
            )
            cached = row.scalar_one_or_none()
            if cached:
                logger.info("cv_parse_cache hit for hash %s", text_hash[:12])
                return StructuredCvParse.model_validate_json(cached)
        except Exception:
            logger.warning("cv_parse_cache read failed — falling back to OpenAI", exc_info=True)

    # ── OpenAI call ─────────────────────────────────────────────────────────
    result = await _call_openai_parse(raw_text)

    # ── Cache write (non-fatal) ──────────────────────────────────────────────
    if db is not None:
        try:
            await db.execute(
                sql_text(
                    "INSERT INTO cv_parse_cache (text_hash, parsed_json) "
                    "VALUES (:h, :j) ON CONFLICT (text_hash) DO NOTHING"
                ),
                {"h": text_hash, "j": result.model_dump_json()},
            )
            # No commit here — caller owns the transaction
        except Exception:
            logger.warning("cv_parse_cache write failed — result still returned", exc_info=True)

    return result
