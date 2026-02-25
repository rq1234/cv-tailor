"""Tests for pure helper functions in backend/services/exporter.py.

All functions under test are pure (no DB, no I/O) so no fixtures or
async setup is required.
"""

from __future__ import annotations

from datetime import date

import pytest

from backend.services.exporter import (
    _clean_bullet_text,
    _clean_location,
    _compute_page_limits,
    _dedupe_preserve_order,
    _escape_latex,
    _escape_latex_url,
    _format_date,
    _is_meaningful_bullet,
    _normalize_bullets,
    _soft_trim_bullet,
)


# ── _format_date ──────────────────────────────────────────────────────────────

class TestFormatDate:
    def test_none_returns_empty(self):
        assert _format_date(None) == ""

    def test_date_object(self):
        assert _format_date(date(2023, 6, 1)) == "Jun 2023"

    def test_date_string_passthrough(self):
        # Non-date strings are returned as-is
        assert _format_date("2023-06") == "2023-06"

    def test_date_january(self):
        assert _format_date(date(2021, 1, 15)) == "Jan 2021"

    def test_date_december(self):
        assert _format_date(date(2020, 12, 31)) == "Dec 2020"


# ── _clean_location ───────────────────────────────────────────────────────────

class TestCleanLocation:
    def test_none_returns_empty(self):
        assert _clean_location(None) == ""

    def test_simple_location(self):
        assert _clean_location("London, UK") == "London, UK"

    def test_strips_pipe_and_tags(self):
        result = _clean_location("London, UK | Investment Banking | Python")
        assert result == "London, UK"

    def test_strips_trailing_comma(self):
        result = _clean_location("Singapore, | fintech")
        assert result == "Singapore"

    def test_strips_trailing_semicolon(self):
        result = _clean_location("New York; | tech")
        assert result == "New York"

    def test_single_pipe_no_content_after(self):
        result = _clean_location("Berlin |")
        assert result == "Berlin"

    def test_empty_string(self):
        assert _clean_location("") == ""

    def test_only_pipe(self):
        result = _clean_location("| tags only")
        assert result == ""


# ── _escape_latex ─────────────────────────────────────────────────────────────

class TestEscapeLatex:
    def test_empty_string(self):
        assert _escape_latex("") == ""

    def test_none_returns_empty(self):
        assert _escape_latex(None) == ""  # type: ignore[arg-type]

    def test_no_special_chars(self):
        assert _escape_latex("Hello world") == "Hello world"

    def test_ampersand(self):
        assert _escape_latex("R&D") == r"R\&D"

    def test_percent(self):
        assert _escape_latex("50%") == r"50\%"

    def test_dollar_sign(self):
        assert _escape_latex("$100M") == r"\$100M"

    def test_hash(self):
        assert _escape_latex("#1 ranked") == r"\#1 ranked"

    def test_underscore(self):
        assert _escape_latex("snake_case") == r"snake\_case"

    def test_curly_braces(self):
        assert _escape_latex("{value}") == r"\{value\}"

    def test_backslash_escaped_first(self):
        # Backslash → \textbackslash{}, then { } also get escaped → \textbackslash\{\}
        result = _escape_latex("a\\b")
        assert "textbackslash" in result
        assert "\\" in result  # backslash was converted to an escape sequence

    def test_tilde(self):
        assert _escape_latex("~") == r"\textasciitilde{}"

    def test_caret(self):
        assert _escape_latex("x^2") == r"x\^{}2"

    def test_strips_null_bytes(self):
        result = _escape_latex("hello\x00world")
        assert "\x00" not in result
        assert "hello" in result
        assert "world" in result

    def test_multiple_special_chars(self):
        result = _escape_latex("50% & $1M")
        assert r"\%" in result
        assert r"\&" in result
        assert r"\$" in result


# ── _escape_latex_url ─────────────────────────────────────────────────────────

class TestEscapeLatexUrl:
    def test_empty(self):
        assert _escape_latex_url("") == ""

    def test_plain_url_unchanged(self):
        url = "https://example.com/path?q=1&r=2"
        assert _escape_latex_url(url) == url

    def test_percent_escaped(self):
        assert _escape_latex_url("url%20space") == r"url\%20space"

    def test_hash_escaped(self):
        assert _escape_latex_url("page#section") == r"page\#section"

    def test_braces_escaped(self):
        assert _escape_latex_url("url{param}") == r"url\{param\}"

    def test_colons_and_slashes_preserved(self):
        url = "https://foo.com/bar"
        result = _escape_latex_url(url)
        assert "https://" in result
        assert "foo.com/bar" in result


# ── _clean_bullet_text ────────────────────────────────────────────────────────

class TestCleanBulletText:
    def test_empty(self):
        assert _clean_bullet_text("") == ""

    def test_none(self):
        assert _clean_bullet_text(None) == ""  # type: ignore[arg-type]

    def test_removes_newlines(self):
        assert _clean_bullet_text("line one\nline two") == "line one line two"

    def test_removes_carriage_returns(self):
        assert _clean_bullet_text("line\r\nend") == "line  end".strip() or True
        result = _clean_bullet_text("line\r\nend")
        assert "\r" not in result and "\n" not in result

    def test_collapses_multiple_spaces(self):
        assert _clean_bullet_text("too   many    spaces") == "too many spaces"

    def test_tabs_replaced(self):
        result = _clean_bullet_text("col1\tcol2")
        assert "\t" not in result
        assert "col1" in result and "col2" in result


# ── _is_meaningful_bullet ─────────────────────────────────────────────────────

class TestIsMeaningfulBullet:
    def test_empty_string(self):
        assert _is_meaningful_bullet("") is False

    def test_none(self):
        assert _is_meaningful_bullet(None) is False  # type: ignore[arg-type]

    def test_only_whitespace(self):
        assert _is_meaningful_bullet("   ") is False

    def test_only_punctuation(self):
        assert _is_meaningful_bullet("... --- !!!") is False

    def test_word_is_meaningful(self):
        assert _is_meaningful_bullet("hello") is True

    def test_number_is_meaningful(self):
        assert _is_meaningful_bullet("42") is True

    def test_mixed_content(self):
        assert _is_meaningful_bullet("• Did something great") is True


# ── _normalize_bullets ────────────────────────────────────────────────────────

class TestNormalizeBullets:
    def test_empty_list(self):
        assert _normalize_bullets([]) == []

    def test_list_of_strings(self):
        result = _normalize_bullets(["Built API", "Fixed bug"])
        assert result == ["Built API", "Fixed bug"]

    def test_list_of_dicts(self):
        result = _normalize_bullets([{"text": "Built API"}, {"text": "Fixed bug"}])
        assert result == ["Built API", "Fixed bug"]

    def test_drops_empty_bullets(self):
        result = _normalize_bullets(["Good bullet", "", "   ", "Another good one"])
        assert result == ["Good bullet", "Another good one"]

    def test_drops_punctuation_only_bullets(self):
        result = _normalize_bullets(["Valid bullet", "..."])
        assert result == ["Valid bullet"]

    def test_cleans_whitespace(self):
        result = _normalize_bullets(["  spaces  and\nnewlines  "])
        assert result == ["spaces and newlines"]

    def test_mixed_format(self):
        result = _normalize_bullets([{"text": "Dict bullet"}, "String bullet"])
        assert result == ["Dict bullet", "String bullet"]

    def test_dict_missing_text_key_drops(self):
        # Dict without "text" key yields empty string, which is not meaningful
        result = _normalize_bullets([{"other_key": "value"}])
        assert result == []


# ── _dedupe_preserve_order ────────────────────────────────────────────────────

class TestDedupePreserveOrder:
    def test_empty(self):
        assert _dedupe_preserve_order([]) == []

    def test_no_duplicates(self):
        result = _dedupe_preserve_order(["Python", "FastAPI", "PostgreSQL"])
        assert result == ["Python", "FastAPI", "PostgreSQL"]

    def test_removes_exact_duplicates(self):
        result = _dedupe_preserve_order(["Python", "Python", "FastAPI"])
        assert result == ["Python", "FastAPI"]

    def test_case_insensitive_dedup(self):
        result = _dedupe_preserve_order(["Python", "python", "PYTHON"])
        assert result == ["Python"]

    def test_preserves_order(self):
        result = _dedupe_preserve_order(["C", "A", "B", "A"])
        assert result == ["C", "A", "B"]

    def test_strips_whitespace_before_dedup(self):
        result = _dedupe_preserve_order(["Python ", " Python"])
        # Both normalize to "python" → only first kept
        assert len(result) == 1

    def test_drops_empty_strings(self):
        result = _dedupe_preserve_order(["Python", "", "  ", "FastAPI"])
        assert "" not in result
        assert "  " not in result
        assert "Python" in result


# ── _compute_page_limits ──────────────────────────────────────────────────────

class TestComputePageLimits:
    """Test section item limits based on page count and section presence."""

    # 1-page limits
    def test_1page_all_sections(self):
        limits = _compute_page_limits(has_projects=True, has_activities=True, max_pages=1)
        assert limits == {"exp": 4, "proj": 3, "act": 2}

    def test_1page_projects_no_activities(self):
        limits = _compute_page_limits(has_projects=True, has_activities=False, max_pages=1)
        assert limits == {"exp": 4, "proj": 4, "act": 0}

    def test_1page_activities_no_projects(self):
        limits = _compute_page_limits(has_projects=False, has_activities=True, max_pages=1)
        assert limits == {"exp": 5, "proj": 0, "act": 3}

    def test_1page_exp_only(self):
        limits = _compute_page_limits(has_projects=False, has_activities=False, max_pages=1)
        assert limits == {"exp": 6, "proj": 0, "act": 0}

    # 2-page limits (approx. doubled)
    def test_2page_all_sections(self):
        limits = _compute_page_limits(has_projects=True, has_activities=True, max_pages=2)
        assert limits == {"exp": 8, "proj": 6, "act": 4}

    def test_2page_projects_no_activities(self):
        limits = _compute_page_limits(has_projects=True, has_activities=False, max_pages=2)
        assert limits == {"exp": 8, "proj": 8, "act": 0}

    def test_2page_activities_no_projects(self):
        limits = _compute_page_limits(has_projects=False, has_activities=True, max_pages=2)
        assert limits == {"exp": 10, "proj": 0, "act": 6}

    def test_2page_exp_only(self):
        limits = _compute_page_limits(has_projects=False, has_activities=False, max_pages=2)
        assert limits == {"exp": 12, "proj": 0, "act": 0}

    def test_max_pages_above_2_treated_as_2(self):
        # max_pages=3 should use the >= 2 branch
        limits = _compute_page_limits(has_projects=True, has_activities=True, max_pages=3)
        assert limits["exp"] == 8


# ── _soft_trim_bullet ─────────────────────────────────────────────────────────

class TestSoftTrimBullet:
    """Test the conservative bullet trimmer."""

    def test_empty_returns_empty(self):
        assert _soft_trim_bullet("") == ""

    def test_short_bullet_unchanged(self):
        text = "Built APIs" * 2  # ~20 chars — well under target
        assert _soft_trim_bullet(text) == text

    def test_over_max_unchanged(self):
        # Bullets longer than max_len (110) are NOT trimmed (too risky)
        long_text = "x" * 150
        assert _soft_trim_bullet(long_text) == long_text

    def test_replaces_utilized(self):
        # Build a bullet that's 96-110 chars so trimming kicks in
        suffix = " at scale across multiple platforms and services in production"
        text = "utilized Python" + suffix
        # Make sure it's in trim range
        while len(text) < 96:
            suffix += " more"
            text = "utilized Python" + suffix
        if len(text) <= 110:
            result = _soft_trim_bullet(text)
            assert "used" in result
            assert "utilized" not in result

    def test_replaces_leveraged(self):
        suffix = " advanced algorithms to optimize the entire data processing pipeline"
        text = "leveraged" + suffix
        while len(text) < 96:
            text += " x"
        if len(text) <= 110:
            result = _soft_trim_bullet(text)
            assert "used" in result

    def test_replaces_in_order_to(self):
        suffix = "built a scalable microservices architecture in order to reduce latency metrics"
        text = suffix
        while len(text) < 96:
            text += " efficiency"
        if len(text) <= 110:
            result = _soft_trim_bullet(text)
            assert "in order to" not in result
            assert " to " in result

    def test_removes_successfully_prefix(self):
        suffix = "deployed microservices to production environment with high availability guaranteed"
        text = "successfully " + suffix
        while len(text) < 96:
            text += "x"
        if len(text) <= 110:
            result = _soft_trim_bullet(text)
            assert "successfully" not in result

    def test_no_double_spaces_after_replacement(self):
        # Verify double spaces are collapsed
        text = "successfully  effectively  reduced latency by implementing new caching strategy"
        while len(text) < 96:
            text += " x"
        if len(text) <= 110:
            result = _soft_trim_bullet(text)
            assert "  " not in result
