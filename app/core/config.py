"""
Configuration management for the SaaS AI Agents platform.
Uses environment variables for different deployment stages.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_environment_files() -> None:
    """
    Load environment files with safe precedence.

    Precedence:
    1) Real environment variables from cloud runtime (highest)
    2) `.env.<APP_ENV>` if exists
    3) `.env`
    """
    app_env = (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "development").strip().lower()
    root = Path(__file__).resolve().parents[2]

    candidate_files = [
        root / f".env.{app_env}",
        root / ".env",
    ]

    for env_file in candidate_files:
        if env_file.exists():
            load_dotenv(env_file, override=False)


_load_environment_files()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ---------------------------------------------------
    # Environment
    # ---------------------------------------------------

    APP_ENV: str = os.getenv("APP_ENV", "development")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    DEBUG: bool = False

    # ---------------------------------------------------
    # API
    # ---------------------------------------------------

    API_TITLE: str = "AI Agents SaaS Platform"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "Scalable SaaS platform for creating and managing AI agents"

    # ---------------------------------------------------
    # Database
    # ---------------------------------------------------

    DATABASE_URL: str = "postgresql://user:password@localhost:5432/ai_agents"
    DATABASE_ECHO: bool = False

    # ---------------------------------------------------
    # Redis
    # ---------------------------------------------------

    REDIS_URL: str = "redis://localhost:6379/0"

    # ---------------------------------------------------
    # JWT
    # ---------------------------------------------------

    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---------------------------------------------------
    # CORS
    # ---------------------------------------------------

    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # ---------------------------------------------------
    # Multi Tenant
    # ---------------------------------------------------

    ENABLE_MULTI_TENANCY: bool = True

    # ---------------------------------------------------
    # Logging
    # ---------------------------------------------------

    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True

    # ---------------------------------------------------
    # Security limits
    # ---------------------------------------------------

    MAX_REQUEST_BODY_BYTES: int = 1_048_576
    DEFAULT_TOOL_TIMEOUT_SECONDS: int = 20
    MAX_TOOL_CALLS_PER_EXECUTION: int = 20
    MAX_TOOL_RETRIES: int = 2

    # ---------------------------------------------------
    # Rate limiting
    # ---------------------------------------------------

    RATE_LIMIT_AUTH_PER_MINUTE: int = 20
    RATE_LIMIT_AGENTS_PER_MINUTE: int = 120
    RATE_LIMIT_EXECUTE_PER_MINUTE: int = 30
    RATE_LIMIT_EXECUTE_BURST: int = 10

    # ---------------------------------------------------
    # OpenAI
    # ---------------------------------------------------

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # ---------------------------------------------------
    # Stripe
    # ---------------------------------------------------

    STRIPE_API_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    STRIPE_SUCCESS_URL: str = "http://localhost:5173/billing?checkout=success"
    STRIPE_CANCEL_URL: str = "http://localhost:5173/billing?checkout=cancel"

    # ---------------------------------------------------
    # Validators
    # ---------------------------------------------------

    @field_validator("DEBUG", mode="before")
    @classmethod
    def _coerce_debug(cls, value):

        if isinstance(value, bool):
            return value

        if isinstance(value, str):

            lowered = value.strip().lower()

            if lowered in {"1", "true", "yes", "on", "debug", "development", "dev"}:
                return True

            if lowered in {"0", "false", "no", "off", "release", "production", "prod"}:
                return False

        return value

    # ---------------------------------------------------
    # Pydantic config
    # ---------------------------------------------------

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()