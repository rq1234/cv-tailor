"""Generate LaTeX source from a CvVersion (Jake Gutierrez resume template)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.tables import CvVersion

from ._context import _build_cv_context
from ._fitting import _trim_bullet
from ._text import (
    _clean_bullet_text,
    _clean_location,
    _escape_latex,
    _escape_latex_url,
    _is_meaningful_bullet,
)

# ── LaTeX preamble (Jake Gutierrez template) ─────────────────────────────────
_PREAMBLE = r"""\documentclass[letterpaper,11pt]{article}

\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\input{glyphtounicode}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}

\urlstyle{same}

\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

% Sections formatting
\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

% Ensure that generate pdf is machine readable/ATS parsable
\pdfgentounicode=1

% Custom commands
\newcommand{\resumeItem}[1]{
  \item\small{
    {#1 \vspace{-2pt}}
  }
}

\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubSubheading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textit{\small#1} & \textit{\small #2} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}

\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}

\begin{document}
"""


def _date_range(start: str, end: str) -> str:
    if start and end:
        return f"{start} -- {end}"
    return start or end or ""


def _render_bullet(bullet: str) -> str | None:
    """Clean, trim and escape one bullet. Returns None if the result is empty."""
    cleaned = _clean_bullet_text(bullet)
    trimmed = _trim_bullet(cleaned)
    if not trimmed or not _is_meaningful_bullet(trimmed):
        return None
    return _escape_latex(trimmed)


async def generate_latex(db: AsyncSession, cv_version: CvVersion, user_id: uuid.UUID) -> str:
    """Generate LaTeX source (not compiled PDF) from the final CV data."""
    context = await _build_cv_context(db, cv_version, user_id)
    profile = context["profile"]

    lines: list[str] = [_PREAMBLE]

    # ── Header ───────────────────────────────────────────────────────────────
    name = _escape_latex(profile.get("name", "Your Name"))
    lines.append(r"\begin{center}")
    lines.append(f"    \\textbf{{\\Huge \\scshape {name}}} \\\\ \\vspace{{1pt}}")

    contact_items = []
    if phone := profile.get("phone"):
        contact_items.append(f"\\small {_escape_latex(phone)}")
    if email := profile.get("email"):
        contact_items.append(
            f"\\href{{mailto:{_escape_latex_url(email)}}}{{\\underline{{{_escape_latex(email)}}}}}"
        )
    if linkedin := profile.get("linkedin_url"):
        display = linkedin.replace("https://", "").replace("http://", "")
        contact_items.append(
            f"\\href{{{_escape_latex_url(linkedin)}}}{{\\underline{{{_escape_latex(display)}}}}}"
        )
    if portfolio := profile.get("portfolio_url"):
        display = portfolio.replace("https://", "").replace("http://", "")
        contact_items.append(
            f"\\href{{{_escape_latex_url(portfolio)}}}{{\\underline{{{_escape_latex(display)}}}}}"
        )
    if location := profile.get("location"):
        contact_items.append(_escape_latex(location))

    lines.append("    \\small " + " $|$ ".join(contact_items))
    lines.append(r"\end{center}")
    lines.append("")

    # ── Education ────────────────────────────────────────────────────────────
    if context["education"]:
        lines.append(r"\section{Education}")
        lines.append(r"  \resumeSubHeadingListStart")
        for edu in context["education"]:
            degree = _escape_latex(edu.get("degree", "Degree"))
            institution = _escape_latex(edu.get("institution", "Institution"))
            dates = _date_range(edu.get("date_start", ""), edu.get("date_end", ""))
            location_str = _escape_latex(_clean_location(edu.get("location", "")))
            lines.append(f"    \\resumeSubheading{{{institution}}}{{{dates}}}{{{degree}}}{{{location_str}}}")

            if edu.get("achievements") or edu.get("modules"):
                lines.append(r"      \resumeItemListStart")
                for ach in edu.get("achievements", []):
                    if rendered := _render_bullet(ach):
                        lines.append(f"        \\resumeItem{{{rendered}}}")
                if edu.get("modules"):
                    modules_escaped = _escape_latex(_clean_bullet_text(", ".join(edu["modules"])))
                    lines.append(f"        \\resumeItem{{\\textbf{{Coursework:}} {modules_escaped}}}")
                lines.append(r"      \resumeItemListEnd")

        lines.append(r"  \resumeSubHeadingListEnd")
        lines.append("")

    # ── Work Experience ───────────────────────────────────────────────────────
    if context["experiences"]:
        lines.append(r"\section{Experience}")
        lines.append(r"  \resumeSubHeadingListStart")
        for exp in context["experiences"]:
            role = _escape_latex(exp.get("role_title", "Role"))
            company = _escape_latex(exp.get("company", "Company"))
            dates = _date_range(exp.get("date_start", ""), exp.get("date_end", ""))
            location_str = _escape_latex(_clean_location(exp.get("location", "")))
            lines.append(f"    \\resumeSubheading{{{company}}}{{{dates}}}{{{role}}}{{{location_str}}}")

            if exp.get("bullets"):
                lines.append(r"      \resumeItemListStart")
                for bullet in exp["bullets"]:
                    if rendered := _render_bullet(bullet):
                        lines.append(f"        \\resumeItem{{{rendered}}}")
                lines.append(r"      \resumeItemListEnd")

        lines.append(r"  \resumeSubHeadingListEnd")
        lines.append("")

    # ── Projects ─────────────────────────────────────────────────────────────
    if context["projects"]:
        lines.append(r"\section{Projects}")
        lines.append(r"    \resumeSubHeadingListStart")
        for proj in context["projects"]:
            name_str = _escape_latex(proj.get("name", "Project"))
            dates = _date_range(proj.get("date_start", ""), proj.get("date_end", ""))
            skill_tags = proj.get("skill_tags", [])
            if skill_tags:
                tech_str = _escape_latex(", ".join(skill_tags[:4]))
                title = f"\\textbf{{{name_str}}} $|$ \\emph{{{tech_str}}}"
            else:
                title = f"\\textbf{{{name_str}}}"
            lines.append(f"      \\resumeProjectHeading{{{title}}}{{{dates}}}")

            if proj.get("bullets"):
                lines.append(r"          \resumeItemListStart")
                for bullet in proj["bullets"]:
                    if rendered := _render_bullet(bullet):
                        lines.append(f"            \\resumeItem{{{rendered}}}")
                lines.append(r"          \resumeItemListEnd")

        lines.append(r"    \resumeSubHeadingListEnd")
        lines.append("")

    # ── Leadership & Activities ───────────────────────────────────────────────
    if context["activities"]:
        lines.append(r"\section{Leadership \& Activities}")
        lines.append(r"  \resumeSubHeadingListStart")
        for act in context["activities"]:
            role = _escape_latex(act.get("role_title", "Role"))
            org = _escape_latex(act.get("organization", "Organization"))
            dates = _date_range(act.get("date_start", ""), act.get("date_end", ""))
            location_str = _escape_latex(_clean_location(act.get("location", "")))
            lines.append(f"    \\resumeSubheading{{{role}}}{{{dates}}}{{{org}}}{{{location_str}}}")

            if act.get("bullets"):
                lines.append(r"      \resumeItemListStart")
                for bullet in act["bullets"]:
                    if rendered := _render_bullet(bullet):
                        lines.append(f"        \\resumeItem{{{rendered}}}")
                lines.append(r"      \resumeItemListEnd")

        lines.append(r"  \resumeSubHeadingListEnd")
        lines.append("")

    # ── Technical Skills ──────────────────────────────────────────────────────
    if context["skills_by_category"]:
        lines.append(r"\section{Technical Skills}")
        lines.append(r" \begin{itemize}[leftmargin=0.15in, label={}]")
        lines.append(r"    \small{\item{")

        allowed = ["Technical", "Certification", "Interests"]
        categories = [
            (c, context["skills_by_category"][c])
            for c in allowed
            if c in context["skills_by_category"]
        ]
        for i, (category, skill_list) in enumerate(categories):
            cat_escaped = _escape_latex(category)
            skills_escaped = ", ".join(_escape_latex(s) for s in skill_list)
            line = f"     \\textbf{{{cat_escaped}}}{{: {skills_escaped}}}"
            if i < len(categories) - 1:
                line += " \\\\"
            lines.append(line)

        lines.append(r"    }}")
        lines.append(r" \end{itemize}")
        lines.append("")

    lines.append(r"\end{document}")
    return "\n".join(lines)
