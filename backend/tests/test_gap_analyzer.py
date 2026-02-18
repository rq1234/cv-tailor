"""Tests for the gap analyzer agent (data-in, data-out — no DB needed)."""

from __future__ import annotations

import pytest

from backend.agents.gap_analyzer import _build_exp_text


class TestBuildExpText:
    """Test the experience text builder used in gap analysis prompts."""

    def test_basic_experience(self, sample_experiences):
        text = _build_exp_text(sample_experiences)
        assert "Acme Corp" in text
        assert "Backend Engineer" in text
        assert "Built REST APIs" in text
        assert "StartupXYZ" in text

    def test_with_activities(self, sample_experiences, sample_activities):
        text = _build_exp_text(sample_experiences, sample_activities)
        assert "Tech Society" in text
        assert "(Activity)" in text
        assert "Led a team of 15" in text

    def test_empty_experiences(self):
        text = _build_exp_text([])
        assert text == ""

    def test_experience_with_string_bullets(self):
        exps = [
            {
                "company": "TestCo",
                "role_title": "Engineer",
                "bullets": ["Did thing A", "Did thing B"],
            }
        ]
        text = _build_exp_text(exps)
        assert "Did thing A" in text
        assert "Did thing B" in text

    def test_experience_with_empty_bullets(self):
        exps = [
            {
                "company": "TestCo",
                "role_title": "Engineer",
                "bullets": [],
            }
        ]
        text = _build_exp_text(exps)
        assert "TestCo" in text
