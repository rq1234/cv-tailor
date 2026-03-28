"""Centralized settings — all env vars and magic numbers live here."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

# Load .env before anything reads os.getenv
load_dotenv(Path(__file__).resolve().parent / ".env")


class Settings(BaseSettings):
    """Application settings. Values come from environment variables, then defaults."""

    # ── API keys ──
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_service_key: str = Field(default="", alias="SUPABASE_SERVICE_KEY")
    supabase_jwt_secret: str = Field(default="", alias="SUPABASE_JWT_SECRET")

    # ── Database ──
    database_url: str = Field(default="", alias="DATABASE_URL")

    # ── Server ──
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        alias="CORS_ORIGINS",
    )

    # ── OpenAI models ──
    model_name: str = "gpt-4o"
    model_mini: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    # ── Temperature presets ──
    temp_parsing: float = 0.1
    temp_gap_analysis: float = 0.2
    temp_tailoring: float = 0.72

    # ── Deduplication thresholds ──
    near_duplicate_threshold: float = 0.92
    variant_threshold: float = 0.75

    # ── Confidence thresholds ──
    confidence_review_threshold: float = 0.75  # below this → flag for user review

    # ── Master account (exempt from all usage limits) ──
    master_account_email: str = Field(default="rongquan.yeo@gmail.com", alias="MASTER_ACCOUNT_EMAIL")

    # ── Usage limits ──
    max_applications_per_user: int = 10
    max_bullet_regens_per_user: int = 100

    # ── Pipeline timeouts (seconds) ──
    pipeline_timeout_s: int = 300
    pipeline_stale_lock_s: int = 180

    # ── Embedding cache ──
    embedding_cache_size: int = 2000

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _check_required_secrets(self) -> "Settings":
        """Fail fast at startup if critical secrets are missing."""
        missing = [
            name for name, value in [
                ("SUPABASE_JWT_SECRET", self.supabase_jwt_secret),
                ("SUPABASE_URL", self.supabase_url),
                ("SUPABASE_SERVICE_KEY", self.supabase_service_key),
                ("DATABASE_URL", self.database_url),
                ("OPENAI_API_KEY", self.openai_api_key),
            ]
            if not value
        ]
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached singleton settings instance."""
    return Settings()
