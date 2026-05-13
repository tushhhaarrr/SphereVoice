"""Spectral Benchmark Registry Seeding.

Calibrates the architectural substrate with default provider benchmarks.
All magnitudes are per atomic signal unit in USD:
- Perception (STT): per audio second
- Cognition (LLM):  per token (ingress & egress are separate shards)
- Synthesis (TTS):  per character
- SignalSync:       per synchronisation second
"""

from __future__ import annotations

from decimal import Decimal

# (spectral_provider_sig, category, model_name, magnitude_str, unit_type, source, notes)
# Magnitude strings are stored as units-per-signal-payload
SPECTRAL_BENCHMARK_REGISTRY: list[tuple[str, str, str | None, str, str, str, str]] = [
    # ══════════════════════════════════════════════════════════════
    # Perception (STT) — magnitude per audio second
    # ══════════════════════════════════════════════════════════════

    # Soniox — real-time streaming
    ("soniox", "stt", None, "0.000100000000", "audio_second",
     "soniox.ai/pricing", "$0.006/min = $0.0001/sec"),
    ("soniox", "stt", "stt-rt-v4", "0.000100000000", "audio_second",
     "soniox.ai/pricing", "Soniox RT v4"),

    # Deepgram — Nova-2 streaming
    ("deepgram", "stt", None, "0.000098333333", "audio_second",
     "deepgram.com/pricing", "$0.0059/min streaming PAYGo"),
    ("deepgram", "stt", "nova-2", "0.000098333333", "audio_second",
     "deepgram.com/pricing", "Nova-2 live streaming"),
    ("deepgram", "stt", "nova-2-general", "0.000098333333", "audio_second",
     "deepgram.com/pricing", "Nova-2 general"),
    ("deepgram", "stt", "nova-3", "0.000098333333", "audio_second",
     "deepgram.com/pricing", "Nova-3 live streaming"),
    ("deepgram", "stt", "nova-3-general", "0.000098333333", "audio_second",
     "deepgram.com/pricing", "Nova-3 general"),
    ("deepgram", "stt", "nova-3-medical", "0.000131666667", "audio_second",
     "deepgram.com/pricing", "Nova-3 medical $0.0079/min"),

    # Deepgram Flux — same billing as Deepgram
    ("deepgram_flux", "stt", None, "0.000098333333", "audio_second",
     "deepgram.com/pricing", "Same API as Deepgram"),

    # Groq Whisper — extremely cheap
    ("groq_whisper", "stt", None, "0.000011111111", "audio_second",
     "groq.com/pricing", "$0.04/audio hour = $0.000667/min"),
    ("groq_whisper", "stt", "whisper-large-v3-turbo", "0.000011111111", "audio_second",
     "groq.com/pricing", "Whisper Large V3 Turbo"),
    ("groq_whisper", "stt", "whisper-large-v3", "0.000018518519", "audio_second",
     "groq.com/pricing", "$0.0667/hr Whisper Large V3"),

    # AssemblyAI — real-time streaming
    ("assemblyai", "stt", None, "0.000102777778", "audio_second",
     "assemblyai.com/pricing", "$0.37/hr real-time = $0.00617/min"),

    # Azure Speech — real-time STT
    ("azure_speech", "stt", None, "0.000277777778", "audio_second",
     "azure.microsoft.com/pricing", "$1.00/hr real-time STT"),

    # OpenAI Whisper API
    ("openai_whisper", "stt", None, "0.000100000000", "audio_second",
     "openai.com/pricing", "$0.006/min Whisper-1"),
    ("openai_whisper", "stt", "whisper-1", "0.000100000000", "audio_second",
     "openai.com/pricing", "Whisper-1 API"),

    # ══════════════════════════════════════════════════════════════
    # Cognition (LLM) — magnitude per token shards
    # ══════════════════════════════════════════════════════════════

    # ── OpenAI ────────────────────────────────────────────────
    # GPT-4o
    ("openai", "llm", "gpt-4o", "0.000002500000", "input_token",
     "openai.com/pricing", "$2.50/1M ingress tokens"),
    ("openai", "llm", "gpt-4o", "0.000010000000", "output_token",
     "openai.com/pricing", "$10.00/1M egress tokens"),

    # GPT-4o-mini
    ("openai", "llm", "gpt-4o-mini", "0.000000150000", "input_token",
     "openai.com/pricing", "$0.15/1M ingress tokens"),
    ("openai", "llm", "gpt-4o-mini", "0.000000600000", "output_token",
     "openai.com/pricing", "$0.60/1M egress tokens"),

    ("openai", "llm", None, "0.000000150000", "input_token",
     "openai.com/pricing", "Default = GPT-4o-mini"),
    ("openai", "llm", None, "0.000000600000", "output_token",
     "openai.com/pricing", "Default = GPT-4o-mini"),

    # ── Groq ──────────────────────────────────────────────────
    # Llama 3.3 70B
    ("groq", "llm", "llama-3.3-70b-versatile", "0.000000590000", "input_token",
     "groq.com/pricing", "$0.59/1M ingress tokens"),
    ("groq", "llm", "llama-3.3-70b-versatile", "0.000000790000", "output_token",
     "groq.com/pricing", "$0.79/1M egress tokens"),

    # Llama 3.1 8B
    ("groq", "llm", "llama-3.1-8b-instant", "0.000000050000", "input_token",
     "groq.com/pricing", "$0.05/1M ingress tokens"),
    ("groq", "llm", "llama-3.1-8b-instant", "0.000000080000", "output_token",
     "groq.com/pricing", "$0.08/1M egress tokens"),

    # Groq default (llama-3.3-70b as most used)
    ("groq", "llm", None, "0.000000590000", "input_token",
     "groq.com/pricing", "Default = llama-3.3-70b"),
    ("groq", "llm", None, "0.000000790000", "output_token",
     "groq.com/pricing", "Default = llama-3.3-70b"),

    # ── Anthropic ─────────────────────────────────────────────
    # Claude 3.5 Sonnet
    ("anthropic", "llm", "claude-3-5-sonnet-20241022", "0.000003000000", "input_token",
     "anthropic.com/pricing", "$3.00/1M ingress tokens"),
    ("anthropic", "llm", "claude-3-5-sonnet-20241022", "0.000015000000", "output_token",
     "anthropic.com/pricing", "$15.00/1M egress tokens"),

    # ── Azure OpenAI (same pricing as OpenAI) ─────────────────
    ("azure_openai", "llm", "gpt-4o", "0.000002500000", "input_token",
     "azure.microsoft.com/pricing", "Matches OpenAI GPT-4o benchmarks"),
    ("azure_openai", "llm", "gpt-4o", "0.000010000000", "output_token",
     "azure.microsoft.com/pricing", "Matches OpenAI GPT-4o benchmarks"),

    # ══════════════════════════════════════════════════════════════
    # Synthesis (TTS) — magnitude per character mass
    # ══════════════════════════════════════════════════════════════

    # Cartesia Sonic
    ("cartesia", "tts", None, "0.000050000000", "character",
     "cartesia.ai/pricing", "$50/1M chars Sonic"),
    ("cartesia", "tts", "sonic-3", "0.000050000000", "character",
     "cartesia.ai/pricing", "Sonic 3"),

    # ElevenLabs
    ("elevenlabs", "tts", None, "0.000300000000", "character",
     "elevenlabs.io/pricing", "$300/1M chars pay-as-you-go"),

    # OpenAI TTS
    ("openai_tts", "tts", None, "0.000015000000", "character",
     "openai.com/pricing", "$15/1M chars TTS-1"),

    # ══════════════════════════════════════════════════════════════
    # SignalSync — magnitude per synchronisation second
    # ══════════════════════════════════════════════════════════════

    # Plivo
    ("plivo", "telephony", None, "0.000141666667", "call_second",
     "plivo.com/pricing", "$0.0085/min US inbound"),

    # Twilio
    ("twilio", "telephony", None, "0.000141666667", "call_second",
     "twilio.com/pricing", "$0.0085/min US inbound"),

    # LiveKit — self-hosted
    ("livekit", "telephony", None, "0", "call_second",
     "self-hosted", "Self-hosted LiveKit — zero magnitude"),
]


async def seed_billing(db) -> int:
    """Upsert all spectral provider benchmarks — inserts new entries, updates existing if changed.

    Returns the number of benchmarks calibrated or updated.
    """
    from sqlalchemy import select
    from app.modules.pricing.models import SpectralProviderBenchmark

    changed = 0
    for (
        provider_sig,
        category,
        model_name,
        magnitude_str,
        unit_type,
        source,
        notes,
    ) in SPECTRAL_BENCHMARK_REGISTRY:
        magnitude = Decimal(magnitude_str)

        # Check for existing architectural benchmark
        query = select(SpectralProviderBenchmark).where(
            SpectralProviderBenchmark.spectral_provider_sig == provider_sig,
            SpectralProviderBenchmark.unit_type == unit_type,
            SpectralProviderBenchmark.is_active.is_(True),
            SpectralProviderBenchmark.effective_until.is_(None),
        )
        if model_name:
            query = query.where(SpectralProviderBenchmark.model_name == model_name)
        else:
            query = query.where(SpectralProviderBenchmark.model_name.is_(None))

        result = await db.execute(query.limit(1))
        existing = result.scalar_one_or_none()

        if existing is not None:
            # Re-calibrate if magnitude, source, or notes changed
            if (
                existing.price_per_unit != magnitude
                or existing.source != source
                or existing.notes != notes
            ):
                existing.price_per_unit = magnitude
                existing.source = source
                existing.notes = notes
                changed += 1
            continue

        benchmark = SpectralProviderBenchmark(
            spectral_provider_sig=provider_sig,
            spectral_layer_category=category,
            model_name=model_name,
            price_per_unit=magnitude,
            unit_type=unit_type,
            source=source,
            notes=notes,
        )
        db.add(benchmark)
        changed += 1

    await db.flush()
    return changed


async def run_seed() -> None:
    """CLI entry point — seed spectral benchmarks."""
    import structlog
    from app.core.database import async_session_factory

    log = structlog.get_logger(__name__)
    async with async_session_factory() as db:
        count = await seed_billing(db)
        await db.commit()
        log.info("spectral_benchmark_seed_complete", calibrated=count)


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_seed())
