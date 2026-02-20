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


class ForbiddenError(AppError):
    """Authenticated user is not allowed to perform this action."""

    status_code = 403
    detail = "Forbidden"


class UnprocessableError(AppError):
    """Request body is structurally valid but semantically incorrect."""

    status_code = 422
    detail = "Unprocessable request"


class PipelineError(AppError):
    """Tailoring pipeline failed at a specific step."""

    status_code = 500
    detail = "Pipeline error"


class AuthError(AppError):
    """Token missing, expired, or invalid."""

    status_code = 401
    detail = "Authentication failed"
