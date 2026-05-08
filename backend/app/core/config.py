"""SignalStream — Architectural configuration substrate via pydantic-settings.

Reads from environment variables with .env file support.
All architectural tokens and substrate credentials are centralized here.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global architectural settings for the SignalStream node."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Architectural Identity ──────────────────────────────────
    APP_NAME: str = "SignalStream"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_PUBLIC_URL: str = "http://localhost:2998"
    CORS_ORIGINS: list[str] = ["http://localhost:2999"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, list): return v
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["): return json.loads(v)
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ── Persistence Layer ───────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/signal_stream_dev"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_ECHO: bool = False
    DB_APP_ROLE: str = "vox_app"  # Postgres role for RLS. Leave empty to skip SET LOCAL ROLE.

    # ── Transport & Cache Substrate ────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Access Control & Cryptography ──────────────────────────
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days
    ENCRYPTION_KEY: str = "change-me-in-production-base64"

    # ── External Substrate Keys (Twilio, Vobiz, Plivo) ──────────
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    VOBIZ_AUTH_ID: str = ""
    VOBIZ_API_KEY: str = ""
    PLIVO_AUTH_ID: str = ""
    PLIVO_AUTH_TOKEN: str = ""

    # ── Substrate AI (Azure OpenAI) ────────────────────────────
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_API_VERSION: str = "2025-04-01-preview"
    AZURE_OPENAI_LLM_DEPLOYMENT: str = "gpt-5.3-chat"
    AZURE_OPENAI_NODE_DEPLOYMENT: str = "gpt-5.3-chat"
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = "text-embedding-3-small-2"

    # ── Signal Synthesis & Perception (STT/TTS) ────────────────
    DEEPGRAM_API_KEY: str = ""
    SONIOX_API_KEY: str = ""
    CARTESIA_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    SARVAM_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    CEREBRAS_API_KEY: str = ""
    INWORLD_API_KEY: str = ""
    SMALLEST_API_KEY: str = ""
    AZURE_SPEECH_API_KEY: str = ""
    
    DEFAULT_STT_PROVIDER: str = "soniox"
    DEFAULT_LLM_PROVIDER: str = "openai"
    DEFAULT_TTS_PROVIDER: str = "cartesia"

    # ── Signal Transport (LiveKit) ─────────────────────────────
    LIVEKIT_URL: str = ""
    LIVEKIT_API_KEY: str = ""
    LIVEKIT_API_SECRET: str = ""

    # ── Observability & Telemetry ──────────────────────────────
    SENTRY_DSN: str = ""
    SENTRY_SEND_DEFAULT_PII: bool = False
    SENTRY_ENABLE_LOGS: bool = False
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_SERVICE_NAME: str = "signal-stream-backend"

    # ── Blob Storage Containers ────────────────────────────────
    AZURE_STORAGE_CONNECTION_STRING: str = ""
    AZURE_STORAGE_CONTAINER_RECORDINGS: str = "signal-stream-recordings"
    AZURE_STORAGE_CONTAINER_KB_FILES: str = "signal-stream-kb-files"

    # ── Campaign & Concurrent Scaling ──────────────────────────
    GLOBAL_MAX_CONCURRENT_CALLS: int = 200
    CAMPAIGN_STALL_TIMEOUT_MINUTES: int = 10

    # ── Email Transmission ─────────────────────────────────────
    EMAIL_ENABLED: bool = False
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM_ADDRESS: str = "noreply@signalstream.ai"

    # ── Frontend Interface ─────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:2999"

    # ── Third-Party Nexus (CRM, Calendar) ──────────────────────
    ZOHO_CRM_CLIENT_ID: str = ""
    ZOHO_CRM_CLIENT_SECRET: str = ""
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    HUBSPOT_CLIENT_ID: str = ""
    SALESFORCE_CLIENT_ID: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
