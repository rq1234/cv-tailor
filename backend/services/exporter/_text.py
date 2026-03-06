"""Text-cleaning and LaTeX-escaping helpers for the exporter."""

from __future__ import annotations

from datetime import date


def _format_date(d: date | str | None) -> str:
    if d is None:
        return ""
    if isinstance(d, date):
        return d.strftime("%b %Y")
    return str(d)


def _clean_location(location: str | None) -> str:
    """Strip anything after the first pipe.

    The CV parser sometimes puts domain tags or skill lists in the location
    field (e.g. 'London, UK | Investment Banking | Python'). Only the city/
    country portion belongs in the LaTeX heading.
    """
    if not location:
        return ""
    location = location.split("|")[0].strip()
    return location.rstrip(" ,;")


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
    text = "".join(ch for ch in text if ch >= " " or ch == "\t")
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
    """Remove newlines and collapse multiple spaces from bullet text."""
    if not text:
        return ""
    text = str(text)
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
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
