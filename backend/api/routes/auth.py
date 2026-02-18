"""Authentication routes — password reset."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from supabase import create_client
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

settings = get_settings()


class PasswordResetRequest(BaseModel):
    """Request password reset email."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Confirm password reset with new password."""

    password: str = Field(min_length=8, max_length=128)


@router.post("/password-reset")
@limiter.limit("5/hour")
async def request_password_reset(req: PasswordResetRequest) -> dict:
    """Send password reset email to user.

    Rate limited to 5 requests per hour to prevent abuse.
    Supabase will send a link to the user's email.
    The reset link redirects to your frontend with a token in the URL.
    """
    try:
        supabase = create_client(settings.supabase_url, settings.supabase_service_key)

        # Use service key to reset password (works even for unverified emails)
        await supabase.auth.admin.reset_password_for_email(req.email)

        # Return generic response (don't leak whether email exists)
        return {"message": "If an account exists, you'll receive a password reset link."}
    except Exception as e:
        # Log the error but return generic message
        print(f"Password reset error: {e}")
        return {"message": "If an account exists, you'll receive a password reset link."}


@router.post("/password-reset/confirm")
@limiter.limit("10/hour")
async def confirm_password_reset(
    token: str,
    new_password: str = Field(min_length=8, max_length=128),
) -> dict:
    """Confirm password reset with token and new password.

    Rate limited to 10 requests per hour.
    The token comes from the reset email link.
    Frontend should extract it from URL params and pass here.
    """
    try:
        supabase = create_client(settings.supabase_url, settings.supabase_service_key)

        # Update user password using the reset token
        result = await supabase.auth.update_user(
            {"password": new_password},
            jwt=token,
        )

        return {"message": "Password updated successfully."}
    except Exception as e:
        print(f"Password reset confirm error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )
