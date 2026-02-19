"""Authentication routes — password reset."""

from __future__ import annotations

import logging

import jwt as pyjwt
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from supabase import create_client
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

settings = get_settings()


class PasswordResetRequest(BaseModel):
    """Request password reset email."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Confirm password reset with new password."""

    token: str
    password: str = Field(min_length=8, max_length=128)


@router.post("/password-reset")
@limiter.limit("5/hour")
async def request_password_reset(request: Request, req: PasswordResetRequest) -> dict:
    """Send password reset email to user.

    Rate limited to 5 requests per hour to prevent abuse.
    Supabase will send a link to the user's email.
    The reset link redirects to the frontend with a token in the URL.
    """
    try:
        supabase = create_client(settings.supabase_url, settings.supabase_service_key)
        supabase.auth.reset_password_for_email(req.email)
    except Exception as e:
        logger.error("Password reset error: %s", e)
    # Always return generic response — don't leak whether the email exists
    return {"message": "If an account exists, you'll receive a password reset link."}


@router.post("/password-reset/confirm")
@limiter.limit("10/hour")
async def confirm_password_reset(
    request: Request,
    req: PasswordResetConfirm,
) -> dict:
    """Confirm password reset with token and new password.

    Rate limited to 10 requests per hour.
    The frontend extracts the access_token from the Supabase recovery URL and
    passes it here along with the new password.
    """
    try:
        # Decode the recovery access token to get the user's ID
        payload = pyjwt.decode(
            req.token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token.",
            )

        supabase = create_client(settings.supabase_url, settings.supabase_service_key)
        supabase.auth.admin.update_user_by_id(user_id, {"password": req.password})

        return {"message": "Password updated successfully."}
    except HTTPException:
        raise
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )
    except pyjwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )
    except Exception as e:
        logger.error("Password reset confirm error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )
