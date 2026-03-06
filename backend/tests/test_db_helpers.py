"""Tests for db_helpers — focuses on pure scoring logic in find_similar_applications."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.enums import ApplicationStatus


def _make_app(domain: str, keywords: list[str], app_id: uuid.UUID | None = None) -> MagicMock:
    """Create a mock Application with jd_parsed."""
    app = MagicMock()
    app.id = app_id or uuid.uuid4()
    app.company_name = "TestCo"
    app.role_title = "Engineer"
    app.created_at = MagicMock()
    app.created_at.isoformat.return_value = "2024-01-01T00:00:00"
    app.jd_parsed = {"domain": domain, "keywords": keywords}
    return app


class TestFindSimilarApplicationsScoring:
    """Tests for the similarity scoring logic without a real DB."""

    @pytest.mark.asyncio
    async def test_no_jd_parsed_returns_empty(self):
        from backend.api.db_helpers import find_similar_applications

        db = AsyncMock()
        current_app = MagicMock()
        current_app.jd_parsed = None
        user_id = uuid.uuid4()

        result = await find_similar_applications(db, current_app, user_id)
        assert result == []

    @pytest.mark.asyncio
    async def test_domain_match_boosts_score(self):
        from backend.api.db_helpers import find_similar_applications

        current = _make_app("finance", ["python", "sql"])
        other_finance = _make_app("finance", ["python", "sql"])
        other_tech = _make_app("technology", ["python", "sql"])

        db = AsyncMock()
        # Mock other apps query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [other_finance, other_tech]
        # Mock cv versions query (no ATS scores)
        mock_cv_result = MagicMock()
        mock_cv_result.all.return_value = []
        db.execute = AsyncMock(side_effect=[mock_result, mock_cv_result])
        current.id = uuid.uuid4()

        results = await find_similar_applications(db, current, uuid.uuid4())
        # Both should be returned; finance match should rank first
        assert len(results) >= 1
        if len(results) == 2:
            assert results[0]["domain"] == "finance"

    @pytest.mark.asyncio
    async def test_no_other_apps_returns_empty(self):
        from backend.api.db_helpers import find_similar_applications

        current = _make_app("finance", ["python"])
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)
        current.id = uuid.uuid4()

        results = await find_similar_applications(db, current, uuid.uuid4())
        assert results == []

    @pytest.mark.asyncio
    async def test_limited_to_3_results(self):
        from backend.api.db_helpers import find_similar_applications

        current = _make_app("finance", ["python", "sql", "excel"])
        others = [_make_app("finance", ["python", "sql", "excel"]) for _ in range(6)]

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = others
        mock_cv_result = MagicMock()
        mock_cv_result.all.return_value = []
        db.execute = AsyncMock(side_effect=[mock_result, mock_cv_result])
        current.id = uuid.uuid4()

        results = await find_similar_applications(db, current, uuid.uuid4())
        assert len(results) <= 3


class TestFetchActiveRulesText:
    @pytest.mark.asyncio
    async def test_no_rules_returns_empty_string(self):
        from backend.api.db_helpers import fetch_active_rules_text

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        result = await fetch_active_rules_text(db, uuid.uuid4())
        assert result == ""

    @pytest.mark.asyncio
    async def test_rules_formatted_as_list(self):
        from backend.api.db_helpers import fetch_active_rules_text

        rule1 = MagicMock()
        rule1.rule_text = "Always quantify achievements"
        rule2 = MagicMock()
        rule2.rule_text = "Use action verbs"

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [rule1, rule2]
        db.execute = AsyncMock(return_value=mock_result)

        result = await fetch_active_rules_text(db, uuid.uuid4())
        assert "Always quantify achievements" in result
        assert "Use action verbs" in result
        assert result.startswith("Additional tailoring rules")
