"""Shared fixtures for backend tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_jd_parsed() -> dict:
    """A minimal parsed JD for testing."""
    return {
        "role_summary": "Software Engineer at TechCorp",
        "domain": "technology",
        "seniority_level": "mid",
        "required_skills": ["Python", "FastAPI", "PostgreSQL"],
        "key_responsibilities": [
            "Design and build REST APIs",
            "Write unit and integration tests",
        ],
        "tools_and_technologies": ["Docker", "AWS"],
        "nice_to_have_skills": ["Kubernetes", "GraphQL"],
        "keywords": ["backend", "API", "microservices", "Python"],
    }


@pytest.fixture
def sample_experiences() -> list[dict]:
    """Sample work experiences as plain dicts (post-Phase-3 format)."""
    return [
        {
            "id": "exp-1",
            "company": "Acme Corp",
            "role_title": "Backend Engineer",
            "bullets": [
                {"text": "Built REST APIs serving 10K RPM using FastAPI and PostgreSQL", "domain_tags": ["backend"]},
                {"text": "Reduced API latency by 40% through query optimization", "domain_tags": ["backend"]},
                {"text": "Implemented CI/CD pipelines with GitHub Actions and Docker", "domain_tags": ["devops"]},
            ],
            "domain_tags": ["technology", "backend"],
            "skill_tags": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        },
        {
            "id": "exp-2",
            "company": "StartupXYZ",
            "role_title": "Full Stack Developer",
            "bullets": [
                {"text": "Developed React frontend consuming GraphQL APIs", "domain_tags": ["frontend"]},
                {"text": "Managed AWS infrastructure including ECS and RDS", "domain_tags": ["devops"]},
            ],
            "domain_tags": ["technology", "full-stack"],
            "skill_tags": ["React", "GraphQL", "AWS"],
        },
    ]


@pytest.fixture
def sample_activities() -> list[dict]:
    """Sample activities as plain dicts."""
    return [
        {
            "id": "act-1",
            "organization": "Tech Society",
            "role_title": "Vice President",
            "bullets": [
                {"text": "Led a team of 15 members organizing hackathons with 200+ participants"},
                {"text": "Managed $5K budget for technical workshops and speaker events"},
            ],
            "domain_tags": ["leadership"],
            "skill_tags": ["leadership", "event management"],
        },
    ]
