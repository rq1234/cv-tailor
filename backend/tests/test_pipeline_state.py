"""Tests for PipelineState model validation and defaults in backend/agents/graph.py."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.agents.graph import PipelineState


class TestPipelineStateDefaults:
    """Verify PipelineState Pydantic model has correct defaults."""

    def test_required_fields(self):
        state = PipelineState(application_id="app-1", user_id="user-1")
        assert state.application_id == "app-1"
        assert state.user_id == "user-1"

    def test_jd_raw_defaults_empty(self):
        state = PipelineState(application_id="a", user_id="u")
        assert state.jd_raw == ""

    def test_jd_parsed_defaults_empty_dict(self):
        state = PipelineState(application_id="a", user_id="u")
        assert state.jd_parsed == {}

    def test_selection_defaults_empty_dict(self):
        state = PipelineState(application_id="a", user_id="u")
        assert state.selection == {}

    def test_gap_analysis_defaults_empty_dict(self):
        state = PipelineState(application_id="a", user_id="u")
        assert state.gap_analysis == {}

    def test_tailored_experiences_defaults_empty_list(self):
        state = PipelineState(application_id="a", user_id="u")
        assert state.tailored_experiences == []

    def test_tailored_projects_defaults_empty_list(self):
        state = PipelineState(application_id="a", user_id="u")
        assert state.tailored_projects == []

    def test_tailored_activities_defaults_empty_list(self):
        state = PipelineState(application_id="a", user_id="u")
        assert state.tailored_activities == []

    def test_ats_result_defaults_empty_dict(self):
        state = PipelineState(application_id="a", user_id="u")
        assert state.ats_result == {}

    def test_cv_version_id_defaults_empty(self):
        state = PipelineState(application_id="a", user_id="u")
        assert state.cv_version_id == ""

    def test_current_step_defaults_pending(self):
        state = PipelineState(application_id="a", user_id="u")
        assert state.current_step == "pending"

    def test_error_defaults_none(self):
        state = PipelineState(application_id="a", user_id="u")
        assert state.error is None

    def test_max_pages_defaults_1(self):
        state = PipelineState(application_id="a", user_id="u")
        assert state.max_pages == 1

    def test_selection_mode_defaults_library(self):
        state = PipelineState(application_id="a", user_id="u")
        assert state.selection_mode == "library"


class TestPipelineStateAssignment:
    """Verify state fields can be assigned correctly."""

    def test_set_selection_mode_latest_cv(self):
        state = PipelineState(
            application_id="a", user_id="u", selection_mode="latest_cv"
        )
        assert state.selection_mode == "latest_cv"

    def test_set_max_pages_2(self):
        state = PipelineState(application_id="a", user_id="u", max_pages=2)
        assert state.max_pages == 2

    def test_set_error(self):
        state = PipelineState(application_id="a", user_id="u")
        state.error = "Something went wrong"
        assert state.error == "Something went wrong"

    def test_set_current_step(self):
        state = PipelineState(application_id="a", user_id="u")
        state.current_step = "tailoring_cv"
        assert state.current_step == "tailoring_cv"

    def test_set_jd_parsed(self):
        jd_data = {"role_summary": "Software Engineer", "required_skills": ["Python"]}
        state = PipelineState(application_id="a", user_id="u", jd_parsed=jd_data)
        assert state.jd_parsed == jd_data

    def test_set_selection_with_experiences(self):
        selection = {
            "selected_experiences": [{"id": "exp-1"}],
            "selected_projects": [],
            "selected_activities": [],
            "selected_education": [],
            "selected_skills": [],
        }
        state = PipelineState(application_id="a", user_id="u", selection=selection)
        assert state.selection["selected_experiences"][0]["id"] == "exp-1"

    def test_tailored_experiences_list(self):
        state = PipelineState(application_id="a", user_id="u")
        state.tailored_experiences = [
            {"experience_id": "exp-1", "suggested_bullets": ["Improved throughput"]}
        ]
        assert len(state.tailored_experiences) == 1

    def test_cv_version_id_set(self):
        state = PipelineState(application_id="a", user_id="u")
        state.cv_version_id = "version-uuid-here"
        assert state.cv_version_id == "version-uuid-here"


class TestPipelineStateIsolation:
    """Verify default mutable collections are independent between instances."""

    def test_lists_not_shared_between_instances(self):
        s1 = PipelineState(application_id="a", user_id="u")
        s2 = PipelineState(application_id="b", user_id="u")
        s1.tailored_experiences.append({"id": "x"})
        assert s2.tailored_experiences == []

    def test_dicts_not_shared_between_instances(self):
        s1 = PipelineState(application_id="a", user_id="u")
        s2 = PipelineState(application_id="b", user_id="u")
        s1.jd_parsed["key"] = "value"
        assert "key" not in s2.jd_parsed
