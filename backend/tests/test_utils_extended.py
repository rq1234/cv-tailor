"""Extended tests for backend.utils — covers split_description_to_bullets and retry_openai."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import openai
import pytest

from backend.utils import retry_openai, split_description_to_bullets


def _make_rate_limit_error() -> openai.RateLimitError:
    """Build an openai.RateLimitError with the required response mock."""
    mock_request = MagicMock()
    mock_response = MagicMock()
    mock_response.request = mock_request
    return openai.RateLimitError("Rate limited", response=mock_response, body=None)  # type: ignore[arg-type]


# ── split_description_to_bullets ─────────────────────────────────────────────

class TestSplitDescriptionToBullets:
    def test_empty_string(self):
        assert split_description_to_bullets("") == []

    def test_none_returns_empty(self):
        assert split_description_to_bullets(None) == []  # type: ignore[arg-type]

    def test_whitespace_only(self):
        assert split_description_to_bullets("   ") == []

    def test_single_sentence(self):
        result = split_description_to_bullets("Built REST APIs using FastAPI.")
        assert result == ["Built REST APIs using FastAPI."]

    def test_two_sentences(self):
        result = split_description_to_bullets(
            "Built REST APIs using FastAPI. Reduced latency by 40%."
        )
        assert len(result) == 2
        assert result[0] == "Built REST APIs using FastAPI."
        assert result[1] == "Reduced latency by 40%."

    def test_three_sentences(self):
        result = split_description_to_bullets(
            "Designed the database. Built the API. Deployed to AWS."
        )
        assert len(result) == 3

    def test_strips_leading_trailing_whitespace(self):
        result = split_description_to_bullets(
            "  Sentence one.  Sentence two.  "
        )
        for s in result:
            assert s == s.strip()

    def test_sentence_starting_lowercase_not_split(self):
        # Split only on ". [UpperCase]", so "e.g. something" stays together
        text = "Used Python e.g. for scripting. Deployed to AWS."
        result = split_description_to_bullets(text)
        # Should have 2 parts, not split at "e.g."
        assert len(result) == 2

    def test_no_period_single_bullet(self):
        text = "Built APIs using FastAPI and deployed to AWS"
        result = split_description_to_bullets(text)
        assert result == [text]

    def test_filters_empty_parts(self):
        # Edge case: trailing period doesn't create empty bullet
        result = split_description_to_bullets("Did something.")
        assert all(s.strip() for s in result)


# ── retry_openai ──────────────────────────────────────────────────────────────

class TestRetryOpenAI:
    """Test the retry decorator for transient OpenAI errors."""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        @retry_openai(max_retries=3)
        async def fn():
            return "result"

        assert await fn() == "result"

    @pytest.mark.asyncio
    async def test_retries_on_rate_limit(self):
        call_count = 0

        @retry_openai(max_retries=3, backoff=0.001)
        async def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise _make_rate_limit_error()
            return "ok"

        result = await fn()
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self):
        call_count = 0

        @retry_openai(max_retries=3, backoff=0.001)
        async def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise openai.APITimeoutError(request=None)  # type: ignore[arg-type]
            return "ok"

        result = await fn()
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        @retry_openai(max_retries=2, backoff=0.001)
        async def fn():
            raise _make_rate_limit_error()

        with pytest.raises(openai.RateLimitError):
            await fn()

    @pytest.mark.asyncio
    async def test_does_not_retry_unexpected_errors(self):
        call_count = 0

        @retry_openai(max_retries=3, backoff=0.001)
        async def fn():
            nonlocal call_count
            call_count += 1
            raise ValueError("Unexpected error")

        with pytest.raises(ValueError):
            await fn()

        assert call_count == 1  # No retries for non-OpenAI errors

    @pytest.mark.asyncio
    async def test_preserves_return_value(self):
        expected = {"key": "value", "number": 42}

        @retry_openai(max_retries=1)
        async def fn():
            return expected

        result = await fn()
        assert result == expected

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        @retry_openai()
        async def my_special_function():
            return "x"

        assert my_special_function.__name__ == "my_special_function"
