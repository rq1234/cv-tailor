"""Adaptive page-fitting: bullet trimming and content height estimation."""

from __future__ import annotations

# Approximate chars that fit on one line at 11pt in the Jake Gutierrez template
# (US letter, 1in left/right margins widened by 0.5in each side → ~6.5in text width)
_CHARS_PER_LINE = 100

# Approximate line-unit budgets.  Each "line" is one rendered text line at 11pt.
# The Jake Gutierrez template squeezes ~52 lines onto a US letter page at 11pt.
_LINE_BUDGET_1PAGE = 52.0
_LINE_BUDGET_2PAGE = 108.0


def _trim_bullet(text: str) -> str:
    """Trim a bullet point to keep it within ~2 rendered lines.

    - ≤ 90 chars : return as-is
    - 90–200 chars: apply phrase substitutions then stop-word filtering
    - > 155 chars after trimming: hard-truncate at the last word boundary
    """
    if not text or len(text) <= 90:
        return text

    # Phase 1: replace wordy phrases with shorter equivalents
    subs = [
        ("in order to", "to"),
        ("for the purpose of", "to"),
        ("responsible for", "led"),
        ("as well as", "and"),
        ("a wide range of", "various"),
        ("a variety of", "various"),
        ("utilized", "used"),
        ("leveraged", "used"),
        ("successfully ", ""),
        ("effectively ", ""),
        ("efficiently ", ""),
        ("significantly ", ""),
        ("substantially ", ""),
        ("demonstrated ability to ", ""),
        ("contributed to the ", ""),
        ("contributed to ", ""),
    ]
    trimmed = text
    for src, dst in subs:
        trimmed = trimmed.replace(src, dst)
    trimmed = " ".join(trimmed.split())

    if len(trimmed) <= 90:
        return trimmed

    # Phase 2: drop filler stop-words from the *middle* of the sentence
    if len(trimmed) > 105:
        tokens = trimmed.split()
        stop_words = {"a", "an", "the", "to", "for", "of", "on", "in", "that", "which", "with"}
        if len(tokens) > 8:
            filtered = (
                tokens[:3]
                + [t for t in tokens[3:-3] if t.lower() not in stop_words]
                + tokens[-3:]
            )
            candidate = " ".join(filtered)
            if len(candidate) < len(trimmed):
                trimmed = candidate

    # Phase 3: hard-truncate at word boundary before 155 chars
    if len(trimmed) > 155:
        cut = trimmed[:152].rfind(" ")
        trimmed = (trimmed[:cut] + "...") if cut > 80 else (trimmed[:152] + "...")

    return trimmed


def _soft_trim_bullet(text: str, target_len: int = 95, max_len: int = 110) -> str:
    """Conservatively trim bullets — delegates to _trim_bullet."""
    return _trim_bullet(text)


def _estimate_bullet_lines(text: str) -> float:
    """Return the estimated number of rendered lines for one bullet."""
    if not text:
        return 0.0
    return max(1.0, len(text) / _CHARS_PER_LINE) + 0.15


def _estimate_content_lines(
    experiences: list,
    education: list,
    projects: list,
    activities: list,
    skills_by_category: dict,
) -> float:
    """Estimate total rendered line count for the full CV."""
    lines = 3.0  # name + contact header

    if education:
        lines += 1.5
        for edu in education:
            lines += 1.5
            for ach in edu.get("achievements", []):
                lines += _estimate_bullet_lines(ach)
            mods = edu.get("modules", [])
            if mods:
                lines += _estimate_bullet_lines("Relevant coursework: " + ", ".join(mods))

    if experiences:
        lines += 1.5
        for exp in experiences:
            lines += 1.5
            for b in exp.get("bullets", []):
                lines += _estimate_bullet_lines(b)

    if projects:
        lines += 1.5
        for proj in projects:
            lines += 1.5
            for b in proj.get("bullets", []):
                lines += _estimate_bullet_lines(b)

    if activities:
        lines += 1.5
        for act in activities:
            lines += 1.5
            for b in act.get("bullets", []):
                lines += _estimate_bullet_lines(b)

    if skills_by_category:
        lines += 1.5
        lines += len(skills_by_category)

    return lines


def _compute_page_limits(has_projects: bool, has_activities: bool, max_pages: int = 1) -> dict:
    """Return per-section item caps so the CV fits within the target page count.

    1-page limits (Jake Gutierrez template at 11pt):
      - Full profile (exp + proj + act): 4 exp, 3 proj, 2 act
      - IB/Finance (exp + act, no proj):  5 exp, 3 act
      - Tech (exp + proj, no act):        4 exp, 4 proj
      - Exp-only (no proj, no act):       6 exp

    2-page limits are approximately doubled.
    """
    if max_pages >= 2:
        if has_projects and has_activities:
            return {"exp": 8, "proj": 6, "act": 4}
        if has_projects and not has_activities:
            return {"exp": 8, "proj": 8, "act": 0}
        if not has_projects and has_activities:
            return {"exp": 10, "proj": 0, "act": 6}
        return {"exp": 12, "proj": 0, "act": 0}
    # 1-page limits
    if has_projects and has_activities:
        return {"exp": 4, "proj": 3, "act": 2}
    if has_projects and not has_activities:
        return {"exp": 4, "proj": 4, "act": 0}
    if not has_projects and has_activities:
        return {"exp": 5, "proj": 0, "act": 3}
    return {"exp": 6, "proj": 0, "act": 0}


def _fit_content_to_page(
    experiences: list,
    education: list,
    projects: list,
    activities: list,
    skills_by_category: dict,
    line_budget: float,
) -> None:
    """Shorten bullets in-place until the estimated line count fits line_budget.

    Trimming priority (least → most important content):
    1. Shorten all bullet text via _trim_bullet.
    2. Drop trailing bullets from oldest activities.
    3. Drop trailing bullets from oldest projects.
    4. Drop trailing bullets from oldest experiences (keep ≥ 1 per entry).
    """
    for entry in experiences + projects + activities:
        entry["bullets"] = [_trim_bullet(b) for b in entry.get("bullets", [])]
    for edu in education:
        edu["achievements"] = [_trim_bullet(a) for a in edu.get("achievements", [])]

    def _lines() -> float:
        return _estimate_content_lines(experiences, education, projects, activities, skills_by_category)

    if _lines() <= line_budget:
        return

    for act in reversed(activities):
        while act.get("bullets") and _lines() > line_budget:
            act["bullets"].pop()

    if _lines() <= line_budget:
        return

    for proj in reversed(projects):
        while proj.get("bullets") and _lines() > line_budget:
            proj["bullets"].pop()

    if _lines() <= line_budget:
        return

    for exp in reversed(experiences):
        while len(exp.get("bullets", [])) > 1 and _lines() > line_budget:
            exp["bullets"].pop()
