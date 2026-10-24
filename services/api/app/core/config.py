"""Application settings, read from environment variables (and an optional local .env file)."""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_SECRETS = {"", "change-me", "changeme", "replace-me", "secret"}
MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    environment: Literal["development", "test", "production"] = "development"
    app_name: str = "CoreSync AI API"

    # Persistence
    database_url: str = "sqlite:///./.data/coresync.db"
    redis_url: str | None = None
    storage_dir: str = "./.data/storage"

    # Auth
    jwt_secret: str | None = None
    jwt_issuer: str = "coresync-ai"
    jwt_ttl_minutes: int = 60
    min_password_length: int = 10

    # HTTP
    cors_origins: str = "http://localhost:3000"

    # Uploads / ingestion
    max_upload_bytes: int = 2 * 1024 * 1024
    max_endpoints_per_document: int = 2000

    # Rate limits (requests per window, window in seconds)
    rate_limit_window_seconds: int = 60
    rate_limit_auth_per_window: int = 10
    rate_limit_ai_per_window: int = 20
    rate_limit_credential_issue_per_window: int = 10
    rate_limit_run_per_window: int = 20
    sandbox_rate_limit_per_window: int = 30

    # Sandbox
    sandbox_default_ttl_minutes: int = 30
    sandbox_max_ttl_minutes: int = 24 * 60
    sandbox_default_max_requests: int = 100
    sandbox_max_requests_cap: int = 1000
    sandbox_timeout_seconds: float = 5.0
    sandbox_max_output_bytes: int = 16 * 1024

    # LLM (server-side only; never sent to the browser)
    llm_provider: Literal["offline", "openai_compatible"] = "offline"
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_timeout_seconds: float = 30.0

    @model_validator(mode="after")
    def _validate_security_settings(self) -> Settings:
        secret = (self.jwt_secret or "").strip()
        if self.environment == "production":
            if secret.lower() in PLACEHOLDER_SECRETS or len(secret) < MIN_SECRET_LENGTH:
                raise ValueError(
                    "JWT_SECRET must be set to a random value of at least "
                    f"{MIN_SECRET_LENGTH} characters in production."
                )
            if self.database_url.startswith("sqlite"):
                raise ValueError("DATABASE_URL must point to PostgreSQL in production.")
        elif secret.lower() in PLACEHOLDER_SECRETS or len(secret) < MIN_SECRET_LENGTH:
            # Development/test: use an ephemeral per-process secret rather than a hardcoded one.
            # Tokens become invalid when the process restarts.
            self.jwt_secret = secrets.token_urlsafe(48)
        if self.llm_provider == "openai_compatible" and not (
            self.llm_base_url and self.llm_model and self.llm_api_key
        ):
            raise ValueError(
                "LLM_PROVIDER=openai_compatible requires LLM_BASE_URL, LLM_MODEL and LLM_API_KEY."
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
