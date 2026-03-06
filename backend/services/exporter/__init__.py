"""Export service — generates LaTeX and DOCX from final CV data."""

from ._docx import generate_docx
from ._fitting import _compute_page_limits, _soft_trim_bullet
from ._latex import generate_latex
from ._text import (
    _clean_bullet_text,
    _clean_location,
    _dedupe_preserve_order,
    _escape_latex,
    _escape_latex_url,
    _format_date,
    _is_meaningful_bullet,
    _normalize_bullets,
)

__all__ = [
    "generate_latex",
    "generate_docx",
    # helpers re-exported for tests
    "_clean_bullet_text",
    "_clean_location",
    "_compute_page_limits",
    "_dedupe_preserve_order",
    "_escape_latex",
    "_escape_latex_url",
    "_format_date",
    "_is_meaningful_bullet",
    "_normalize_bullets",
    "_soft_trim_bullet",
]
