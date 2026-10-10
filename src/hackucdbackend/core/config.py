import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "FamilyCareEats Backend"
    APP_VERSION: str = "1.0.0"
    APP_URL: str = "http://localhost:8000"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database Settings
    DATABASE_URL: str = "sqlite+aiosqlite:///./hackucd.db"
    SUPABASE_DIRECT_CONNECTION: str = ""
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Supabase Settings
    SUPABASE_PROJECT_URL: str = ""
    SUPABASE_PUBLISHABLE_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_PASSWORD: str = ""
    SUPABASE_STORAGE_BUCKET: str = "meals"

    # OpenRouter Settings
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_PRIMARY_MODEL: str = "google/gemini-3.8-flash"
    OPENROUTER_FALLBACK_MODEL: str = "google/gemini-3.8-flash"
    OPENROUTER_REASONING_MODEL: str = "openai/gpt-6-luna"

    # Auth & Security
    JWT_SECRET: str = "hackucd-secret-key-2026-supersecure"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Stripe Billing Settings
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = "pk_test_sample_nurtrition_2026"
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_SUCCESS_URL: str = "https://wheatless-jermaine-aftmost.ngrok-free.dev/billing/success"
    STRIPE_CANCEL_URL: str = "https://wheatless-jermaine-aftmost.ngrok-free.dev/billing/cancel"

    # CORS Settings
    CORS_ORIGINS: List[str] = [
        "http://localhost:8081",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:19000",
        "http://localhost:19006",
        "exp://localhost:8081",
        "*",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def async_database_url(self) -> str:
        """Resolve async database url with asyncpg or aiosqlite prefix."""
        url = self.DATABASE_URL
        if not url and self.SUPABASE_DIRECT_CONNECTION:
            url = self.SUPABASE_DIRECT_CONNECTION

        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url


settings = Settings()
