"""Shared service clients — single instances reused across the app."""

from __future__ import annotations

from functools import lru_cache

from openai import AsyncOpenAI

from backend.config import get_settings


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    """Return a cached singleton AsyncOpenAI client."""
    settings = get_settings()
    return AsyncOpenAI(api_key=settings.openai_api_key, timeout=60.0)
