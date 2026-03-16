"""Live tailoring output test — runs real LLM calls, no mocks.

Tests two scenarios:
  A. Same-domain: Software engineer CV -> backend engineering JD
  B. Cross-domain: Finance/quant CV -> ML/search JD (TikTok-style)
  C. Weak bullets: passive/vague bullets that need structural fixes

Run from repo root:
  cd backend && python scripts/test_tailoring_live.py
"""

from __future__ import annotations
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.agents.cv_tailor import tailor_experiences, tailor_projects


# ── JDs ───────────────────────────────────────────────────────────────────────

JD_BACKEND = {
    "role_summary": "Senior Backend Engineer",
    "domain": "software engineering",
    "seniority_level": "senior",
    "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis"],
    "key_responsibilities": [
        "Design and build high-throughput REST APIs serving 10M+ requests/day",
        "Optimise database query performance and schema design",
        "Own backend services end-to-end from design to production",
        "Improve observability with structured logging and metrics",
    ],
    "keywords": ["microservices", "CI/CD", "async", "performance", "scalability"],
    "nice_to_have_skills": ["Kubernetes", "AWS"],
    "outcome_signals": ["latency reduction", "throughput improvement", "uptime"],
}

JD_ML_SEARCH = {
    "role_summary": "Search Algorithm Intern",
    "domain": "machine learning / search",
    "seniority_level": "internship",
    "required_skills": ["Python", "machine learning", "NLP", "deep learning", "information retrieval"],
    "key_responsibilities": [
        "Develop and optimize search ranking algorithms using ML and NLP",
        "Analyse large-scale user behaviour data to improve search relevance",
        "Build and evaluate recommendation and retrieval models",
        "Research state-of-the-art techniques in search, NLP, and ranking",
    ],
    "keywords": ["search ranking", "recommendation systems", "neural networks", "data analysis", "A/B testing"],
    "nice_to_have_skills": ["C++", "PyTorch", "TensorFlow"],
    "outcome_signals": ["relevance improvement", "latency reduction", "precision recall"],
}


# ── Sample experiences ─────────────────────────────────────────────────────────

SAME_DOMAIN_EXP = [{
    "id": "exp-backend",
    "company": "Stripe",
    "role_title": "Backend Engineer",
    "bullets": [
        {"text": "Built REST APIs using Python and FastAPI for payment processing"},
        {"text": "Optimised PostgreSQL queries reducing average response time by 35%"},
        {"text": "Containerised services with Docker and deployed to AWS ECS"},
        {"text": "Responsible for maintaining legacy billing codebase"},  # weak
        {"text": "Worked on Redis caching layer for session management"},  # weak
    ],
}]

CROSS_DOMAIN_EXP = [{
    "id": "exp-amili",
    "company": "Amili",
    "role_title": "Data Engineer",
    "bullets": [
        {"text": "Built data pipelines using Apache Airflow and PostgreSQL to automate clinical trial data ingestion"},
        {"text": "Trained XGBoost classification models to predict patient outcomes, achieving 87% accuracy"},
        {"text": "Developed REST APIs using FastAPI to expose ML model predictions to downstream services"},
    ],
}, {
    "id": "exp-citadel",
    "company": "Citadel",
    "role_title": "Quantitative Research Intern",
    "bullets": [
        {"text": "Conducted quantitative research on equity factor models using Python and pandas"},
        {"text": "Backtested systematic trading strategies on 10 years of historical tick data"},
        {"text": "Automated risk reporting dashboards using Bloomberg API, reducing manual effort by 60%"},
    ],
}, {
    "id": "exp-army",
    "company": "Singapore Armed Forces",
    "role_title": "Infantry Officer",
    "bullets": [
        {"text": "Commanded 30-person platoon conducting operations across multiple terrain types"},
        {"text": "Led logistics coordination for multi-vehicle convoy over 300km route"},
    ],
}]

WEAK_BULLETS_EXP = [{
    "id": "exp-weak",
    "company": "TechCorp",
    "role_title": "Software Engineer",
    "bullets": [
        {"text": "Helped with Python backend development"},
        {"text": "Responsible for database work"},
        {"text": "Assisted in API design"},
        {"text": "Was part of the DevOps team"},
        {"text": "Worked on performance"},
    ],
}]


# ── Runner ─────────────────────────────────────────────────────────────────────

def print_results(label: str, exps_input: list, results: list) -> None:
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    for exp_input, result in zip(exps_input, results):
        print(f"\n  [{result.experience_id}] {exp_input['role_title']} @ {exp_input['company']}")
        print(f"  confidence: {result.confidence:.0%}")
        for orig, sug in zip(result.original_bullets, result.suggested_bullets):
            changed = orig != sug.text
            marker = "~" if changed else " "
            print(f"\n  {marker} ORIG: {orig}")
            if changed:
                ph = " [has placeholder]" if sug.has_placeholder else ""
                print(f"    NEW:  {sug.text}{ph}")


async def main() -> None:
    print("\nRunning live tailoring tests — real LLM calls...\n")

    print("Scenario A: Same-domain (backend eng CV -> backend eng JD)")
    results_a = await tailor_experiences(SAME_DOMAIN_EXP, JD_BACKEND)
    print_results("Scenario A — Same Domain", SAME_DOMAIN_EXP, results_a)

    print("\n\nScenario B: Cross-domain (finance/ML CV -> search/ML JD)")
    results_b = await tailor_experiences(CROSS_DOMAIN_EXP, JD_ML_SEARCH)
    print_results("Scenario B — Cross Domain", CROSS_DOMAIN_EXP, results_b)

    print("\n\nScenario C: Weak/passive bullets -> backend JD")
    results_c = await tailor_experiences(WEAK_BULLETS_EXP, JD_BACKEND)
    print_results("Scenario C — Weak Bullets", WEAK_BULLETS_EXP, results_c)

    # Summary stats
    all_results = results_a + results_b + results_c
    total = sum(len(r.original_bullets) for r in all_results)
    changed = sum(
        sum(1 for o, s in zip(r.original_bullets, r.suggested_bullets) if o != s.text)
        for r in all_results
    )
    placeholders = sum(
        sum(1 for s in r.suggested_bullets if s.has_placeholder)
        for r in all_results
    )
    print(f"\n\n{'='*70}")
    print(f"  SUMMARY: {changed}/{total} bullets rewritten ({changed/total:.0%}), {placeholders} placeholders added")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
