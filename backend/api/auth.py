"""Supabase JWT authentication dependency."""

from __future__ import annotations

import json
import uuid
from functools import lru_cache

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import get_settings

security = HTTPBearer()


@lru_cache(maxsize=1)
def _get_jwks_keys() -> list[dict]:
    """Fetch and cache Supabase JWKS public keys (used for RS256 tokens)."""
    settings = get_settings()
    url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    with httpx.Client(timeout=10) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json().get("keys", [])


def _verify_rs256(token: str) -> dict:
    """Verify an RS256-signed token using Supabase's JWKS endpoint."""
    keys = _get_jwks_keys()
    kid = jwt.get_unverified_header(token).get("kid")
    for key_data in keys:
        if kid and key_data.get("kid") != kid:
            continue
        public_key = RSAAlgorithm.from_jwk(json.dumps(key_data))
        return jwt.decode(token, public_key, algorithms=["RS256"], audience="authenticated")
    raise jwt.InvalidTokenError("No matching RS256 key found in JWKS")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> uuid.UUID:
    """Verify Supabase JWT and return the user_id (UUID).

    Supports both legacy HS256 tokens and new RS256 tokens (JWT Signing Keys).
    """
    settings = get_settings()
    token = credentials.credentials

    try:
        alg = jwt.get_unverified_header(token).get("alg", "HS256")
        if alg == "RS256":
            payload = _verify_rs256(token)
        else:
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unauthorized: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    try:
        return uuid.UUID(sub)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
