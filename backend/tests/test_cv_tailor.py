"""Comprehensive tests for backend.agents.cv_tailor.

Covers all helper functions, all brief tiers, edge cases, and async tailoring
functions (with mocked OpenAI API so no real calls are made).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.cv_tailor import (
    BulletBrief,
    TailoredExperience,
    TailoredProject,
    TailoredActivity,
    _APR_RESULT_PHRASES,
    _assign_keywords_to_bullets,
    _best_req,
    _build_bullet_briefs,
    _bullet_weakness,
    _compute_experience_focus,
    _diagnose_apr,
    _find_redundant_pairs,
    _get_seniority_note,
    _has_hallucinated_numbers,
    _jd_relevance_score,
    _keyword_in_text,
    _score_bullet_candidate,
    _similarity,
    _tailor_one_bullet,
    tailor_experiences,
    tailor_projects,
    tailor_activities,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def jd_tech():
    return {
        "role_summary": "Senior Software Engineer",
        "domain": "technology",
        "seniority_level": "senior",
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "key_responsibilities": [
            "Design and build scalable REST APIs",
            "Optimise database query performance",
            "Write unit and integration tests",
        ],
        "keywords": ["backend", "microservices", "CI/CD"],
        "nice_to_have_skills": ["Kubernetes"],
        "outcome_signals": ["latency reduction", "throughput improvement"],
        "tools_and_technologies": ["AWS", "Docker"],
    }


@pytest.fixture
def jd_quant():
    return {
        "role_summary": "Quantitative Analyst",
        "domain": "quantitative finance",
        "seniority_level": "mid",
        "required_skills": ["Python", "statistics", "backtesting", "pandas"],
        "key_responsibilities": [
            "Research and develop alpha-generating strategies",
            "Backtest strategies on historical tick data",
            "Build risk models and performance attribution",
        ],
        "keywords": ["Sharpe ratio", "factor model", "signal research"],
        "nice_to_have_skills": ["C++", "kdb+"],
        "outcome_signals": ["Sharpe ratio", "alpha", "max drawdown"],
        "tools_and_technologies": ["Python", "pandas", "numpy"],
    }


@pytest.fixture
def jd_empty():
    """JD with no keywords — neutral scoring."""
    return {
        "role_summary": "Unknown Role",
        "domain": "",
        "seniority_level": "",
        "required_skills": [],
        "key_responsibilities": [],
        "keywords": [],
        "nice_to_have_skills": [],
        "outcome_signals": [],
        "tools_and_technologies": [],
    }


def _make_openai_response(*texts: str):
    """Build a mock OpenAI response with n choices."""
    choices = [
        MagicMock(message=MagicMock(content=t))
        for t in texts
    ]
    response = MagicMock()
    response.choices = choices
    return response


def _make_async_client(*response_texts: str):
    """Mock OpenAI async client that returns the given texts as n=2 candidates."""
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(
        return_value=_make_openai_response(*response_texts)
    )
    return client


def _make_settings(model="gpt-4o-mini", temp=0.72):
    s = MagicMock()
    s.model_name = model
    s.temp_tailoring = temp
    return s


# ── _diagnose_apr ─────────────────────────────────────────────────────────────

class TestDiagnoseApr:
    def test_strong_bullet_has_all_components(self):
        b = "Built Python ETL pipeline ingesting 50 GB daily, reducing latency by 40%"
        apr = _diagnose_apr(b)
        assert apr["action_verb"] is True
        assert apr["scope"] is True
        assert apr["result"] is True

    def test_weak_start_no_action_verb(self):
        b = "Responsible for building Python services that processed 1M rows"
        apr = _diagnose_apr(b)
        assert apr["action_verb"] is False

    def test_short_bullet_no_scope(self):
        b = "Built a tool"
        apr = _diagnose_apr(b)
        assert apr["scope"] is False

    def test_no_result_no_numbers_no_outcome_verb(self):
        b = "Developed and maintained the internal Python microservices codebase"
        apr = _diagnose_apr(b)
        assert apr["result"] is False

    def test_result_via_number(self):
        b = "Deployed Docker containers, handling 500 requests per second"
        apr = _diagnose_apr(b)
        assert apr["result"] is True

    def test_result_via_phrase(self):
        b = "Refactored legacy authentication module, improving code coverage across services"
        apr = _diagnose_apr(b)
        assert apr["result"] is True

    def test_empty_bullet(self):
        apr = _diagnose_apr("")
        assert apr == {"action_verb": False, "scope": False, "result": False}

    def test_single_word(self):
        apr = _diagnose_apr("Python")
        assert apr["scope"] is False

    def test_weak_verb_detected(self):
        # _diagnose_apr checks _WEAK_STARTS (phrases) and _WEAK_VERBS (exact base forms)
        b = "Responsible for implementing microservices architecture for backend systems"
        apr = _diagnose_apr(b)
        assert apr["action_verb"] is False


# ── _get_seniority_note ───────────────────────────────────────────────────────

class TestGetSeniorityNote:
    @pytest.mark.parametrize("level", ["director", "executive", "lead", "vp", "head"])
    def test_director_level(self, level):
        note = _get_seniority_note(level)
        assert "Architected" in note or "Led" in note
        assert "strategic" in note.lower()

    def test_senior_level(self):
        note = _get_seniority_note("senior")
        assert "ownership" in note.lower()
        assert "Championed" in note or "Owned" in note

    @pytest.mark.parametrize("level", ["internship", "entry", "junior", "graduate"])
    def test_entry_level(self, level):
        note = _get_seniority_note(level)
        assert "Built" in note or "Implemented" in note

    def test_mid_level_empty(self):
        assert _get_seniority_note("mid") == ""
        assert _get_seniority_note("") == ""

    def test_case_insensitive(self):
        assert _get_seniority_note("SENIOR") == _get_seniority_note("senior")
        assert _get_seniority_note("Director") == _get_seniority_note("director")


# ── _score_bullet_candidate ───────────────────────────────────────────────────

class TestScoreBulletCandidate:
    def test_keyword_in_first_six_scores_higher(self):
        kws = ["Python", "FastAPI"]
        early = "Python FastAPI service handling requests at scale"
        late = "Built a high-throughput service using Python and FastAPI"
        assert _score_bullet_candidate(early, kws) > _score_bullet_candidate(late, kws)

    def test_empty_text_returns_negative(self):
        assert _score_bullet_candidate("", ["Python"]) < 0

    def test_has_result_bonus(self):
        kws = ["Python"]
        with_result = "Built Python pipeline reducing latency by 40%"
        without_result = "Built Python pipeline for data ingestion tasks"
        assert _score_bullet_candidate(with_result, kws) > _score_bullet_candidate(without_result, kws)

    def test_placeholder_bonus(self):
        kws = ["Python"]
        with_ph = "Built Python pipeline reducing latency by [X]"
        without_ph = "Built Python pipeline for data ingestion tasks"
        assert _score_bullet_candidate(with_ph, kws) > _score_bullet_candidate(without_ph, kws)

    def test_good_length_bonus(self):
        kws: list[str] = []
        short = "Built a tool"
        good = "Built and deployed a Python microservice handling 10K daily requests"
        assert _score_bullet_candidate(good, kws) > _score_bullet_candidate(short, kws)

    def test_no_keywords_still_scores_on_other_signals(self):
        score = _score_bullet_candidate("Implemented system reducing errors by 30%", [])
        assert score > 0  # has result + good length

    def test_empty_keywords_list(self):
        score = _score_bullet_candidate("Built FastAPI service", [])
        assert isinstance(score, float)


# ── _compute_experience_focus ─────────────────────────────────────────────────

class TestComputeExperienceFocus:
    def test_single_experience_gets_all_requirements(self, jd_tech):
        exps = [{"id": "exp-1", "bullets": [{"text": "Built Python API"}]}]
        focus = _compute_experience_focus(exps, jd_tech)
        assert set(focus["exp-1"]) == set(jd_tech["key_responsibilities"])

    def test_empty_requirements_returns_empty_lists(self):
        exps = [
            {"id": "exp-1", "bullets": [{"text": "Built Python API"}]},
            {"id": "exp-2", "bullets": [{"text": "Managed AWS infrastructure"}]},
        ]
        jd = {"key_responsibilities": []}
        focus = _compute_experience_focus(exps, jd)
        assert focus["exp-1"] == []
        assert focus["exp-2"] == []

    def test_two_experiences_split_responsibilities(self, jd_tech):
        exps = [
            {"id": "exp-1", "bullets": [{"text": "Built REST APIs with FastAPI and PostgreSQL"}]},
            {"id": "exp-2", "bullets": [{"text": "Wrote unit tests and integration tests with pytest"}]},
        ]
        focus = _compute_experience_focus(exps, jd_tech)
        # Each requirement is assigned to exactly one experience
        all_assigned = focus["exp-1"] + focus["exp-2"]
        for req in jd_tech["key_responsibilities"]:
            assert req in all_assigned

    def test_experience_with_no_coverage_gets_all_requirements(self, jd_tech):
        # exp-2 has completely unrelated bullets → should get all requirements as fallback
        # Use short bullets so SequenceMatcher ratio favours exp-1 for each requirement
        exps = [
            {"id": "exp-1", "bullets": [
                {"text": "Design and build scalable REST APIs"},
                {"text": "Optimise database query performance"},
                {"text": "Write unit and integration tests"},
            ]},
            {"id": "exp-2", "bullets": [{"text": "Commanded platoon in combat"}]},
        ]
        focus = _compute_experience_focus(exps, jd_tech)
        # exp-2 wins no requirements → fallback to all requirements
        assert len(focus["exp-2"]) == len(jd_tech["key_responsibilities"])

    def test_no_experiences_returns_empty_dict(self, jd_tech):
        focus = _compute_experience_focus([], jd_tech)
        assert focus == {}


# ── _assign_keywords_to_bullets ───────────────────────────────────────────────

class TestAssignKeywords:
    def test_already_present_keyword_skipped(self):
        bullets = ["Built Python microservices using FastAPI"]
        assignment = _assign_keywords_to_bullets(bullets, ["Python"])
        assert "Python" not in assignment.get(0, [])

    def test_zero_fit_score_not_assigned(self):
        # "Black-Scholes" has zero word overlap with a Python engineering bullet
        bullets = ["Built Python microservices using FastAPI and PostgreSQL"]
        assignment = _assign_keywords_to_bullets(bullets, ["Black-Scholes"])
        assert "Black-Scholes" not in assignment.get(0, [])

    def test_single_word_overlap_not_assigned(self):
        # "Python scripting" has only 1-word overlap with bullet ("Python") → score=1, below threshold
        # Prevents false-positive injection like "deep learning" into "machine learning" bullets
        bullets = ["Developed Python data pipelines", "Managed AWS infrastructure for deployments"]
        assignment = _assign_keywords_to_bullets(bullets, ["Python scripting"])
        assert "Python scripting" not in assignment.get(0, [])

    def test_two_word_overlap_assigned(self):
        # "Python data processing" has 2 words matching "Developed Python data pipelines" → score≥2
        bullets = ["Developed Python data pipelines for ETL", "Managed AWS infrastructure"]
        assignment = _assign_keywords_to_bullets(bullets, ["Python data processing"])
        assert "Python data processing" in assignment.get(0, [])

    def test_max_bullets_per_kw_respected(self):
        bullets = [
            "Built Python data service",
            "Developed Python data pipeline",
            "Wrote Python data tests",
        ]
        assignment = _assign_keywords_to_bullets(bullets, ["Python"], max_bullets_per_kw=2)
        python_count = sum(1 for kws in assignment.values() if "Python" in kws)
        assert python_count <= 2

    def test_empty_bullets(self):
        assignment = _assign_keywords_to_bullets([], ["Python"])
        assert assignment == {}

    def test_empty_keywords(self):
        assignment = _assign_keywords_to_bullets(["Built API"], [])
        assert all(v == [] for v in assignment.values())


# ── _build_bullet_briefs — all tiers ─────────────────────────────────────────

class TestBuildBulletBriefs:
    """Test all 6 tiers and edge cases."""

    def test_tier5_cross_domain_bullet_not_keep_original(self, jd_quant):
        """Army logistics bullet: cross-domain → Tier 5 transferable-skills brief, NOT keep_original."""
        bullets = ["Commanded supply convoy operations across 200km desert route"]
        briefs = _build_bullet_briefs(bullets, None, jd_quant)
        assert len(briefs) == 1
        assert briefs[0].keep_original is False
        assert "transferable" in briefs[0].approach.lower() or len(briefs[0].approach) > 10

    def test_all_cross_domain_bullets_get_tailored(self, jd_quant):
        """All army bullets should get Tier 5 transferable-skills briefs, not keep_original."""
        bullets = [
            "Led infantry patrol operations in mountainous terrain",
            "Coordinated medical evacuation procedures for 50-person unit",
            "Maintained equipment inventory for armoured vehicle fleet",
        ]
        briefs = _build_bullet_briefs(bullets, None, jd_quant)
        assert all(not b.keep_original for b in briefs)

    def test_tier2_weak_structure_always_rewrites(self, jd_quant):
        """Weak-structure bullet always gets a rewrite brief regardless of domain relevance."""
        bullets = ["Responsible for Python scripting for data processing tasks"]
        briefs = _build_bullet_briefs(bullets, None, jd_quant)
        assert len(briefs) == 1
        b = briefs[0]
        assert b.keep_original is False
        assert len(b.approach) > 10

    def test_tier2_apr_diagnosis_in_approach(self, jd_tech):
        """Weak bullet should have APR missing components listed in approach."""
        bullets = ["Worked on Python services for backend systems"]
        # Score this bullet: "Python" and "backend" match jd_tech keywords → > 0.12
        briefs = _build_bullet_briefs(bullets, None, jd_tech)
        b = briefs[0]
        assert not b.keep_original
        assert len(b.approach) > 10  # has real content

    def test_tier2_weak_high_score_allows_keyword_injection(self, jd_tech):
        """Bullet with Python+FastAPI+backend (high score) AND weak structure → full rewrite with keywords."""
        bullets = ["Responsible for Python FastAPI backend microservices PostgreSQL database"]
        briefs = _build_bullet_briefs(bullets, None, jd_tech)
        b = briefs[0]
        assert b.keep_original is False
        # Should NOT say "keep the original domain" since score is high
        # (may or may not include weave-in, depends on score)

    def test_tier3_gap_analysis_framing_with_evidence(self, jd_tech):
        """Bullet with gap analysis mapping gets framing + evidence anchoring."""
        bullet = "Built FastAPI microservices handling backend API requests for PostgreSQL"
        bullets = [bullet]
        gap_analysis = {
            "mappings": [
                {
                    "requirement": "Design and build scalable REST APIs",
                    "status": "partial_match",
                    "evidence": "Built FastAPI microservices handling backend API requests",
                    "suggested_framing": "Emphasise the scalability and throughput of the API",
                }
            ]
        }
        briefs = _build_bullet_briefs(bullets, gap_analysis, jd_tech)
        b = briefs[0]
        assert b.keep_original is False
        assert "scalability" in b.approach or "Emphasise" in b.approach
        # Evidence should be anchored in approach
        assert "Evidence identified" in b.approach

    def test_tier3_gap_framing_applied_regardless_of_score(self, jd_quant):
        """Gap framing is applied whenever gap analysis matches — no score gate."""
        bullet = "Developed Python scripts for data analysis reporting tasks"
        bullets = [bullet]
        gap_analysis = {
            "mappings": [
                {
                    "requirement": "Research and develop alpha-generating strategies",
                    "status": "partial_match",
                    "evidence": "Python scripts for data analysis",
                    "suggested_framing": "Reframe as alpha research using Python",
                }
            ]
        }
        briefs = _build_bullet_briefs(bullets, gap_analysis, jd_quant)
        b = briefs[0]
        assert not b.keep_original
        # Should apply the gap framing since evidence similarity threshold is met
        assert "alpha" in b.approach or len(b.approach) > 10

    def test_tier4_keyword_injection_only_with_fit(self, jd_tech):
        """Keywords with 0 fit score should not be assigned."""
        # This bullet has Python but not Black-Scholes (quant term)
        bullets = ["Built Python service processing backend API requests efficiently"]
        # Inject an unrelated keyword that has no word overlap
        jd_with_unrelated = {**jd_tech, "required_skills": ["Black-Scholes", "Python", "FastAPI"]}
        briefs = _build_bullet_briefs(bullets, None, jd_with_unrelated)
        b = briefs[0]
        if "Black-Scholes" in b.approach:
            pytest.fail("Unrelated domain keyword injected into brief")

    def test_tier5_well_structured_bullet_gets_transferable_skills_brief(self, jd_tech):
        """Well-structured bullet with all keywords → Tier 5 transferable-skills polish brief."""
        bullet = "Deployed scalable microservices infrastructure with FastAPI and Docker for CI/CD pipelines"
        bullets = [bullet]
        briefs = _build_bullet_briefs(bullets, None, jd_tech)
        b = briefs[0]
        assert not b.keep_original
        assert len(b.approach) > 10  # has real content

    def test_exp_context_propagated_all_tiers(self, jd_tech):
        """exp_context should appear in every BulletBrief."""
        bullets = [
            "Commanded supply convoy operations",  # Tier 5 transferable skills
            "Responsible for building Python APIs",  # Tier 2 weak
            "Built FastAPI microservices for backend Python CI/CD",  # Tier 4/5
        ]
        briefs = _build_bullet_briefs(bullets, None, jd_tech, exp_context="Engineer at Google")
        for b in briefs:
            assert b.exp_context == "Engineer at Google"

    def test_focus_requirements_restricts_best_req(self, jd_tech):
        """focus_requirements should limit which JD req is selected."""
        bullets = ["Built Python FastAPI backend microservices with PostgreSQL and Docker"]
        focus = ["Optimise database query performance"]
        briefs = _build_bullet_briefs(bullets, None, jd_tech, focus_requirements=focus)
        b = briefs[0]
        assert not b.keep_original
        assert "Optimise database query performance" in b.requirement

    def test_empty_bullets_returns_empty(self, jd_tech):
        assert _build_bullet_briefs([], None, jd_tech) == []

    def test_rules_suffix_appended(self, jd_tech):
        bullets = ["Responsible for Python backend API services"]
        briefs = _build_bullet_briefs(bullets, None, jd_tech, rules_text="Keep bullets under 150 chars")
        b = briefs[0]
        assert not b.keep_original
        assert "Keep bullets under 150 chars" in b.approach

    def test_redundant_bullets_detected(self, jd_tech):
        """Two near-identical bullets → second flagged as redundant."""
        bullets = [
            "Built Python FastAPI REST APIs for backend microservices with PostgreSQL",
            "Developed Python FastAPI REST APIs for backend microservices with PostgreSQL",
        ]
        briefs = _build_bullet_briefs(bullets, None, jd_tech)
        # Second bullet should get redundant approach
        b1, b2 = briefs
        assert "same ground" in b2.approach

    def test_gap_analysis_none_does_not_crash(self, jd_tech):
        bullets = ["Built Python FastAPI backend API microservices"]
        briefs = _build_bullet_briefs(bullets, None, jd_tech)
        assert len(briefs) == 1


# ── _tailor_one_bullet (async, mocked) ────────────────────────────────────────

class TestTailorOneBullet:
    @pytest.mark.asyncio
    async def test_keep_original_skips_api_call(self):
        client = _make_async_client("should not be called")
        brief = BulletBrief(requirement="", approach="", keep_original=True)
        result = await _tailor_one_bullet("original bullet", brief, "Role context", client, _make_settings())
        client.chat.completions.create.assert_not_called()
        assert result == "original bullet"

    @pytest.mark.asyncio
    async def test_returns_best_of_two_candidates(self):
        """Should pick candidate with more JD keywords in first 6 words."""
        client = _make_async_client(
            "Built Python API reducing backend latency by 40%",     # candidate 1
            "FastAPI Python microservices backend CI/CD pipeline",   # candidate 2 — more kws early
        )
        brief = BulletBrief(
            requirement="Design and build scalable REST APIs",
            approach="Restructure to lead with FastAPI",
        )
        result = await _tailor_one_bullet(
            "worked on Python backend services",
            brief, "Senior Engineer (tech)", client, _make_settings(),
            priority_keywords=["FastAPI", "Python", "backend", "microservices", "CI/CD"],
        )
        # Should pick candidate 2 since it has more JD kws in first 6 words
        assert "FastAPI" in result

    @pytest.mark.asyncio
    async def test_quality_gate_rejects_hallucinated_numbers(self):
        """Candidate that introduces new numbers → rejected, falls back to original."""
        original = "Built Python service for backend API processing"
        client = _make_async_client(
            "Built Python service handling 50,000 requests/day reducing latency by 40%",
            "Built Python service handling 50,000 requests/day reducing latency by 40%",
        )
        brief = BulletBrief(requirement="Build APIs", approach="Improve")
        result = await _tailor_one_bullet(original, brief, "Role", client, _make_settings())
        # Both candidates introduce "50,000" and "40%" not in original → fallback
        assert result == original

    @pytest.mark.asyncio
    async def test_domain_guidance_included_in_system_prompt(self, jd_quant):
        """Domain guidance should be in the system message sent to API."""
        from backend.agents.domain_guidance import _get_domain_guidance
        client = _make_async_client(
            "Backtested momentum strategy on 5-year dataset achieving Sharpe ratio of 1.4"
        )
        brief = BulletBrief(
            requirement="Research and develop alpha-generating strategies",
            approach="Reframe as quant research",
        )
        domain_guidance = _get_domain_guidance("quantitative finance")
        await _tailor_one_bullet(
            "Developed statistical analysis using Python and pandas",
            brief, "Quantitative Analyst (quantitative finance)",
            client, _make_settings(),
            domain_guidance=domain_guidance,
        )
        call_args = client.chat.completions.create.call_args
        system_msg = call_args.kwargs["messages"][0]["content"]
        assert "Sharpe" in system_msg or "quant" in system_msg.lower()

    @pytest.mark.asyncio
    async def test_seniority_note_included_in_system_prompt(self):
        client = _make_async_client("Led Python API development delivering 40% latency reduction")
        brief = BulletBrief(requirement="Build APIs", approach="Improve")
        await _tailor_one_bullet(
            "worked on Python APIs",
            brief, "Role", client, _make_settings(),
            seniority_note="Seniority: Senior — prefer ownership verbs.",
        )
        call_args = client.chat.completions.create.call_args
        system_msg = call_args.kwargs["messages"][0]["content"]
        assert "Senior" in system_msg

    @pytest.mark.asyncio
    async def test_exp_context_in_user_prompt(self):
        client = _make_async_client("Built Python backend API service reducing latency")
        brief = BulletBrief(
            requirement="Build APIs",
            approach="Improve",
            exp_context="Backend Engineer at Goldman Sachs",
        )
        await _tailor_one_bullet(
            "Built Python service", brief, "Role", client, _make_settings()
        )
        call_args = client.chat.completions.create.call_args
        user_msg = call_args.kwargs["messages"][1]["content"]
        assert "Goldman Sachs" in user_msg

    @pytest.mark.asyncio
    async def test_n2_requested(self):
        """API should be called with n=2."""
        client = _make_async_client(
            "Built Python FastAPI service",
            "Developed Python FastAPI REST API",
        )
        brief = BulletBrief(requirement="Build APIs", approach="Improve")
        await _tailor_one_bullet("worked on Python APIs", brief, "Role", client, _make_settings())
        call_args = client.chat.completions.create.call_args
        assert call_args.kwargs["n"] == 2

    @pytest.mark.asyncio
    async def test_api_exception_falls_back_to_original(self):
        client = MagicMock()
        client.chat = MagicMock()
        client.chat.completions = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=Exception("API error"))
        brief = BulletBrief(requirement="Build APIs", approach="Improve")
        result = await _tailor_one_bullet("original bullet", brief, "Role", client, _make_settings())
        assert result == "original bullet"

    @pytest.mark.asyncio
    async def test_empty_api_response_falls_back_to_original(self):
        client = _make_async_client("", "")
        brief = BulletBrief(requirement="Build APIs", approach="Improve")
        result = await _tailor_one_bullet("original bullet", brief, "Role", client, _make_settings())
        assert result == "original bullet"


# ── tailor_experiences (full integration, mocked) ────────────────────────────

class TestTailorExperiences:
    @pytest.mark.asyncio
    async def test_empty_experiences_returns_empty(self, jd_tech):
        with patch("backend.agents.cv_tailor.get_openai_client") as mock_client:
            mock_client.return_value = _make_async_client("irrelevant")
            result = await tailor_experiences([], jd_tech)
        assert result == []

    @pytest.mark.asyncio
    async def test_experience_with_empty_bullets_returns_zero_confidence(self, jd_tech):
        exps = [{"id": "exp-1", "company": "Acme", "role_title": "Engineer", "bullets": []}]
        with patch("backend.agents.cv_tailor.get_openai_client") as mock_client, \
             patch("backend.agents.cv_tailor.get_settings") as mock_settings:
            mock_client.return_value = _make_async_client("never called")
            mock_settings.return_value = _make_settings()
            result = await tailor_experiences(exps, jd_tech)
        assert len(result) == 1
        assert result[0].original_bullets == []
        assert result[0].suggested_bullets == []

    @pytest.mark.asyncio
    async def test_cross_domain_bullets_are_tailored(self, jd_quant):
        """Army bullets for a quant role → LLM is called (Tier 5 transferable-skills brief)."""
        exps = [{
            "id": "exp-1",
            "company": "British Army",
            "role_title": "Infantry Officer",
            "bullets": [
                {"text": "Commanded 30-person platoon conducting operations in challenging terrain"},
                {"text": "Led logistics coordination for multi-vehicle convoy over 300km"},
            ],
        }]
        rewrite = "Led 30-person team executing time-sensitive logistics operations across 300km route"
        with patch("backend.agents.cv_tailor.get_openai_client") as mock_client, \
             patch("backend.agents.cv_tailor.get_settings") as mock_settings:
            mock_client.return_value = _make_async_client(rewrite, rewrite)
            mock_settings.return_value = _make_settings()
            result = await tailor_experiences(exps, jd_quant)

        assert len(result) == 1
        te = result[0]
        assert len(te.suggested_bullets) == 2
        # LLM was called — bullets are processed (may or may not change depending on mock)
        for sb in te.suggested_bullets:
            assert isinstance(sb.text, str) and len(sb.text) > 0

    @pytest.mark.asyncio
    async def test_relevant_bullets_are_tailored(self, jd_tech):
        """Bullets with JD keyword overlap should be rewritten."""
        tailored_text = "Engineered Python FastAPI microservices reducing backend API latency"
        exps = [{
            "id": "exp-1",
            "company": "TechCo",
            "role_title": "Backend Engineer",
            "bullets": [
                {"text": "Responsible for Python backend API services handling requests"},
            ],
        }]
        with patch("backend.agents.cv_tailor.get_openai_client") as mock_client, \
             patch("backend.agents.cv_tailor.get_settings") as mock_settings:
            mock_client.return_value = _make_async_client(tailored_text, tailored_text)
            mock_settings.return_value = _make_settings()
            result = await tailor_experiences(exps, jd_tech)

        assert len(result) == 1
        assert result[0].suggested_bullets[0].text == tailored_text

    @pytest.mark.asyncio
    async def test_returns_tailored_experience_model(self, jd_tech):
        exps = [{
            "id": "exp-42",
            "company": "Corp",
            "role_title": "Engineer",
            "bullets": [{"text": "Built Python FastAPI backend microservices with PostgreSQL"}],
        }]
        with patch("backend.agents.cv_tailor.get_openai_client") as mock_client, \
             patch("backend.agents.cv_tailor.get_settings") as mock_settings:
            mock_client.return_value = _make_async_client(
                "Engineered Python FastAPI microservices backend reducing latency by 30%",
                "Engineered Python FastAPI microservices backend reducing latency by 30%",
            )
            mock_settings.return_value = _make_settings()
            result = await tailor_experiences(exps, jd_tech)

        te = result[0]
        assert isinstance(te, TailoredExperience)
        assert te.experience_id == "exp-42"
        assert len(te.original_bullets) == 1
        assert len(te.suggested_bullets) == 1
        assert 0.0 <= te.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_has_placeholder_detected(self, jd_tech):
        """Suggested bullet containing [X] → has_placeholder=True."""
        exps = [{
            "id": "exp-1",
            "company": "Corp",
            "role_title": "Engineer",
            "bullets": [{"text": "Responsible for Python backend service development"}],
        }]
        with patch("backend.agents.cv_tailor.get_openai_client") as mock_client, \
             patch("backend.agents.cv_tailor.get_settings") as mock_settings:
            mock_client.return_value = _make_async_client(
                "Engineered Python FastAPI service reducing backend latency by [X]",
                "Engineered Python FastAPI service reducing backend latency by [X]",
            )
            mock_settings.return_value = _make_settings()
            result = await tailor_experiences(exps, jd_tech)

        assert result[0].suggested_bullets[0].has_placeholder is True


# ── tailor_projects ───────────────────────────────────────────────────────────

class TestTailorProjects:
    @pytest.mark.asyncio
    async def test_empty_projects_returns_empty(self, jd_tech):
        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client()
            ms.return_value = _make_settings()
            result = await tailor_projects([], jd_tech)
        assert result == []

    @pytest.mark.asyncio
    async def test_project_with_bullets(self, jd_tech):
        projects = [{
            "id": "proj-1",
            "name": "CV Tailor App",
            "bullets": [{"text": "Responsible for Python FastAPI backend microservices"}],
            "description": None,
        }]
        rewrite = "Engineered Python FastAPI backend reducing API response time by [X%]"
        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client(rewrite, rewrite)
            ms.return_value = _make_settings()
            result = await tailor_projects(projects, jd_tech)

        assert len(result) == 1
        assert isinstance(result[0], TailoredProject)
        assert result[0].project_id == "proj-1"

    @pytest.mark.asyncio
    async def test_project_falls_back_to_description_when_no_bullets(self, jd_tech):
        projects = [{
            "id": "proj-1",
            "name": "CLI Tool",
            "bullets": [],
            "description": "Built a Python CLI tool for data processing using FastAPI",
        }]
        rewrite = "Engineered Python CLI tool processing data with FastAPI backend integration"
        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client(rewrite, rewrite)
            ms.return_value = _make_settings()
            result = await tailor_projects(projects, jd_tech)

        assert len(result) == 1
        assert len(result[0].original_bullets) > 0

    @pytest.mark.asyncio
    async def test_project_with_no_bullets_and_no_description_skipped(self, jd_tech):
        projects = [{"id": "proj-1", "name": "Empty", "bullets": [], "description": None}]
        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client()
            ms.return_value = _make_settings()
            result = await tailor_projects(projects, jd_tech)
        assert result == []


# ── tailor_activities ─────────────────────────────────────────────────────────

class TestTailorActivities:
    @pytest.mark.asyncio
    async def test_empty_activities_returns_empty(self, jd_tech):
        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client()
            ms.return_value = _make_settings()
            result = await tailor_activities([], jd_tech)
        assert result == []

    @pytest.mark.asyncio
    async def test_activity_with_no_bullets_skipped(self, jd_tech):
        acts = [{"id": "act-1", "organization": "Club", "role_title": "Member", "bullets": []}]
        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client()
            ms.return_value = _make_settings()
            result = await tailor_activities(acts, jd_tech)
        assert result == []

    @pytest.mark.asyncio
    async def test_activity_tailored_correctly(self, jd_tech):
        acts = [{
            "id": "act-1",
            "organization": "Tech Society",
            "role_title": "VP Engineering",
            "bullets": [{"text": "Responsible for Python workshops and backend sessions"}],
        }]
        rewrite = "Led Python and FastAPI backend workshops for 50+ members improving technical skills"
        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client(rewrite, rewrite)
            ms.return_value = _make_settings()
            result = await tailor_activities(acts, jd_tech)

        assert len(result) == 1
        assert isinstance(result[0], TailoredActivity)
        assert result[0].activity_id == "act-1"


# ── Edge cases / regression guards ────────────────────────────────────────────

class TestEdgeCases:
    def test_jd_with_no_keywords_neutral_score(self):
        """Empty JD keyword pool → neutral score of 0.5 (not 0)."""
        score = _jd_relevance_score("any bullet text", {"required_skills": [], "keywords": []})
        assert score == 0.5

    def test_similarity_empty_strings(self):
        assert _similarity("", "") == 1.0
        assert _similarity("", "something") == 0.0
        assert _similarity("something", "") == 0.0

    def test_keyword_abbreviation_expansion(self):
        assert _keyword_in_text("ML", "machine learning pipeline for classification")
        assert _keyword_in_text("machine learning", "built ML model for production")

    def test_has_hallucinated_numbers_false_for_same_numbers(self):
        orig = "Reduced latency by 40% in Python FastAPI service"
        sug = "Engineered Python FastAPI service reducing API latency by 40%"
        assert not _has_hallucinated_numbers(orig, sug)

    def test_has_hallucinated_numbers_true_for_new_number(self):
        orig = "Built Python service for data processing"
        sug = "Built Python service processing 50,000 requests per day"
        assert _has_hallucinated_numbers(orig, sug)

    def test_bullet_weakness_detects_passive_start(self):
        assert _bullet_weakness("Responsible for building Python services") is not None
        assert _bullet_weakness("Assisted with backend Python development tasks") is not None

    def test_bullet_weakness_none_for_strong_bullet(self):
        assert _bullet_weakness("Engineered Python FastAPI REST service handling 10K RPM reducing backend latency") is None

    def test_find_redundant_pairs_similar_bullets(self):
        bullets = [
            "Built Python FastAPI REST API for backend microservices",
            "Developed Python FastAPI REST API for backend microservices",
        ]
        redundant = _find_redundant_pairs(bullets)
        assert 1 in redundant

    def test_find_redundant_pairs_distinct_bullets(self):
        bullets = [
            "Built Python FastAPI REST API for backend microservices",
            "Managed AWS infrastructure with Docker and CI/CD pipelines",
        ]
        redundant = _find_redundant_pairs(bullets)
        assert redundant == {}

    def test_build_bullet_briefs_with_no_gap_analysis(self, jd_tech):
        """Should not raise when gap_analysis is None."""
        bullets = ["Built Python FastAPI backend microservices with PostgreSQL"]
        briefs = _build_bullet_briefs(bullets, None, jd_tech)
        assert len(briefs) == 1

    def test_best_req_empty_focus_falls_back_to_all(self, jd_tech):
        req = _best_req(jd_tech, "built APIs", focus=[])
        # Empty focus → falls back to all key_responsibilities
        assert req in jd_tech["key_responsibilities"] or req == jd_tech.get("role_summary")

    def test_best_req_with_focus_list(self, jd_tech):
        focus = ["Optimise database query performance"]
        req = _best_req(jd_tech, "built API", focus=focus)
        assert req == "Optimise database query performance"

    @pytest.mark.asyncio
    async def test_tailor_experiences_with_empty_jd(self):
        """Empty JD should not crash — all bullets scored neutral and processed."""
        jd = {
            "role_summary": "", "domain": "", "seniority_level": "",
            "required_skills": [], "key_responsibilities": [],
            "keywords": [], "nice_to_have_skills": [], "outcome_signals": [],
        }
        exps = [{
            "id": "exp-1",
            "company": "Corp",
            "role_title": "Dev",
            "bullets": [{"text": "Built Python service"}],
        }]
        rewrite = "Developed Python service for internal data processing"
        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client(rewrite, rewrite)
            ms.return_value = _make_settings()
            result = await tailor_experiences(exps, jd)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_multiple_experiences_all_tailored(self, jd_tech):
        """Multiple experiences run in parallel without interfering."""
        exps = [
            {
                "id": f"exp-{i}",
                "company": f"Corp{i}",
                "role_title": "Engineer",
                "bullets": [{"text": f"Built Python FastAPI backend microservices exp{i}"}],
            }
            for i in range(3)
        ]
        rewrite = "Engineered Python FastAPI microservices reducing backend latency by 40%"
        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client(rewrite, rewrite)
            ms.return_value = _make_settings()
            result = await tailor_experiences(exps, jd_tech)
        assert len(result) == 3
        for te in result:
            assert len(te.suggested_bullets) == 1


# ── End-to-end scenario tests ─────────────────────────────────────────────────

class TestEndToEndScenarios:
    """Realistic multi-bullet, multi-experience scenarios.

    All mock responses are pre-validated to pass _has_lost_tech_terms,
    _has_hallucinated_numbers, _BANNED_PHRASE_RE, and similarity checks.
    """

    @pytest.mark.asyncio
    async def test_quant_finance_mixed_experience(self, jd_quant):
        """Quant JD: both bullets are sent to LLM (army bullet gets Tier 5 transferable-skills brief)."""
        exps = [{
            "id": "quant-exp",
            "company": "Hedge Fund",
            "role_title": "Analyst",
            "bullets": [
                {"text": "Developed Python pandas scripts for data manipulation tasks"},
                {"text": "Commanded platoon in field operations"},
            ],
        }]
        rewrite = "Developed Python pandas pipeline analysing historical market tick data"
        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client(rewrite, rewrite)
            ms.return_value = _make_settings()
            result = await tailor_experiences(exps, jd_quant)

        assert len(result) == 1
        te = result[0]
        assert len(te.original_bullets) == 2
        assert len(te.suggested_bullets) == 2
        # Both bullets processed by LLM
        for sb in te.suggested_bullets:
            assert isinstance(sb.text, str) and len(sb.text) > 0

    @pytest.mark.asyncio
    async def test_full_pipeline_experiences_projects_activities(self, jd_tech):
        """All three tailoring functions run without error on typical inputs."""
        exps = [{
            "id": "exp-1",
            "company": "TechCo",
            "role_title": "Backend Engineer",
            "bullets": [{"text": "Responsible for Python backend service development"}],
        }]
        projects = [{
            "id": "proj-1",
            "title": "Data Pipeline",
            "bullets": [{"text": "Built Python data pipeline for backend processing"}],
        }]
        activities = [{
            "id": "act-1",
            "name": "Chess Club",
            "bullets": [{"text": "Competed in university chess tournament finals"}],
        }]
        exp_rewrite = "Engineered Python backend service reducing processing time for team"
        proj_rewrite = "Developed Python data pipeline automating backend ingestion tasks"

        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client(exp_rewrite, exp_rewrite)
            ms.return_value = _make_settings()
            exp_result = await tailor_experiences(exps, jd_tech)

        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client(proj_rewrite, proj_rewrite)
            ms.return_value = _make_settings()
            proj_result = await tailor_projects(projects, jd_tech)

        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client("SHOULD NOT APPEAR")
            ms.return_value = _make_settings()
            act_result = await tailor_activities(activities, jd_tech)

        assert len(exp_result) == 1
        assert exp_result[0].suggested_bullets[0].text == exp_rewrite
        assert len(proj_result) == 1
        assert proj_result[0].suggested_bullets[0].text == proj_rewrite
        assert len(act_result) == 1
        # Chess activity gets Tier 5 transferable-skills brief — LLM is called
        assert len(act_result[0].suggested_bullets) == 1

    @pytest.mark.asyncio
    async def test_three_bullet_experience_mix_keep_and_tailor(self, jd_tech):
        """Experience with 3 bullets: relevant tailored, irrelevant kept, semi-relevant tailored."""
        exps = [{
            "id": "mixed-exp",
            "company": "Corp",
            "role_title": "Engineer",
            "bullets": [
                {"text": "Wrote Python scripts to process data records"},           # relevant
                {"text": "Attended weekly team standup meetings"},                   # irrelevant
                {"text": "Built Python service for backend data processing"},       # relevant
            ],
        }]
        rewrite_a = "Built Python scripts automating data ingestion and processing"
        rewrite_b = "Refactored Python service improving backend data analysis throughput"

        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client(rewrite_a, rewrite_b)
            ms.return_value = _make_settings()
            result = await tailor_experiences(exps, jd_tech)

        assert len(result) == 1
        te = result[0]
        assert len(te.original_bullets) == 3
        assert len(te.suggested_bullets) == 3
        # All bullets processed — LLM called for each (including standup)

    @pytest.mark.asyncio
    async def test_redundant_bullet_pair_no_crash(self, jd_tech):
        """Near-duplicate bullets — redundancy tier should not raise."""
        exps = [{
            "id": "dup-exp",
            "company": "Corp",
            "role_title": "Engineer",
            "bullets": [
                {"text": "Built Python service for backend data processing"},
                {"text": "Built Python service for backend data analysis"},  # near-duplicate
            ],
        }]
        rewrite = "Refactored Python service improving backend data analysis throughput"
        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client(rewrite, rewrite)
            ms.return_value = _make_settings()
            result = await tailor_experiences(exps, jd_tech)

        assert len(result) == 1
        te = result[0]
        assert len(te.suggested_bullets) == 2
        for sb in te.suggested_bullets:
            assert isinstance(sb.text, str) and len(sb.text) > 0

    @pytest.mark.asyncio
    async def test_director_seniority_no_crash(self):
        """Director-level seniority note should be injected without error."""
        jd = {
            "role_summary": "Engineering Director",
            "domain": "technology",
            "seniority_level": "director",
            "required_skills": ["Python", "leadership"],
            "key_responsibilities": ["Lead engineering teams"],
            "keywords": ["backend", "strategy"],
            "nice_to_have_skills": [],
            "outcome_signals": [],
        }
        exps = [{
            "id": "dir-exp",
            "company": "BigCo",
            "role_title": "Engineering Director",
            "bullets": [{"text": "Led Python backend engineering team on data services"}],
        }]
        rewrite = "Directed Python backend engineering squad deploying scalable data infrastructure"
        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client(rewrite, rewrite)
            ms.return_value = _make_settings()
            result = await tailor_experiences(exps, jd)

        assert len(result) == 1
        assert isinstance(result[0], TailoredExperience)

    @pytest.mark.asyncio
    async def test_non_tech_domain_marketing_no_crash(self):
        """Non-tech domain (marketing) should not crash the pipeline."""
        jd = {
            "role_summary": "Marketing Manager",
            "domain": "marketing",
            "seniority_level": "mid",
            "required_skills": ["copywriting", "analytics", "campaigns", "social media"],
            "key_responsibilities": ["Plan and execute marketing campaigns"],
            "keywords": ["engagement", "conversion", "branding"],
            "nice_to_have_skills": [],
            "outcome_signals": ["conversion rate", "engagement"],
        }
        exps = [{
            "id": "mkt-exp",
            "company": "BrandCo",
            "role_title": "Marketing Analyst",
            "bullets": [
                {"text": "Managed social media campaigns increasing follower engagement"},
                {"text": "Drafted financial reports for stakeholders"},
            ],
        }]
        rewrite = "Optimised social media campaigns boosting follower engagement and conversion metrics"
        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client(rewrite, rewrite)
            ms.return_value = _make_settings()
            result = await tailor_experiences(exps, jd)

        assert len(result) == 1
        te = result[0]
        assert len(te.suggested_bullets) == 2
        for sb in te.suggested_bullets:
            assert isinstance(sb.text, str) and len(sb.text) > 0

    @pytest.mark.asyncio
    async def test_gap_analysis_tier3_evidence_anchoring(self, jd_tech):
        """Gap analysis with evidence_quote should produce Tier 3 briefs without crashing."""
        gap_analysis = {
            "gaps": [
                {
                    "requirement": "Write unit and integration tests",
                    "status": "partial",
                    "suggested_framing": "Reframe to highlight testing work",
                    "evidence_quote": "tested API endpoints with pytest",
                    "target_bullets": [0],
                }
            ]
        }
        exps = [{
            "id": "gap-exp",
            "company": "Corp",
            "role_title": "Engineer",
            "bullets": [{"text": "Built Python backend service processing data requests"}],
        }]
        rewrite = "Built Python backend service with pytest integration tests for data requests"
        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client(rewrite, rewrite)
            ms.return_value = _make_settings()
            result = await tailor_experiences(exps, jd_tech, gap_analysis=gap_analysis)

        assert len(result) == 1
        assert isinstance(result[0].suggested_bullets[0].text, str)

    @pytest.mark.asyncio
    async def test_all_cross_domain_bullets_still_processed(self, jd_quant):
        """When all bullets are cross-domain, they still get Tier 5 transferable-skills briefs and LLM is called."""
        army_bullets = [
            "Commanded 30-person platoon in field operations",
            "Led logistics convoy over 200km route in adverse conditions",
            "Coordinated evacuation of personnel from forward operating base",
        ]
        exps = [{
            "id": "army-exp",
            "company": "British Army",
            "role_title": "Infantry Officer",
            "bullets": [{"text": b} for b in army_bullets],
        }]
        rewrite = "Led 30-person team executing time-sensitive logistics and operations coordination"
        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client(rewrite, rewrite)
            ms.return_value = _make_settings()
            result = await tailor_experiences(exps, jd_quant)

        te = result[0]
        assert len(te.suggested_bullets) == 3
        for sb in te.suggested_bullets:
            assert isinstance(sb.text, str) and len(sb.text) > 0

    @pytest.mark.asyncio
    async def test_projects_with_cross_domain_bullets(self, jd_quant):
        """Projects with cross-domain bullets still get LLM calls (Tier 5), quant project gets tailored."""
        projects = [
            {
                "id": "proj-army",
                "title": "Military Logistics System",
                "bullets": [{"text": "Designed radio communication protocols for field units"}],
            },
            {
                "id": "proj-relevant",
                "title": "Quant Research Tool",
                "bullets": [{"text": "Built Python backtesting framework for strategy evaluation"}],
            },
        ]
        rewrite = "Developed Python backtesting framework analysing strategy performance and statistics"
        with patch("backend.agents.cv_tailor.get_openai_client") as mc, \
             patch("backend.agents.cv_tailor.get_settings") as ms:
            mc.return_value = _make_async_client(rewrite, rewrite)
            ms.return_value = _make_settings()
            result = await tailor_projects(projects, jd_quant)

        assert len(result) == 2
        for proj in result:
            assert len(proj.suggested_bullets) == 1
            assert isinstance(proj.suggested_bullets[0].text, str)
