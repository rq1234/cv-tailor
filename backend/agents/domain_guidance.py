"""Domain-specific tailoring guidance for the CV tailor agent.

Distilled from strong real-world CVs per industry.
"""

from __future__ import annotations

DOMAIN_GUIDANCE: dict[str, str] = {
    "tech": """\
## Domain-Specific Norms: Technology / Software Engineering
Apply these norms on top of the general rules above.

**Action Verbs (prefer):** Architected, Engineered, Built, Implemented, Deployed, Automated, Designed, Launched, Shipped, Migrated, Integrated, Optimised

**Lead with:** Specific named technologies + quantified scale/impact
- Pattern: "[Verb] [system/tool] using [Tech A, Tech B], [reducing/achieving/improving] [metric]"
- Good: "Engineered high-performance CLI tool in Go, cutting logging infrastructure cost by 50% with a self-updating binary"
- Good: "Implemented dataset using Scala and Apache Beam APIs, achieving 60% compression vs raw metadata source"
- Good: "Developed scalable event-driven AWS pipeline (CDK, API Gateway, Lambda, SQS), serving 500,000+ events daily while reducing AWS costs by 50%"

**Always embed tech names inline** — never appended at the end as a list. ATS systems and recruiters Ctrl+F for exact tech names.

**Preferred scale language:** "500,000+ events daily", "over 200 students", "1.88 million records", "reducing latency by X%", "99.9% uptime", "X% compression"

**Quantified outcome formats to use:**
- Cost: "reducing AWS costs by 50%", "cutting infrastructure cost by 50%"
- Speed: "improving data refresh rates by 50%", "reducing metric reporting time by 95%"
- Scale: "serving 500,000+ events daily", "automating 100% of the backend API test suite"
- Accuracy: "reaching an accuracy of 83%"
- Efficiency: "reduced customer time-to-analysis by 75%", "reduced manual testing efforts by 80%"

**Avoid:** vague statements without tech specifics; "responsible for"; listing tech at the end of the bullet instead of inline in the action.
""",

    "finance": """\
## Domain-Specific Norms: Finance / Investment Banking
Apply these norms on top of the general rules above.

**Action Verbs (prefer):** Advised, Executed, Modeled, Analyzed, Prepared, Coordinated, Originated, Evaluated, Structured, Supported, Performed, Constructed

**Lead with:** Deal size ($XXXm / $XXXBn) or transaction type when the original mentions a deal
- Pattern: "Member of deal team on $[X]B [transaction type] advising [Target/Acquirer]"
- Pattern: "[Verb] [financial analysis type] for [deal context/client tier]"
- Good: "Member of deal team on $3.2 billion acquisition of a publicly traded company by a large-cap private equity firm"
- Good: "Built dynamic LBO model with multiple operating and pro forma capital structure scenarios to determine private equity sponsor affordability based on projected IRR and LCFV Yield"
- Good: "Prepared CIM and pitch book for $700MM debt financing transaction in the energy sector"

**Finance vocabulary — use naturally where truthful:**
- Documents: CIM (Confidential Information Memorandum), pitch book, information memorandum, teaser, management presentation
- Analysis types: LBO (Leveraged Buyout), M&A, DCF (Discounted Cash Flow), precedent transactions, comparable companies (comps), accretion/dilution analysis, pro forma, sensitivity analysis, operating model, 3-statement model
- Financial metrics: IRR, EBITDA, EBITDA margins, revenue, COGS, capital structure, debt drawdown, covenant compliance
- Modeling verbs: built, constructed, prepared, performed, ran

**Tools — reference only if truthful:** Bloomberg, CapitalIQ, Excel (financial modeling), PowerPoint (pitch materials)

**Outcome proxies when % metrics are not available:**
- Deal size: "$700MM transaction", "$3.2 billion acquisition"
- Deal status: "Closed July 2020", "Active", "Pending"
- Client/counterparty tier: "publicly traded company", "Fortune 500", "PE sponsor"
- Geographic scope: "across Americas, Europe and Asia-Pacific", "across 37 product lines"

**Avoid:** Technology-style % efficiency metrics where not applicable to the work described; starting bullets with "Responsible for" — always reframe to active voice ("Prepared" instead of "Responsible for preparing").
""",

    "consulting": """\
## Domain-Specific Norms: Management Consulting
Apply these norms on top of the general rules above.

**Action Verbs (prefer):** Advised, Delivered, Structured, Synthesised, Developed, Presented, Facilitated, Coordinated, Diagnosed, Recommended, Designed, Led

**Lead with:** Client impact or business outcome
- Pattern: "[Verb] [deliverable type] for [client context], [resulting in/enabling] [business outcome]"
- Good: "Structured go-to-market diagnostic for a PE-backed retail client, identifying $4m cost reduction opportunity"
- Good: "Developed recommendations across 5 workstreams for a Fortune 500 consumer goods client, enabling $12m annual savings"

**Consulting vocabulary — use naturally where truthful:**
- Structure terms: workstream, deliverable, MECE framework, top-down, structured problem-solving, hypothesis-driven
- Process terms: diagnostic, discovery phase, client engagement, stakeholder alignment, steering committee, executive presentation
- Output terms: recommendations, board deck, business case, implementation roadmap

**Outcome formats to prefer:**
- "$Xm cost reduction", "X% efficiency gain", "X new markets entered", "X% improvement in [metric]"
- Team/scope: "across [X] business units", "for [Fortune 500 / PE-backed / government] client", "in [X] countries"

**Avoid:** Tech-heavy descriptions (unless in tech consulting); "responsible for"; bullets with no outcome or scope signal.
""",

    "quant": """\
## Domain-Specific Norms: Quantitative Finance / Algorithmic Trading
Apply these norms on top of the general rules above.

**Action Verbs (prefer):** Developed, Researched, Implemented, Backtested, Deployed, Optimised, Modeled, Calibrated, Engineered, Built, Analysed

**Lead with:** Strategy/model performance OR technical achievement — whichever is stronger
- Pattern (research): "[Verb] [strategy/model type] using [method/tech], achieving [performance metric]"
- Pattern (engineering): "[Verb] [system component] in [language], achieving [latency/throughput metric]"
- Good: "Developed mean-reversion equity strategy using Python and scikit-learn, achieving 1.4 Sharpe ratio over 3-year backtest"
- Good: "Built cross-sectional factor model on 1,000+ US equities using XGBoost and SHAP, generating [X]% annualised alpha"
- Good: "Implemented low-latency order execution engine in C++, achieving <50μs round-trip latency on co-located infrastructure"
- Good: "Backtested momentum strategy on 10 years of tick data, achieving Sharpe of 1.8 with max drawdown of 12%"

**Quant vocabulary — use naturally where truthful:**
- Strategy types: alpha generation, signal research, momentum, mean reversion, statistical arbitrage (stat arb), pairs trading, market making, execution optimisation, delta hedging
- Model types: factor model, covariance matrix estimation, regime detection, volatility surface, Monte Carlo simulation, GARCH, PCA, Kalman filter
- Performance metrics: Sharpe ratio, Sortino ratio, information ratio, maximum drawdown, annualised alpha/return, P&L, hit rate, win/loss ratio, turnover
- Data: tick data, order book (L2/L3), OHLCV, alternative data, sentiment data, corporate actions
- Execution: FIX protocol, market impact, TWAP/VWAP, slippage, co-location, latency (μs/ms)

**Tools — reference only if truthful:** Python (pandas, numpy, scipy, statsmodels, scikit-learn), C++, R, MATLAB, kdb+/q, Bloomberg, Refinitiv/Eikon, QuantLib, Julia

**Performance outcome formats (highest priority — use these when available):**
- Strategy: "achieving 1.4 Sharpe ratio over [X]-year backtest", "generating [X]% annualised alpha", "with maximum drawdown of [X]%"
- System: "<50μs round-trip latency", "processing 10M+ ticks/day", "[X]% reduction in slippage"
- Deployment: "deployed to production managing $[X]m in AUM", "live since [date]"
- Competition/selection: "1 of 80 students selected for Citadel Trading Invitational", "finalist in Jane Street ETC"

**Avoid:** Generic IB vocabulary (pitchbooks, CIM) where not applicable; technology-style cost/user metrics as the primary outcome — quant bullets are judged on financial performance first, engineering scale second.
""",
}


def _get_domain_guidance(domain: str) -> str:
    """Map a JD domain string to domain-specific tailoring guidance.

    Uses keyword matching so "investment banking" → finance, "algorithmic trading" → quant, etc.
    Returns an empty string for unrecognised domains (graceful fallback).
    Quant is checked FIRST because "quantitative finance" is more specific than "finance".
    """
    if not domain:
        return ""
    d = domain.lower()
    # Quant / Trading — check BEFORE finance; "quantitative finance" → quant not generic finance
    if any(
        kw in d
        for kw in (
            "quant",
            "algorithmic",
            "algo trading",
            "prop trading",
            "trading",
            "market making",
            "systematic",
            "high frequency",
            "hft",
            "statistical arbitrage",
        )
    ):
        return DOMAIN_GUIDANCE["quant"]
    # Finance / IB — check before tech because "financial technology" should → finance
    if any(
        kw in d
        for kw in (
            "finance",
            "banking",
            "investment",
            "financial services",
            "capital markets",
            "private equity",
            "asset management",
            "hedge fund",
            "venture capital",
            "wealth management",
        )
    ):
        return DOMAIN_GUIDANCE["finance"]
    # Consulting
    if any(
        kw in d
        for kw in (
            "consulting",
            "advisory",
            "management consulting",
        )
    ):
        return DOMAIN_GUIDANCE["consulting"]
    # Tech / Software
    if any(
        kw in d
        for kw in (
            "tech",
            "software",
            "engineering",
            "data",
            "machine learning",
            " ai",
            "artificial intelligence",
            "saas",
            "cloud",
            "cybersecurity",
            "security",
            "product",
        )
    ):
        return DOMAIN_GUIDANCE["tech"]
    return ""
