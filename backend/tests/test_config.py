"""Tests for config and settings loading."""

from __future__ import annotations

import pytest

from backend.config import Settings


def test_settings_defaults():
    """Settings should have sensible defaults even without env vars."""
    s = Settings(
        OPENAI_API_KEY="test-key",
        DATABASE_URL="postgresql+asyncpg://localhost/test",
    )
    assert s.model_name == "gpt-4o"
    assert s.embedding_model == "text-embedding-3-small"
    assert s.temp_parsing == 0.1
    assert s.near_duplicate_threshold == 0.92
    assert s.max_experiences == 6
    assert s.max_bullet_lines == 26
    assert s.bullet_min_chars == 90


def test_settings_cors_origins_default():
    """Default CORS origins should include localhost:3000."""
    s = Settings(
        OPENAI_API_KEY="test-key",
        DATABASE_URL="postgresql+asyncpg://localhost/test",
    )
    assert "http://localhost:3000" in s.cors_origins


def test_settings_override():
    """Settings can be overridden via constructor."""
    s = Settings(
        OPENAI_API_KEY="test-key",
        DATABASE_URL="postgresql+asyncpg://localhost/test",
        model_name="gpt-4o-mini",
        temp_parsing=0.5,
        max_experiences=10,
    )
    assert s.model_name == "gpt-4o-mini"
    assert s.temp_parsing == 0.5
    assert s.max_experiences == 10
