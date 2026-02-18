"""GPT-4o Vision service — extracts job description text from screenshots."""

from __future__ import annotations

import base64

from backend.clients import get_openai_client
from backend.config import get_settings
from backend.utils import retry_openai

SYSTEM_PROMPT = """\
You are an OCR assistant. The user will provide a screenshot image of a job description / job posting.
Extract ALL text from the image exactly as it appears, preserving the structure (headings, bullet points, paragraphs).
Return ONLY the extracted text — no commentary, no explanations, no markdown formatting beyond what exists in the image.
If the image does not appear to contain a job description, return the text anyway but prepend a single line:
[WARNING: This image may not contain a job description.]
"""


@retry_openai()
async def extract_text_from_screenshot(image_bytes: bytes, content_type: str) -> str:
    """Send a screenshot to GPT-4o Vision and return extracted text."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    media_type = content_type if content_type in ("image/png", "image/jpeg", "image/webp", "image/gif") else "image/png"

    client = get_openai_client()
    settings = get_settings()
    response = await client.chat.completions.create(
        model=settings.model_name,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all text from this job description screenshot:"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{b64}"},
                    },
                ],
            },
        ],
        temperature=settings.temp_parsing,
        max_tokens=4096,
    )

    return response.choices[0].message.content.strip()
