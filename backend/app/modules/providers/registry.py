"""Enterprise Provider Architecture — Capability Mapping & Registry."""

from __future__ import annotations

import os
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel
from app.core.config import get_settings


class ProviderType(str, Enum):
    LLM = "llm"
    VOICE = "voice"
    STT = "stt"
    TELEPHONY = "telephony"


class ProviderCapability(BaseModel):
    id: str
    name: str
    type: ProviderType
    models: list[str] = []
    voices: list[str] = []
    supported_languages: list[str] = []
    is_active: bool = False
    env_var_key: str | None = None
    validation_endpoint: str | None = None


class ProviderRegistry:
    """Centralized Enterprise Provider Registry."""
    
    _providers: dict[str, ProviderCapability] = {}

    @classmethod
    def register(cls, capability: ProviderCapability):
        cls._providers[capability.id] = capability

    @classmethod
    def get_provider(cls, provider_id: str) -> ProviderCapability | None:
        return cls._providers.get(provider_id)

    @classmethod
    def list_providers(cls, provider_type: ProviderType | None = None) -> list[ProviderCapability]:
        providers = list(cls._providers.values())
        if provider_type:
            return [p for p in providers if p.type == provider_type]
        return providers

    @classmethod
    def auto_discover(cls):
        """Auto-discovers and registers providers based on environment variables."""
        settings = get_settings()
        
        # LLMs
        cls._register_if_env("openai", "OpenAI", ProviderType.LLM, ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"], "OPENAI_API_KEY", settings.OPENAI_API_KEY)
        cls._register_if_env("anthropic", "Claude", ProviderType.LLM, ["claude-3-5-sonnet", "claude-3-opus"], "ANTHROPIC_API_KEY", settings.ANTHROPIC_API_KEY)
        cls._register_if_env("groq", "Groq", ProviderType.LLM, ["llama3-70b-8192", "mixtral-8x7b-32768"], "GROQ_API_KEY", settings.GROQ_API_KEY)
        cls._register_if_env("gemini", "Gemini", ProviderType.LLM, ["gemini-1.5-pro", "gemini-1.5-flash"], "GEMINI_API_KEY", getattr(settings, "GEMINI_API_KEY", None))
        cls._register_if_env("deepseek", "DeepSeek", ProviderType.LLM, ["deepseek-coder", "deepseek-chat"], "DEEPSEEK_API_KEY", getattr(settings, "DEEPSEEK_API_KEY", None))
        cls._register_if_env("cohere", "Cohere", ProviderType.LLM, ["command-r", "command-r-plus"], "COHERE_API_KEY", getattr(settings, "COHERE_API_KEY", None))
        cls._register_if_env("mistral", "Mistral", ProviderType.LLM, ["mistral-large-latest", "mistral-small-latest"], "MISTRAL_API_KEY", getattr(settings, "MISTRAL_API_KEY", None))

        # Voices
        cls._register_if_env("elevenlabs", "ElevenLabs", ProviderType.VOICE, [], "ELEVENLABS_API_KEY", settings.ELEVENLABS_API_KEY)
        cls._register_if_env("cartesia", "Cartesia", ProviderType.VOICE, [], "CARTESIA_API_KEY", settings.CARTESIA_API_KEY)
        cls._register_if_env("playht", "PlayHT", ProviderType.VOICE, [], "PLAYHT_API_KEY", getattr(settings, "PLAYHT_API_KEY", None))
        cls._register_if_env("azure-speech", "Azure Speech", ProviderType.VOICE, [], "AZURE_SPEECH_API_KEY", settings.AZURE_SPEECH_API_KEY)

        # STT
        cls._register_if_env("deepgram", "Deepgram", ProviderType.STT, ["nova-2"], "DEEPGRAM_API_KEY", settings.DEEPGRAM_API_KEY)
        cls._register_if_env("assemblyai", "AssemblyAI", ProviderType.STT, ["assemblyai-default"], "ASSEMBLYAI_API_KEY", getattr(settings, "ASSEMBLYAI_API_KEY", None))

        # Telephony
        cls._register_if_env("twilio", "Twilio", ProviderType.TELEPHONY, [], "TWILIO_ACCOUNT_SID", settings.TWILIO_ACCOUNT_SID)

        # Demo / Fallback Mode Models
        cls._register_demo_fallbacks()

    @classmethod
    def _register_if_env(cls, p_id: str, name: str, p_type: ProviderType, models: list[str], env_key: str, env_val: str | None):
        is_active = bool(env_val and len(env_val) > 0)
        cls.register(ProviderCapability(
            id=p_id,
            name=name,
            type=p_type,
            models=models,
            is_active=is_active,
            env_var_key=env_key
        ))

    @classmethod
    def _register_demo_fallbacks(cls):
        """Phase 4: Ensure the app works even without keys. Add demo providers."""
        if not cls.get_provider("demo-llm"):
            cls.register(ProviderCapability(
                id="demo-llm",
                name="Demo AI (Local Fallback)",
                type=ProviderType.LLM,
                models=["demo-model-v1"],
                is_active=True,
                env_var_key="NONE"
            ))
        if not cls.get_provider("demo-voice"):
            cls.register(ProviderCapability(
                id="demo-voice",
                name="Demo Voice (Local Fallback)",
                type=ProviderType.VOICE,
                models=[],
                voices=["demo-voice-mark", "demo-voice-sarah"],
                is_active=True,
                env_var_key="NONE"
            ))

# Auto-discover on module load
ProviderRegistry.auto_discover()
