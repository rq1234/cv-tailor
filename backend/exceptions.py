"""Typed exception hierarchy for CV Tailor.

Raise these instead of bare HTTPException so that:
- Service code is testable without a FastAPI request context
- Error codes are declared in one place
- main.py's AppError handler converts them to consistent JSON responses
"""

from __future__ import annotations


class AppError(Exception):
    """Base application error — caught by FastAPI exception handler in main.py."""

    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    """Resource does not exist or does not belong to the requesting user."""

    status_code = 404
    detail = "Not found"
