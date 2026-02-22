"""Export service — generates LaTeX from final CV data."""

from __future__ import annotations

import re
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db_helpers import fetch_latest_profile
from backend.models.tables import (
    Activity,
    CvVersion,
    Education,
    Project,
    Skill,
    WorkExperience,
)
from backend.utils import extract_bullet_texts, split_description_to_bullets



def _format_date(d: date | str | None) -> str:
    if d is None:
        return ""
    if isinstance(d, date):
        return d.strftime("%b %Y")
    return str(d)


async def _build_cv_context(
    db: AsyncSession,
    cv_version: CvVersion,
    user_id: uuid.UUID,
) -> dict:
    """Build the template context dict from a CvVersion and its referenced records."""
    # Profile
    profile_row = await fetch_latest_profile(db, user_id)
    profile = {}
    if profile_row:
        profile = {
            "name": profile_row.full_name,
            "email": profile_row.email,
            "phone": profile_row.phone,
            "location": profile_row.location,
            "linkedin_url": profile_row.linkedin_url,
            "portfolio_url": profile_row.portfolio_url,
            "summary": profile_row.summary,
        }

    # Work experiences — sorted by date descending (most recent first)
    experiences = []
    exp_ids = cv_version.selected_experiences or []
    if exp_ids:
        result = await db.execute(
            select(WorkExperience)
            .where(
                WorkExperience.id.in_(exp_ids),
                WorkExperience.user_id == user_id,
            )
            .order_by(WorkExperience.date_start.desc().nullslast())
        )
        for exp in result.scalars().all():
            exp_id_str = str(exp.id)
            # Check if we have accepted/final bullets for this experience
            final_cv = cv_version.final_cv_json or {}
            accepted = cv_version.accepted_changes or {}

            if exp_id_str in accepted:
                bullets = accepted[exp_id_str]
                if isinstance(bullets, dict):
                    bullets = bullets.get("bullets", [])
            elif exp_id_str in final_cv:
                bullets = final_cv[exp_id_str]
                if isinstance(bullets, dict):
                    bullets = bullets.get("bullets", [])
            else:
                bullets = extract_bullet_texts(exp.bullets)

            if isinstance(bullets, list):
                bullets = _normalize_bullets(bullets)
            # Cap bullets to 3 max for single-page fit
            bullets = bullets[:3] if isinstance(bullets, list) else []

            experiences.append({
                "company": exp.company,
                "role_title": exp.role_title,
                "location": exp.location,
                "date_start": _format_date(exp.date_start),
                "date_end": "Present" if exp.is_current else _format_date(exp.date_end),
                "bullets": bullets if isinstance(bullets, list) else [],
            })

    # Education
    education = []
    edu_ids = cv_version.selected_education or []
    accepted = cv_version.accepted_changes or {}
    if edu_ids:
        result = await db.execute(
            select(Education).where(
                Education.id.in_(edu_ids),
                Education.user_id == user_id,
            )
        )
        for edu in result.scalars().all():
            edu_id_str = str(edu.id)
            
            # Check if user manually edited this education entry
            if f"education_{edu_id_str}" in accepted:
                manual_items = accepted[f"education_{edu_id_str}"]
                if isinstance(manual_items, dict):
                    achievements = manual_items.get("achievements", [])
                    modules = manual_items.get("modules", [])
                    if isinstance(achievements, str):
                        achievements = [a.strip() for a in achievements.split(",") if a.strip()]
                    if isinstance(modules, str):
                        modules = [m.strip() for m in modules.split(",") if m.strip()]
                elif isinstance(manual_items, list):
                    # Legacy format: combined achievements + modules list
                    achievements = manual_items[:2]
                    modules = []
                else:
                    achievements = []
                    modules = []
            else:
                # Use database values
                achievements = []
                if isinstance(edu.achievements, list):
                    achievements = edu.achievements
                elif isinstance(edu.achievements, dict):
                    achievements = edu.achievements.get("items", [])
                elif isinstance(edu.achievements, str):
                    achievements = [a.strip() for a in edu.achievements.split(",") if a.strip()]
                modules = []
                if isinstance(edu.modules, list):
                    modules = edu.modules
                elif isinstance(edu.modules, dict):
                    modules = edu.modules.get("items", [])
                elif isinstance(edu.modules, str):
                    modules = [m.strip() for m in edu.modules.split(",") if m.strip()]

            # Cap achievements to 2 max for single-page fit
            if isinstance(achievements, list):
                achievements = [str(a).strip() for a in achievements if str(a).strip()]
            if isinstance(modules, list):
                modules = [str(m).strip() for m in modules if str(m).strip()]
            achievements = achievements[:2] if isinstance(achievements, list) else []
            # Cap modules to 4 items, but they'll be on ONE line
            modules = modules[:4] if isinstance(modules, list) else []

            education.append({
                "institution": edu.institution,
                "degree": edu.degree,
                "grade": edu.grade,
                "date_start": _format_date(edu.date_start),
                "date_end": _format_date(edu.date_end),
                "location": edu.location,
                "achievements": achievements,
                "modules": modules,
            })

    # Projects — sorted by date descending (most recent first), deduplicated by name
    projects = []
    seen_proj_names: set[str] = set()
    proj_ids = cv_version.selected_projects or []
    if proj_ids:
        result = await db.execute(
            select(Project)
            .where(Project.id.in_(proj_ids), Project.user_id == user_id)
            .order_by(Project.date_start.desc().nullslast())
        )
        for proj in result.scalars().all():
            name_lower = (proj.name or "").strip().lower()
            if name_lower and name_lower in seen_proj_names:
                continue
            if name_lower:
                seen_proj_names.add(name_lower)
            proj_id_str = str(proj.id)
            final_cv = cv_version.final_cv_json or {}
            accepted = cv_version.accepted_changes or {}

            if proj_id_str in accepted:
                bullets = accepted[proj_id_str]
                if isinstance(bullets, dict):
                    bullets = bullets.get("bullets", [])
            elif proj_id_str in final_cv:
                bullets = final_cv[proj_id_str]
                if isinstance(bullets, dict):
                    bullets = bullets.get("bullets", [])
            else:
                bullets = extract_bullet_texts(proj.bullets)

            if isinstance(bullets, list):
                bullets = _normalize_bullets(bullets)
            # If no bullets, split description into separate sentences
            bullets = bullets[:3] if isinstance(bullets, list) else []
            if not bullets and proj.description:
                bullets = split_description_to_bullets(proj.description)[:3]

            projects.append({
                "name": proj.name,
                "description": proj.description,
                "url": proj.url,
                "date_start": _format_date(proj.date_start),
                "date_end": _format_date(proj.date_end),
                "bullets": bullets if isinstance(bullets, list) else [],
                "skill_tags": proj.skill_tags or [],
            })

    # Activities — sorted by date descending (most recent first)
    activities = []
    act_ids = cv_version.selected_activities or []
    if act_ids:
        result = await db.execute(
            select(Activity)
            .where(Activity.id.in_(act_ids), Activity.user_id == user_id)
            .order_by(Activity.date_start.desc().nullslast())
        )
        for act in result.scalars().all():
            act_id_str = str(act.id)
            final_cv = cv_version.final_cv_json or {}
            accepted = cv_version.accepted_changes or {}

            if act_id_str in accepted:
                bullets = accepted[act_id_str]
                if isinstance(bullets, dict):
                    bullets = bullets.get("bullets", [])
            elif act_id_str in final_cv:
                bullets = final_cv[act_id_str]
                if isinstance(bullets, dict):
                    bullets = bullets.get("bullets", [])
            else:
                bullets = extract_bullet_texts(act.bullets)

            if isinstance(bullets, list):
                bullets = _normalize_bullets(bullets)
            # Cap bullets to 2 max for single-page fit
            bullets = bullets[:2] if isinstance(bullets, list) else []

            activities.append({
                "organization": act.organization,
                "role_title": act.role_title,
                "location": act.location,
                "date_start": _format_date(act.date_start),
                "date_end": "Present" if act.is_current else _format_date(act.date_end),
                "bullets": bullets if isinstance(bullets, list) else [],
            })

    # Skills grouped by category, preserving priority order from selected_skills
    skills_by_category: dict[str, list[str]] = {}
    skill_ids = cv_version.selected_skills or []
    accepted = cv_version.accepted_changes or {}
    if skill_ids:
        result = await db.execute(
            select(Skill).where(Skill.id.in_(skill_ids), Skill.user_id == user_id)
        )
        skills_by_id = {skill.id: skill for skill in result.scalars().all()}
        # Iterate in the order stored in selected_skills (JD-relevant first)
        # Track seen skill names to avoid duplicates
        seen_skills: set[str] = set()
        seen_categories: set[str] = set()
        
        for sid in skill_ids:
            skill = skills_by_id.get(sid)
            if not skill:
                continue
            # Deduplicate by lowercase name
            name_lower = skill.name.strip().lower()
            if name_lower in seen_skills:
                continue
            seen_skills.add(name_lower)
            cat = (skill.category or "Other").capitalize()
            if cat == "Interest":
                cat = "Interests"
            
            # Check if user manually edited this skill category
            skill_key = f"skills_{cat}"
            if skill_key in accepted and cat not in seen_categories:
                # Use manually edited skills for this category
                seen_categories.add(cat)
                manual_skills = accepted[skill_key]
                if isinstance(manual_skills, list) and len(manual_skills) > 0:
                    # manual_skills is now an array of individual skill strings (not comma-separated)
                    # Filter out empty strings
                    parsed_skills = [s.strip() for s in manual_skills if isinstance(s, str) and s.strip()]
                    parsed_skills = _dedupe_preserve_order(parsed_skills)
                    if parsed_skills:
                        skills_by_category[cat] = parsed_skills
                continue
            
            if cat not in skills_by_category:
                skills_by_category[cat] = []
            skills_by_category[cat].append(skill.name)

        for cat, items in list(skills_by_category.items()):
            skills_by_category[cat] = _dedupe_preserve_order(items)

    limits = _compute_page_limits(bool(projects), bool(activities))
    return {
        "profile": profile,
        "experiences": experiences[: limits["exp"]],
        "education": education,
        "projects": projects[: limits["proj"]] if limits["proj"] else projects,
        "activities": activities[: limits["act"]] if limits["act"] else activities,
        "skills_by_category": skills_by_category,
    }



def _escape_latex_url(url: str) -> str:
    """Escape characters that break LaTeX inside \\href{url} arguments.

    URLs live inside a brace group so only { } % # \\ need escaping.
    Other URL characters (: / ? = & @) are safe in this context.
    """
    if not url:
        return ""
    url = str(url)
    url = url.replace("\\", r"\textbackslash{}")
    url = url.replace("{", r"\{")
    url = url.replace("}", r"\}")
    url = url.replace("%", r"\%")
    url = url.replace("#", r"\#")
    return url


def _escape_latex(text: str) -> str:
    """Escape special LaTeX characters."""
    if not text:
        return ""
    text = str(text)
    # Strip null bytes and ASCII control characters (keep printable + tab/space)
    text = "".join(ch for ch in text if ch >= " " or ch == "\t")
    # Backslash MUST be replaced first to avoid double-escaping
    text = text.replace("\\", r"\textbackslash{}")
    for char, replacement in [
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\^{}"),
    ]:
        text = text.replace(char, replacement)
    return text


def _clean_bullet_text(text: str) -> str:
    """Clean whitespace from bullet text - remove newlines and collapse multiple spaces."""
    if not text:
        return ""
    text = str(text)
    # Replace newlines and tabs with spaces
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    # Collapse multiple spaces into single space
    text = " ".join(text.split())
    return text


def _is_meaningful_bullet(text: str) -> bool:
    """Return True if text has any alphanumeric content after cleanup."""
    if not text:
        return False
    return any(ch.isalnum() for ch in text)


def _normalize_bullets(bullets: list) -> list[str]:
    """Normalize bullet list to clean text and drop empty entries."""
    normalized: list[str] = []
    for bullet in bullets:
        if isinstance(bullet, dict):
            bullet = bullet.get("text", "")
        cleaned = _clean_bullet_text(bullet)
        if _is_meaningful_bullet(cleaned):
            normalized.append(cleaned)
    return normalized


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    """Deduplicate strings while preserving order (case-insensitive)."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _compute_page_limits(has_projects: bool, has_activities: bool) -> dict:
    """Return per-section item caps so the CV fits one page regardless of content mix.

    The Jake Gutierrez template at 11pt holds roughly:
      - Full profile (exp + proj + act): 4 exp, 3 proj, 2 act
      - IB/Finance (exp + act, no proj):  5 exp, 3 act
      - Tech (exp + proj, no act):        4 exp, 4 proj
      - Exp-only (no proj, no act):       6 exp
    """
    if has_projects and has_activities:
        return {"exp": 4, "proj": 3, "act": 2}
    if has_projects and not has_activities:
        return {"exp": 4, "proj": 4, "act": 0}
    if not has_projects and has_activities:
        return {"exp": 5, "proj": 0, "act": 3}
    # No projects, no activities
    return {"exp": 6, "proj": 0, "act": 0}


def _soft_trim_bullet(text: str, target_len: int = 95, max_len: int = 110) -> str:
    """Conservatively trim bullets that are just barely over one line."""
    if not text:
        return ""
    if len(text) <= target_len or len(text) > max_len:
        return text

    replacements = {
        "utilized": "used",
        "leveraged": "used",
        "in order to": "to",
        "for the purpose of": "to",
        "responsible for": "led",
        "successfully ": "",
        "effectively ": "",
    }
    lowered = text
    for src, dst in replacements.items():
        lowered = lowered.replace(src, dst)

    # Final cleanup for double spaces after replacements
    trimmed = " ".join(lowered.split())

    if len(trimmed) <= target_len:
        return trimmed

    # Aggressive micro-trim: remove small filler words if still slightly over
    tokens = trimmed.split()
    stop_words = {"a", "an", "the", "to", "for", "of", "on", "in", "that", "which"}
    if len(trimmed) <= max_len:
        filtered = [t for t in tokens if t.lower() not in stop_words]
        trimmed = " ".join(filtered)

    return trimmed


async def generate_latex(db: AsyncSession, cv_version: CvVersion, user_id: uuid.UUID) -> str:
    """Generate LaTeX source (not compiled PDF)."""
    context = await _build_cv_context(db, cv_version, user_id)
    profile = context["profile"]

    # Start LaTeX document - Jake Gutierrez resume template
    latex_lines = [
        r"\documentclass[letterpaper,11pt]{article}",
        "",
        r"\usepackage{latexsym}",
        r"\usepackage[empty]{fullpage}",
        r"\usepackage{titlesec}",
        r"\usepackage{marvosym}",
        r"\usepackage[usenames,dvipsnames]{color}",
        r"\usepackage{verbatim}",
        r"\usepackage{enumitem}",
        r"\usepackage[hidelinks]{hyperref}",
        r"\usepackage{fancyhdr}",
        r"\usepackage[english]{babel}",
        r"\usepackage{tabularx}",
        r"\input{glyphtounicode}",
        "",
        r"\pagestyle{fancy}",
        r"\fancyhf{}",
        r"\fancyfoot{}",
        r"\renewcommand{\headrulewidth}{0pt}",
        r"\renewcommand{\footrulewidth}{0pt}",
        "",
        r"\addtolength{\oddsidemargin}{-0.5in}",
        r"\addtolength{\evensidemargin}{-0.5in}",
        r"\addtolength{\textwidth}{1in}",
        r"\addtolength{\topmargin}{-.5in}",
        r"\addtolength{\textheight}{1.0in}",
        "",
        r"\urlstyle{same}",
        "",
        r"\raggedbottom",
        r"\raggedright",
        r"\setlength{\tabcolsep}{0in}",
        "",
        r"% Sections formatting",
        r"\titleformat{\section}{",
        r"  \vspace{-4pt}\scshape\raggedright\large",
        r"}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]",
        "",
        r"% Ensure that generate pdf is machine readable/ATS parsable",
        r"\pdfgentounicode=1",
        "",
        r"% Custom commands",
        r"\newcommand{\resumeItem}[1]{",
        r"  \item\small{",
        r"    {#1 \vspace{-2pt}}",
        r"  }",
        r"}",
        "",
        r"\newcommand{\resumeSubheading}[4]{",
        r"  \vspace{-2pt}\item",
        r"    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}",
        r"      \textbf{#1} & #2 \\",
        r"      \textit{\small#3} & \textit{\small #4} \\",
        r"    \end{tabular*}\vspace{-7pt}",
        r"}",
        "",
        r"\newcommand{\resumeSubSubheading}[2]{",
        r"    \item",
        r"    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}",
        r"      \textit{\small#1} & \textit{\small #2} \\",
        r"    \end{tabular*}\vspace{-7pt}",
        r"}",
        "",
        r"\newcommand{\resumeProjectHeading}[2]{",
        r"    \item",
        r"    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}",
        r"      \small#1 & #2 \\",
        r"    \end{tabular*}\vspace{-7pt}",
        r"}",
        "",
        r"\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}",
        "",
        r"\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}",
        "",
        r"\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}",
        r"\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}",
        r"\newcommand{\resumeItemListStart}{\begin{itemize}}",
        r"\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}",
        "",
        r"\begin{document}",
        "",
    ]

    # Helper to build date range strings
    def _date_range(start: str, end: str) -> str:
        if start and end:
            return f"{start} -- {end}"
        if start:
            return start
        if end:
            return end
        return ""

    # Header
    name = _escape_latex(profile.get("name", "Your Name"))
    email = profile.get("email", "")
    phone = profile.get("phone", "")
    location = profile.get("location", "")
    linkedin = profile.get("linkedin_url", "")
    portfolio = profile.get("portfolio_url", "")

    latex_lines.append(r"\begin{center}")
    latex_lines.append(f"    \\textbf{{\\Huge \\scshape {name}}} \\\\ \\vspace{{1pt}}")

    contact_items = []
    if phone:
        contact_items.append(f"\\small {_escape_latex(phone)}")
    if email:
        contact_items.append(f"\\href{{mailto:{_escape_latex_url(email)}}}{{\\underline{{{_escape_latex(email)}}}}}")
    if linkedin:
        display_linkedin = linkedin.replace("https://", "").replace("http://", "")
        contact_items.append(f"\\href{{{_escape_latex_url(linkedin)}}}{{\\underline{{{_escape_latex(display_linkedin)}}}}}")
    if portfolio:
        display_portfolio = portfolio.replace("https://", "").replace("http://", "")
        contact_items.append(f"\\href{{{_escape_latex_url(portfolio)}}}{{\\underline{{{_escape_latex(display_portfolio)}}}}}")
    if location:
        contact_items.append(_escape_latex(location))

    latex_lines.append("    \\small " + " $|$ ".join(contact_items))
    latex_lines.append(r"\end{center}")
    latex_lines.append("")

    # Education
    if context["education"]:
        latex_lines.append(r"\section{Education}")
        latex_lines.append(r"  \resumeSubHeadingListStart")
        for edu in context["education"]:
            degree = _escape_latex(edu.get("degree", "Degree"))
            institution = _escape_latex(edu.get("institution", "Institution"))
            dates = _date_range(edu.get("date_start", ""), edu.get("date_end", ""))
            location_str = _escape_latex(edu.get("location", ""))

            latex_lines.append(
                f"    \\resumeSubheading{{{institution}}}{{{dates}}}{{{degree}}}{{{location_str}}}"
            )

            has_items = edu.get("achievements") or edu.get("modules")
            if has_items:
                latex_lines.append(r"      \resumeItemListStart")
                for achievement in edu.get("achievements", []):
                    achievement_cleaned = _clean_bullet_text(achievement)
                    achievement_trimmed = _soft_trim_bullet(achievement_cleaned)
                    if achievement_trimmed and _is_meaningful_bullet(achievement_trimmed):
                        achievement_escaped = _escape_latex(achievement_trimmed)
                        latex_lines.append(f"        \\resumeItem{{{achievement_escaped}}}")
                if edu.get("modules"):
                    modules_str = ", ".join(edu["modules"])
                    modules_cleaned = _clean_bullet_text(modules_str)
                    modules_escaped = _escape_latex(modules_cleaned)
                    latex_lines.append(f"        \\resumeItem{{\\textbf{{Coursework:}} {modules_escaped}}}")
                latex_lines.append(r"      \resumeItemListEnd")

        latex_lines.append(r"  \resumeSubHeadingListEnd")
        latex_lines.append("")

    # Work Experience
    if context["experiences"]:
        latex_lines.append(r"\section{Experience}")
        latex_lines.append(r"  \resumeSubHeadingListStart")
        for exp in context["experiences"]:
            role = _escape_latex(exp.get("role_title", "Role"))
            company = _escape_latex(exp.get("company", "Company"))
            dates = _date_range(exp.get("date_start", ""), exp.get("date_end", ""))
            location_str = _escape_latex(exp.get("location", ""))

            latex_lines.append(f"    \\resumeSubheading{{{company}}}{{{dates}}}{{{role}}}{{{location_str}}}")

            if exp.get("bullets"):
                latex_lines.append(r"      \resumeItemListStart")
                for bullet in exp["bullets"]:
                    bullet_cleaned = _clean_bullet_text(bullet)
                    bullet_trimmed = _soft_trim_bullet(bullet_cleaned)
                    if bullet_trimmed and _is_meaningful_bullet(bullet_trimmed):
                        bullet_escaped = _escape_latex(bullet_trimmed)
                        latex_lines.append(f"        \\resumeItem{{{bullet_escaped}}}")
                latex_lines.append(r"      \resumeItemListEnd")

        latex_lines.append(r"  \resumeSubHeadingListEnd")
        latex_lines.append("")

    # Projects
    if context["projects"]:
        latex_lines.append(r"\section{Projects}")
        latex_lines.append(r"    \resumeSubHeadingListStart")
        for proj in context["projects"]:
            name_str = _escape_latex(proj.get("name", "Project"))
            dates = _date_range(proj.get("date_start", ""), proj.get("date_end", ""))

            # Use skill_tags as tech stack in heading (Jake's style: short comma list)
            skill_tags = proj.get("skill_tags", [])
            desc = proj.get("description", "")

            if skill_tags:
                tech_str = _escape_latex(", ".join(skill_tags))
                title = f"\\textbf{{{name_str}}} $|$ \\emph{{{tech_str}}}"
            else:
                title = f"\\textbf{{{name_str}}}"

            latex_lines.append(f"      \\resumeProjectHeading{{{title}}}{{{dates}}}")

            bullets = proj.get("bullets", [])
            if bullets:
                latex_lines.append(r"          \resumeItemListStart")
                for bullet in bullets:
                    bullet_cleaned = _clean_bullet_text(bullet)
                    bullet_trimmed = _soft_trim_bullet(bullet_cleaned)
                    if bullet_trimmed and _is_meaningful_bullet(bullet_trimmed):
                        bullet_escaped = _escape_latex(bullet_trimmed)
                        latex_lines.append(f"            \\resumeItem{{{bullet_escaped}}}")
                latex_lines.append(r"          \resumeItemListEnd")

        latex_lines.append(r"    \resumeSubHeadingListEnd")
        latex_lines.append("")

    # Activities
    if context["activities"]:
        latex_lines.append(r"\section{Leadership \& Activities}")
        latex_lines.append(r"  \resumeSubHeadingListStart")
        for act in context["activities"]:
            role = _escape_latex(act.get("role_title", "Role"))
            org = _escape_latex(act.get("organization", "Organization"))
            dates = _date_range(act.get("date_start", ""), act.get("date_end", ""))
            location_str = _escape_latex(act.get("location", ""))

            latex_lines.append(f"    \\resumeSubheading{{{role}}}{{{dates}}}{{{org}}}{{{location_str}}}")

            if act.get("bullets"):
                latex_lines.append(r"      \resumeItemListStart")
                for bullet in act["bullets"]:
                    bullet_cleaned = _clean_bullet_text(bullet)
                    bullet_trimmed = _soft_trim_bullet(bullet_cleaned)
                    if bullet_trimmed and _is_meaningful_bullet(bullet_trimmed):
                        bullet_escaped = _escape_latex(bullet_trimmed)
                        latex_lines.append(f"        \\resumeItem{{{bullet_escaped}}}")
                latex_lines.append(r"      \resumeItemListEnd")

        latex_lines.append(r"  \resumeSubHeadingListEnd")
        latex_lines.append("")

    # Skills (limit to one line per key category)
    if context["skills_by_category"]:
        latex_lines.append(r"\section{Technical Skills}")
        latex_lines.append(r" \begin{itemize}[leftmargin=0.15in, label={}]")
        latex_lines.append(r"    \small{\item{")

        allowed = ["Technical", "Certification", "Interests"]
        categories = [(c, context["skills_by_category"].get(c, [])) for c in allowed if c in context["skills_by_category"]]
        for i, (category, skill_list) in enumerate(categories):
            cat_escaped = _escape_latex(category)
            skills_escaped = ", ".join(_escape_latex(s) for s in skill_list)
            line = f"     \\textbf{{{cat_escaped}}}{{: {skills_escaped}}}"
            if i < len(categories) - 1:
                line += " \\\\" 
            latex_lines.append(line)

        latex_lines.append(r"    }}")
        latex_lines.append(r" \end{itemize}")
        latex_lines.append("")

    # End document
    latex_lines.append(r"\end{document}")

    return "\n".join(latex_lines)
