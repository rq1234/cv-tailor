"""Shared string enums for the CV Tailor backend.

All values are stored as plain strings in the database — no migrations needed.
StrEnum values compare equal to their string equivalent, so existing string
comparisons continue to work unchanged.
"""

from __future__ import annotations

from enum import StrEnum


class ApplicationStatus(StrEnum):
    DRAFT = "draft"
    TAILORING = "tailoring"
    REVIEW = "review"
    COMPLETE = "complete"


class SelectionMode(StrEnum):
    LIBRARY = "library"
    LATEST_CV = "latest_cv"


class GapStatus(StrEnum):
    STRONG_MATCH = "strong_match"
    PARTIAL_MATCH = "partial_match"
    GAP = "gap"
