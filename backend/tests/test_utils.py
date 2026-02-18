"""Tests for shared utility functions."""

from __future__ import annotations

import pytest

from backend.utils import extract_bullet_texts


class TestExtractBulletTexts:
    """Test bullet text extraction from various formats."""

    def test_list_of_strings(self):
        bullets = ["Built API", "Fixed bug", "Deployed service"]
        assert extract_bullet_texts(bullets) == ["Built API", "Fixed bug", "Deployed service"]

    def test_list_of_dicts(self):
        bullets = [
            {"text": "Built API", "domain_tags": ["backend"]},
            {"text": "Fixed bug", "domain_tags": ["maintenance"]},
        ]
        assert extract_bullet_texts(bullets) == ["Built API", "Fixed bug"]

    def test_mixed_list(self):
        bullets = [
            {"text": "Built API", "domain_tags": ["backend"]},
            "Fixed bug",
        ]
        assert extract_bullet_texts(bullets) == ["Built API", "Fixed bug"]

    def test_empty_list(self):
        assert extract_bullet_texts([]) == []

    def test_none_input(self):
        assert extract_bullet_texts(None) == []

    def test_dict_input_returns_empty(self):
        """Dict (non-list) input should return empty list."""
        assert extract_bullet_texts({"key": "value"}) == []

    def test_dict_with_missing_text_key(self):
        bullets = [{"description": "no text key"}, {"text": "has text"}]
        assert extract_bullet_texts(bullets) == ["", "has text"]
