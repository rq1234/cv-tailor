"""Shared utility functions used across the backend."""

from __future__ import annotations

import asyncio
import functools
import logging
import re
from typing import TypeVar

import openai

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_openai(
    max_retries: int = 3,
    backoff: float = 1.0,
):
    """Decorator that retries async OpenAI calls on transient errors.

    Retries on RateLimitError and APITimeoutError with exponential backoff.
    """
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return await fn(*args, **kwargs)
                except (openai.RateLimitError, openai.APITimeoutError) as exc:
                    last_exc = exc
                    wait = backoff * (2 ** attempt)
                    logger.warning(
                        "OpenAI %s on attempt %d/%d for %s — retrying in %.1fs",
                        type(exc).__name__, attempt + 1, max_retries, fn.__name__, wait,
                    )
                    await asyncio.sleep(wait)
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


def extract_bullet_texts(bullets_data) -> list[str]:
    """Extract plain text from a JSONB bullets field (list of dicts or strings)."""
    if not bullets_data:
        return []
    if isinstance(bullets_data, list):
        result = []
        for b in bullets_data:
            if isinstance(b, dict):
                result.append(b.get("text", ""))
            elif isinstance(b, str):
                result.append(b)
        return result
    return []


def split_description_to_bullets(description: str) -> list[str]:
    """Split a multi-sentence description into separate bullet points.

    Splits on sentence boundaries (period followed by space and uppercase letter).
    Used consistently across tailoring and export to avoid mismatches.
    """
    if not description or not description.strip():
        return []
    parts = re.split(r'(?<=\.)\s+(?=[A-Z])', description.strip())
    return [p.strip() for p in parts if p.strip()]
