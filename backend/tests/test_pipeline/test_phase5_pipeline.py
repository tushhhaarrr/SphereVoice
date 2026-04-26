"""Tests for Phase 5 — Full Voice Pipeline.

Covers:
- LLM service helpers (llm.py)
- TTS service helpers (tts.py)
- PipecatProviderFactory (get_llm, get_tts)
- VoicePipeline function calling
- Circuit breaker
- Recording service
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# ── STT Service Tests ────────────────────────────────────────


class TestSTTServiceHelpers:
    """Tests for pipeline.services.stt module."""

    @pytest.mark.asyncio
    async def test_create_stt_with_fallback_wraps_groq_in_switcher(self) -> None:
        """Groq STT should be wrapped in ServiceSwitcher like any other STT."""
        from app.modules.pipeline.services.stt import create_stt_with_fallback

        groq_stt = type("GroqSTTService", (), {})()
        fallback_stt = object()

        with patch("pipecat.pipeline.service_switcher.ServiceSwitcher") as mock_switcher:
            mock_switcher.return_value = "switcher_instance"
            resolved = await create_stt_with_fallback(groq_stt, fallback_stt)

        assert resolved == "switcher_instance"
        mock_switcher.assert_called_once()


class TestLiveLatencyProcessors:
    """Tests for real-time pipeline telemetry."""

    @pytest.mark.asyncio
    async def test_live_processors_stream_transcripts_and_latency(self) -> None:
        """User and assistant processors should emit transcript and latency payloads."""
        from pipecat.frames.frames import (
            BotStoppedSpeakingFrame,
            InterimTranscriptionFrame,
            LLMFullResponseEndFrame,
            LLMFullResponseStartFrame,
            MetricsFrame,
            TextFrame,
            TTSTextFrame,
            TTSStartedFrame,
            TranscriptionFrame,
            VADUserStoppedSpeakingFrame,
        )
        from pipecat.metrics.metrics import ProcessingMetricsData, TTFBMetricsData
        from pipecat.processors.frame_processor import FrameDirection

        from app.modules.pipeline.services.latency import (
            LiveAssistantEventProcessor,
            LiveLLMTextBridge,
            LiveUserEventProcessor,
            create_live_session_state,
        )

        clock_values = iter([0.0, 0.12, 0.28, 0.41])
        state = create_live_session_state(
            call_id="call-123",
            clock=lambda: next(clock_values),
            timestamp_factory=lambda: "2026-03-08T00:00:00+00:00",
        )
        user_processor = LiveUserEventProcessor(state)
        llm_text_bridge = LiveLLMTextBridge(state)
        assistant_processor = LiveAssistantEventProcessor(state)
        user_processor.push_frame = AsyncMock()
        llm_text_bridge.push_frame = AsyncMock()
        assistant_processor.push_frame = AsyncMock()

        await user_processor.process_frame(
            VADUserStoppedSpeakingFrame(stop_secs=0.5),
            FrameDirection.DOWNSTREAM,
        )
        await user_processor.process_frame(
            MetricsFrame(data=[
                ProcessingMetricsData(
                    processor="AzureSTTService#1",
                    model="realtime",
                    value=0.095,
                )
            ]),
            FrameDirection.DOWNSTREAM,
        )
        await user_processor.process_frame(
            InterimTranscriptionFrame(text="hel", user_id="", timestamp="2026-03-08T00:00:00+00:00"),
            FrameDirection.DOWNSTREAM,
        )
        await user_processor.process_frame(
            TranscriptionFrame(text="hello", user_id="", timestamp="2026-03-08T00:00:00+00:00"),
            FrameDirection.DOWNSTREAM,
        )
        await assistant_processor.process_frame(
            MetricsFrame(data=[
                TTFBMetricsData(
                    processor="OpenAILLMService#2",
                    model="gpt-4o-mini",
                    value=0.082,
                )
            ]),
            FrameDirection.DOWNSTREAM,
        )
        # LLM text goes through the bridge first (pre-TTS)
        await llm_text_bridge.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        await llm_text_bridge.process_frame(TextFrame(text="Hi there"), FrameDirection.DOWNSTREAM)
        await llm_text_bridge.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)
        # Then latency frames go through assistant processor (post-TTS)
        await assistant_processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        await assistant_processor.process_frame(
            MetricsFrame(data=[
                TTFBMetricsData(
                    processor="AzureTTSService#3",
                    model="hi-IN-AnanyaNeural",
                    value=0.047,
                )
            ]),
            FrameDirection.DOWNSTREAM,
        )
        await assistant_processor.process_frame(TTSStartedFrame(), FrameDirection.DOWNSTREAM)

        user_messages = [
            call.args[0].message
            for call in user_processor.push_frame.await_args_list
            if hasattr(call.args[0], "message")
        ]
        assistant_messages = [
            call.args[0].message
            for call in assistant_processor.push_frame.await_args_list
            if hasattr(call.args[0], "message")
        ]
        bridge_messages = [
            call.args[0].message
            for call in llm_text_bridge.push_frame.await_args_list
            if hasattr(call.args[0], "message")
        ]
        latest_payload = next(
            message for message in reversed(assistant_messages)
            if message["type"] == "latency_update"
        )

        assert latest_payload["type"] == "latency_update"
        assert latest_payload["call_id"] == "call-123"
        assert latest_payload["turn_id"] == 1
        assert latest_payload["pipeline"]["e2e_latency_ms"] == 410.0
        assert latest_payload["services"]["stt"]["response_latency_ms"] == 120.0
        assert latest_payload["services"]["stt"]["processing_latency_ms"] == 95.0
        assert latest_payload["services"]["llm"]["response_latency_ms"] == 160.0
        assert latest_payload["services"]["llm"]["ttfb_latency_ms"] == 82.0
        assert latest_payload["services"]["tts"]["response_latency_ms"] == 130.0
        assert latest_payload["services"]["tts"]["ttfb_latency_ms"] == 47.0
        assert any(message["type"] == "transcript_update" and message["speaker"] == "user" for message in user_messages)
        # Transcript now comes from the LLM text bridge (pre-TTS)
        assert any(message["type"] == "transcript_update" and message["speaker"] == "ai" and message["is_final"] is True for message in bridge_messages)

    @pytest.mark.asyncio
    async def test_multi_chunk_transcript_has_spaces(self) -> None:
        """Multiple LLM TextFrame chunks should be joined with spaces, not concatenated."""
        from pipecat.frames.frames import (
            LLMFullResponseEndFrame,
            LLMFullResponseStartFrame,
            TextFrame,
            VADUserStoppedSpeakingFrame,
            TranscriptionFrame,
        )
        from pipecat.processors.frame_processor import FrameDirection

        from app.modules.pipeline.services.latency import (
            LiveLLMTextBridge,
            LiveUserEventProcessor,
            create_live_session_state,
        )

        state = create_live_session_state(
            call_id="call-space-test",
            clock=lambda: 0.0,
            timestamp_factory=lambda: "2026-03-08T00:00:00+00:00",
        )
        user_proc = LiveUserEventProcessor(state)
        bridge_proc = LiveLLMTextBridge(state)
        user_proc.push_frame = AsyncMock()
        bridge_proc.push_frame = AsyncMock()

        # Trigger a turn start
        await user_proc.process_frame(
            VADUserStoppedSpeakingFrame(stop_secs=0.1),
            FrameDirection.DOWNSTREAM,
        )
        await user_proc.process_frame(
            TranscriptionFrame(text="hi", user_id="", timestamp="2026-03-08T00:00:00+00:00"),
            FrameDirection.DOWNSTREAM,
        )

        # Two sentence-level LLM text frames WITHOUT trailing/leading spaces
        await bridge_proc.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        await bridge_proc.process_frame(
            TextFrame(text="Hello, this is your assistant."),
            FrameDirection.DOWNSTREAM,
        )
        await bridge_proc.process_frame(
            TextFrame(text="How can I help you today?"),
            FrameDirection.DOWNSTREAM,
        )
        await bridge_proc.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

        messages = [
            call.args[0].message
            for call in bridge_proc.push_frame.await_args_list
            if hasattr(call.args[0], "message")
        ]
        final = next(m for m in reversed(messages) if m.get("type") == "transcript_update" and m.get("is_final"))
        assert final["text"] == "Hello, this is your assistant. How can I help you today?"

# ── LLM Service Tests ─────────────────────────────────────────


class TestLLMServiceHelpers:
    """Tests for pipeline.services.llm module."""

    def test_llm_config_named_tuple(self) -> None:
        """LLMConfig NamedTuple has all required fields."""
        from app.modules.pipeline.services.llm import LLMConfig

        config = LLMConfig(
            provider="openai",
            model="gpt-4o-mini",
            max_tokens=1024,
            temperature=0.7,
            description="Test config",
        )
        assert config.provider == "openai"
        assert config.model == "gpt-4o-mini"
        assert config.max_tokens == 1024
        assert config.temperature == 0.7

    def test_default_presets_exist(self) -> None:
        """All expected provider presets are defined."""
        from app.modules.pipeline.services.llm import DEFAULT_CONFIGS

        assert "groq" in DEFAULT_CONFIGS
        assert "openai" in DEFAULT_CONFIGS
        assert "anthropic" in DEFAULT_CONFIGS

    def test_get_default_config_groq(self) -> None:
        """get_default_config returns correct Groq config."""
        from app.modules.pipeline.services.llm import get_default_config

        config = get_default_config("groq")
        assert config.provider == "groq"
        assert "llama" in config.model.lower() or "mixtral" in config.model.lower()

    def test_get_default_config_unknown_raises(self) -> None:
        """get_default_config raises for unknown provider."""
        from app.modules.pipeline.services.llm import get_default_config

        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_default_config("nonexistent_provider")

    def test_build_function_schemas_empty(self) -> None:
        """build_function_schemas returns builtins when no custom functions."""
        from app.modules.pipeline.services.llm import build_function_schemas

        schemas = build_function_schemas({})
        assert isinstance(schemas, list)
        # Should have at least end_call and transfer_call
        names = [s.get("function", {}).get("name") for s in schemas]
        assert "end_call" in names
        assert "transfer_call" in names

    def test_build_function_schemas_with_custom(self) -> None:
        """build_function_schemas includes custom agent functions."""
        from app.modules.pipeline.services.llm import build_function_schemas

        config = {
            "functions": [
                {
                    "name": "book_appointment",
                    "description": "Book an appointment",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Date"},
                        },
                    },
                }
            ]
        }
        schemas = build_function_schemas(config)
        names = [s.get("function", {}).get("name") for s in schemas]
        assert "book_appointment" in names
        assert "end_call" in names
        assert "transfer_call" in names

    def test_build_tools_schema_converts_openai_style_tools(self) -> None:
        """build_tools_schema converts OpenAI-style tool dicts into Pipecat ToolsSchema."""
        from app.modules.pipeline.services.llm import build_tools_schema, build_function_schemas

        tools_schema = build_tools_schema(build_function_schemas({}))

        names = [schema.name for schema in tools_schema.standard_tools]
        assert "end_call" in names
        assert "transfer_call" in names


# ── TTS Service Tests ─────────────────────────────────────────


class TestTTSServiceHelpers:
    """Tests for pipeline.services.tts module."""

    def test_tts_config_named_tuple(self) -> None:
        """TTSConfig NamedTuple has all required fields."""
        from app.modules.pipeline.services.tts import TTSConfig

        config = TTSConfig(
            provider="cartesia",
            model="sonic-3",
            default_voice_id="test-voice",
            sample_rate=16000,
            description="Test",
        )
        assert config.provider == "cartesia"
        assert config.model == "sonic-3"
        assert config.sample_rate == 16000

    def test_default_presets_exist(self) -> None:
        """All expected TTS provider presets are defined."""
        from app.modules.pipeline.services.tts import DEFAULT_CONFIGS

        assert "cartesia" in DEFAULT_CONFIGS
        assert "elevenlabs" in DEFAULT_CONFIGS
        assert "openai_tts" in DEFAULT_CONFIGS
        assert "lmnt" in DEFAULT_CONFIGS

    def test_get_default_config_cartesia(self) -> None:
        """get_default_config returns Cartesia Sonic-3 config."""
        from app.modules.pipeline.services.tts import get_default_config

        config = get_default_config("cartesia")
        assert config.provider == "cartesia"
        assert config.model == "sonic-3"

    def test_get_default_config_unknown_raises(self) -> None:
        """get_default_config raises for unknown provider."""
        from app.modules.pipeline.services.tts import get_default_config

        with pytest.raises(ValueError, match="Unknown TTS provider"):
            get_default_config("nonexistent")

    def test_resolve_voice_id_agent_override(self) -> None:
        """resolve_voice_id prefers agent-level voice_id."""
        from app.modules.pipeline.services.tts import resolve_voice_id

        result = resolve_voice_id("agent-voice-123", {}, "cartesia")
        assert result == "agent-voice-123"

    def test_resolve_voice_id_config_fallback(self) -> None:
        """resolve_voice_id uses provider config when agent voice is None."""
        from app.modules.pipeline.services.tts import resolve_voice_id

        result = resolve_voice_id(None, {"voice_id": "config-voice"}, "cartesia")
        assert result == "config-voice"

    def test_resolve_voice_id_default_fallback(self) -> None:
        """resolve_voice_id falls back to provider default."""
        from app.modules.pipeline.services.tts import resolve_voice_id

        result = resolve_voice_id(None, {}, "cartesia")
        # Should get the Cartesia default voice
        assert result != "default"
        assert isinstance(result, str)

    def test_resolve_voice_speed_default(self) -> None:
        """resolve_voice_speed returns 1.0 when not set."""
        from app.modules.pipeline.services.tts import resolve_voice_speed

        mock_agent = MagicMock(spec=[])
        result = resolve_voice_speed(mock_agent)
        assert result == 1.0

    def test_resolve_voice_speed_from_agent(self) -> None:
        """resolve_voice_speed reads from agent attribute."""
        from app.modules.pipeline.services.tts import resolve_voice_speed

        mock_agent = MagicMock()
        mock_agent.voice_speed = 1.25
        result = resolve_voice_speed(mock_agent)
        assert result == 1.25


# ── Circuit Breaker Tests ─────────────────────────────────────


class TestCircuitBreaker:
    """Tests for pipeline.services.circuit_breaker module."""

    @pytest.mark.asyncio
    async def test_initial_state_closed(self) -> None:
        """Circuit breaker starts in CLOSED state."""
        from app.modules.pipeline.services.circuit_breaker import (
            CircuitBreaker,
            CircuitState,
        )

        cb = CircuitBreaker("test_provider", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        assert not cb.is_open, "Should not be open initially"

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self) -> None:
        """Circuit opens after N consecutive failures."""
        from app.modules.pipeline.services.circuit_breaker import (
            CircuitBreaker,
            CircuitState,
        )

        cb = CircuitBreaker("test_provider", failure_threshold=3)

        await cb.record_failure()
        assert cb.state == CircuitState.CLOSED, "Should still be closed after 1 failure"

        await cb.record_failure()
        assert cb.state == CircuitState.CLOSED, "Should still be closed after 2 failures"

        await cb.record_failure()
        assert cb.state == CircuitState.OPEN, "Should be open after 3 failures"
        assert cb.is_open

    @pytest.mark.asyncio
    async def test_should_use_fallback_when_open(self) -> None:
        """should_use_fallback returns True when circuit is open."""
        from app.modules.pipeline.services.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test_provider", failure_threshold=2, recovery_timeout=60.0)

        await cb.record_failure()
        await cb.record_failure()

        assert await cb.should_use_fallback() is True

    @pytest.mark.asyncio
    async def test_half_open_after_recovery_timeout(self) -> None:
        """Circuit transitions to HALF_OPEN after recovery timeout."""
        from app.modules.pipeline.services.circuit_breaker import (
            CircuitBreaker,
            CircuitState,
        )

        cb = CircuitBreaker(
            "test_provider",
            failure_threshold=2,
            recovery_timeout=0.01,  # 10ms for testing
        )

        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

        await asyncio.sleep(0.02)

        # Checking should_use_fallback triggers the HALF_OPEN transition
        result = await cb.should_use_fallback()
        assert result is False, "Should allow probe request"
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_closes_on_success_in_half_open(self) -> None:
        """Circuit closes after success_threshold successes in HALF_OPEN."""
        from app.modules.pipeline.services.circuit_breaker import (
            CircuitBreaker,
            CircuitState,
        )

        cb = CircuitBreaker(
            "test_provider",
            failure_threshold=2,
            recovery_timeout=0.01,
            success_threshold=2,
        )

        # Open the circuit
        await cb.record_failure()
        await cb.record_failure()

        # Wait for recovery timeout
        await asyncio.sleep(0.02)
        await cb.should_use_fallback()  # Triggers HALF_OPEN

        await cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN, "Should still be half-open after 1 success"

        await cb.record_success()
        assert cb.state == CircuitState.CLOSED, "Should close after 2 successes"

    @pytest.mark.asyncio
    async def test_reopens_on_failure_in_half_open(self) -> None:
        """Circuit re-opens if failure occurs in HALF_OPEN."""
        from app.modules.pipeline.services.circuit_breaker import (
            CircuitBreaker,
            CircuitState,
        )

        cb = CircuitBreaker(
            "test_provider",
            failure_threshold=2,
            recovery_timeout=0.01,
        )

        await cb.record_failure()
        await cb.record_failure()
        await asyncio.sleep(0.02)
        await cb.should_use_fallback()  # HALF_OPEN

        await cb.record_failure()
        assert cb.state == CircuitState.OPEN, "Should re-open on failure in half-open"

    @pytest.mark.asyncio
    async def test_manual_reset(self) -> None:
        """Manual reset transitions circuit to CLOSED."""
        from app.modules.pipeline.services.circuit_breaker import (
            CircuitBreaker,
            CircuitState,
        )

        cb = CircuitBreaker("test_provider", failure_threshold=2)
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

        await cb.reset()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self) -> None:
        """Success in CLOSED state resets the failure count."""
        from app.modules.pipeline.services.circuit_breaker import (
            CircuitBreaker,
            CircuitState,
        )

        cb = CircuitBreaker("test_provider", failure_threshold=3)
        await cb.record_failure()
        await cb.record_failure()
        await cb.record_success()

        # After reset, one more failure should not open
        await cb.record_failure()
        assert cb.state == CircuitState.CLOSED


# ── Provider Circuit Breaker Registry Tests ───────────────────


class TestProviderCircuitBreakerRegistry:
    """Tests for the global registry of circuit breakers."""

    @pytest.mark.asyncio
    async def test_get_or_create(self) -> None:
        """Registry creates and caches circuit breakers by name."""
        from app.modules.pipeline.services.circuit_breaker import (
            ProviderCircuitBreakerRegistry,
        )

        registry = ProviderCircuitBreakerRegistry()
        cb1 = await registry.get_or_create("stt_deepgram")
        cb2 = await registry.get_or_create("stt_deepgram")
        cb3 = await registry.get_or_create("llm_groq")

        assert cb1 is cb2, "Should return same instance for same name"
        assert cb1 is not cb3, "Should return different instance for different name"

    @pytest.mark.asyncio
    async def test_get_status(self) -> None:
        """Registry returns status of all breakers."""
        from app.modules.pipeline.services.circuit_breaker import (
            ProviderCircuitBreakerRegistry,
        )

        registry = ProviderCircuitBreakerRegistry()
        await registry.get_or_create("stt_deepgram")
        await registry.get_or_create("llm_groq")

        status = await registry.get_status()
        assert "stt_deepgram" in status
        assert "llm_groq" in status
        assert status["stt_deepgram"]["state"] == "closed"


# ── Recording Service Tests ───────────────────────────────────


class TestCallRecorder:
    """Tests for pipeline.services.recording module."""

    def test_recorder_init(self) -> None:
        """CallRecorder initializes with correct defaults."""
        from uuid import uuid4

        from app.modules.pipeline.services.recording import CallRecorder

        call_id = uuid4()
        tenant_id = uuid4()
        recorder = CallRecorder(call_id=call_id, tenant_id=tenant_id)

        assert recorder.call_id == call_id
        assert recorder.tenant_id == tenant_id
        assert recorder.sample_rate == 16000
        assert recorder.channels == 1

    def test_add_audio_frame(self) -> None:
        """Audio frames are accumulated in the buffer."""
        from uuid import uuid4

        from app.modules.pipeline.services.recording import CallRecorder

        recorder = CallRecorder(call_id=uuid4(), tenant_id=uuid4())
        recorder.add_audio_frame(b"\x00" * 3200)
        recorder.add_audio_frame(b"\x00" * 3200)

        assert recorder._frame_count == 2

    def test_duration_calculation(self) -> None:
        """Duration is calculated correctly from audio data."""
        from uuid import uuid4

        from app.modules.pipeline.services.recording import CallRecorder

        recorder = CallRecorder(call_id=uuid4(), tenant_id=uuid4())
        # 16000 samples/sec * 2 bytes/sample * 1 channel = 32000 bytes/sec
        # 32000 bytes = 1 second
        recorder.add_audio_frame(b"\x00" * 32000)

        assert abs(recorder.get_duration_seconds() - 1.0) < 0.01

    def test_to_wav_bytes(self) -> None:
        """WAV output starts with RIFF header."""
        from uuid import uuid4

        from app.modules.pipeline.services.recording import CallRecorder

        recorder = CallRecorder(call_id=uuid4(), tenant_id=uuid4())
        recorder.add_audio_frame(b"\x00" * 3200)

        wav = recorder.to_wav_bytes()
        assert wav[:4] == b"RIFF"
        assert b"WAVE" in wav[:12]

    @pytest.mark.asyncio
    async def test_upload_returns_none_when_not_configured(self) -> None:
        """Upload returns None when S3 credentials are not set."""
        from uuid import uuid4

        from app.modules.pipeline.services.recording import CallRecorder

        recorder = CallRecorder(call_id=uuid4(), tenant_id=uuid4())
        recorder.add_audio_frame(b"\x00" * 3200)

        result = await recorder.upload()
        # S3 creds are empty in test env
        assert result is None

    @pytest.mark.asyncio
    async def test_upload_returns_none_when_empty(self) -> None:
        """Upload returns None when no audio was recorded."""
        from uuid import uuid4

        from app.modules.pipeline.services.recording import CallRecorder

        recorder = CallRecorder(call_id=uuid4(), tenant_id=uuid4())
        result = await recorder.upload()
        assert result is None

    def test_reset(self) -> None:
        """Reset clears the recording buffer."""
        from uuid import uuid4

        from app.modules.pipeline.services.recording import CallRecorder

        recorder = CallRecorder(call_id=uuid4(), tenant_id=uuid4())
        recorder.add_audio_frame(b"\x00" * 3200)
        recorder.start()
        recorder.reset()

        assert recorder._frame_count == 0
        assert recorder._started_at is None


# ── Module Exports Tests ──────────────────────────────────────


class TestModuleExports:
    """Verify all Phase 5 exports are accessible."""

    def test_pipeline_services_exports(self) -> None:
        """Pipeline services __init__.py exports all Phase 5 additions."""
        from app.modules.pipeline.services import (
            LLMConfig,
            TTSConfig,
            CallRecorder,
            CircuitBreaker,
            CircuitState,
            build_function_schemas,
            get_default_llm_config,
            get_recording_url,
            provider_circuit_breakers,
            resolve_voice_id,
            resolve_voice_speed,
        )

        assert LLMConfig is not None
        assert TTSConfig is not None
        assert CallRecorder is not None
        assert CircuitBreaker is not None
        assert build_function_schemas is not None

    def test_pipeline_module_exports(self) -> None:
        """Pipeline __init__.py exports recording and circuit breaker."""
        from app.modules.pipeline import (
            CallRecorder,
            CircuitBreaker,
            get_recording_url,
            provider_circuit_breakers,
        )

        assert CallRecorder is not None
        assert CircuitBreaker is not None


# ── Factory Tests (mocked Pipecat) ────────────────────────────


class TestPipecatProviderFactorySTT:
    """Tests for PipecatProviderFactory.get_stt()."""

    @pytest.mark.asyncio
    async def test_get_stt_deepgram(self, db_session: AsyncMock) -> None:
        """get_stt returns DeepgramSTTService for deepgram provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "deepgram"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {"model": "nova-3"}

        mock_agent = MagicMock()
        mock_agent.stt_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="dg-key",
            ),
            patch(
                "pipecat.services.deepgram.stt.DeepgramSTTService",
            ) as mock_service_cls,
        ):
            await PipecatProviderFactory.get_stt(mock_agent, db_session)
            mock_service_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_stt_groq_whisper(self, db_session: AsyncMock) -> None:
        """get_stt returns GroqSTTService for groq_whisper provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "groq_whisper"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {"model": "whisper-large-v3-turbo"}

        mock_agent = MagicMock()
        mock_agent.stt_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="groq-key",
            ),
            patch(
                "pipecat.services.groq.stt.GroqSTTService",
            ) as mock_service_cls,
        ):
            await PipecatProviderFactory.get_stt(mock_agent, db_session)
            call_kwargs = mock_service_cls.call_args[1]
            assert call_kwargs["api_key"] == "groq-key"
            assert call_kwargs["model"] == "whisper-large-v3-turbo"

    @pytest.mark.asyncio
    async def test_get_stt_groq_whisper_uses_configured_default_model(
        self,
        db_session: AsyncMock,
    ) -> None:
        """Groq Whisper falls back to DEFAULT_STT_MODEL when provider config omits a model."""
        from types import SimpleNamespace

        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "groq_whisper"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {"model": "whisper-large-v3"}

        mock_agent = MagicMock()
        mock_agent.stt_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.id = "agent-id"

        settings = SimpleNamespace(
            DEFAULT_STT_PROVIDER="groq_whisper",
            DEFAULT_STT_MODEL="nova-3-general",
        )

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="groq-key",
            ),
            patch("app.modules.pipeline.factory.get_settings", return_value=settings),
            patch(
                "pipecat.services.groq.stt.GroqSTTService",
            ) as mock_service_cls,
        ):
            await PipecatProviderFactory.get_stt(mock_agent, db_session)

        call_kwargs = mock_service_cls.call_args[1]
        assert call_kwargs["api_key"] == "groq-key"
        assert call_kwargs["model"] == "whisper-large-v3"

    @pytest.mark.asyncio
    async def test_get_stt_assemblyai(self, db_session: AsyncMock) -> None:
        """get_stt returns AssemblyAISTTService for assemblyai provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "assemblyai"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {}

        mock_agent = MagicMock()
        mock_agent.stt_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="assembly-key",
            ),
            patch(
                "pipecat.services.assemblyai.stt.AssemblyAISTTService",
            ) as mock_service_cls,
        ):
            await PipecatProviderFactory.get_stt(mock_agent, db_session)
            mock_service_cls.assert_called_once_with(api_key="assembly-key")

    @pytest.mark.asyncio
    async def test_get_stt_azure_speech(self, db_session: AsyncMock) -> None:
        """get_stt returns AzureSTTService for azure_speech provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "azure_speech"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {"region": "eastus2"}

        mock_agent = MagicMock()
        mock_agent.stt_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="azure-speech-key",
            ),
            patch(
                "pipecat.services.azure.stt.AzureSTTService",
            ) as mock_service_cls,
        ):
            await PipecatProviderFactory.get_stt(mock_agent, db_session)
            mock_service_cls.assert_called_once_with(
                api_key="azure-speech-key",
                region="eastus2",
            )

    @pytest.mark.asyncio
    async def test_get_stt_azure_speech_uses_env_fallback(self, db_session: AsyncMock) -> None:
        """Azure Speech STT can resolve from env fallback with region config."""
        from types import SimpleNamespace

        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_agent = MagicMock()
        mock_agent.stt_provider_id = None
        mock_agent.tenant_id = "tenant-id"
        mock_agent.id = "agent-id"

        settings = SimpleNamespace(
            DEFAULT_STT_PROVIDER="azure_speech",
            DEFAULT_STT_MODEL="nova-3-general",
            PROVIDER_ENV_FALLBACK_ENABLED=True,
            ENVIRONMENT="development",
            AZURE_SPEECH_API_KEY="azure-env-key",
            AZURE_SPEECH_REGION="centralindia",
        )

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("app.modules.pipeline.factory.get_settings", return_value=settings),
            patch(
                "pipecat.services.azure.stt.AzureSTTService",
            ) as mock_service_cls,
        ):
            await PipecatProviderFactory.get_stt(mock_agent, db_session)

        mock_service_cls.assert_called_once_with(
            api_key="azure-env-key",
            region="centralindia",
        )

    @pytest.mark.asyncio
    async def test_get_stt_falls_back_to_env_when_db_secret_missing(
        self,
        db_session: AsyncMock,
    ) -> None:
        """Missing DB secrets should fall back to env keys in non-production."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.id = "provider-id"
        mock_key.provider_name = "groq_whisper"
        mock_key.api_key_encrypted = None
        mock_key.secret_ref = None
        mock_key.config = {"model": "whisper-large-v3-turbo"}

        mock_agent = MagicMock()
        mock_agent.stt_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                side_effect=Exception("should not be used directly"),
            ),
            patch(
                "app.modules.pipeline.factory._resolve_db_api_key",
                new_callable=AsyncMock,
                side_effect=ValueError("Provider secret unavailable for groq_whisper"),
            ),
            patch(
                "app.modules.pipeline.factory._provider_env_fallback_enabled",
                return_value=True,
            ),
            patch(
                "app.modules.pipeline.factory._get_env_api_key",
                return_value="groq-env-key",
            ),
            patch(
                "pipecat.services.groq.stt.GroqSTTService",
            ) as mock_service_cls,
        ):
            await PipecatProviderFactory.get_stt(mock_agent, db_session)

        call_kwargs = mock_service_cls.call_args[1]
        assert call_kwargs["api_key"] == "groq-env-key"
        assert call_kwargs["model"] == "whisper-large-v3-turbo"


class TestPipecatProviderFactoryLLM:
    """Tests for PipecatProviderFactory.get_llm()."""

    @pytest.mark.asyncio
    async def test_get_llm_openai(self, db_session: AsyncMock) -> None:
        """get_llm returns OpenAILLMService for openai provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "openai"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {"model": "gpt-4o-mini"}

        mock_agent = MagicMock()
        mock_agent.llm_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.llm_model = None
        mock_agent.llm_temperature = None
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="sk-test-key",
            ),
            patch(
                "pipecat.services.openai.llm.OpenAILLMService",
            ) as mock_service_cls,
        ):
            result = await PipecatProviderFactory.get_llm(mock_agent, db_session)
            mock_service_cls.assert_called_once_with(
                api_key="sk-test-key",
                model="gpt-4o-mini",
            )

    @pytest.mark.asyncio
    async def test_get_llm_groq(self, db_session: AsyncMock) -> None:
        """get_llm returns GroqLLMService for groq provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "groq"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {}

        mock_agent = MagicMock()
        mock_agent.llm_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.llm_model = None
        mock_agent.llm_temperature = None
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="gsk_test_key",
            ),
            patch(
                "pipecat.services.groq.llm.GroqLLMService",
            ) as mock_service_cls,
        ):
            result = await PipecatProviderFactory.get_llm(mock_agent, db_session)
            mock_service_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_llm_anthropic(self, db_session: AsyncMock) -> None:
        """get_llm returns AnthropicLLMService for anthropic provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "anthropic"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {"model": "claude-sonnet-4-20250514"}

        mock_agent = MagicMock()
        mock_agent.llm_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.llm_model = None
        mock_agent.llm_temperature = None
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="anthropic-key",
            ),
            patch(
                "pipecat.services.anthropic.llm.AnthropicLLMService",
            ) as mock_service_cls,
        ):
            await PipecatProviderFactory.get_llm(mock_agent, db_session)
            mock_service_cls.assert_called_once_with(
                api_key="anthropic-key",
                model="claude-sonnet-4-20250514",
            )

    @pytest.mark.asyncio
    async def test_get_llm_cerebras(self, db_session: AsyncMock) -> None:
        """get_llm returns CerebrasLLMService for cerebras provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "cerebras"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {"model": "gpt-oss-120b"}

        mock_agent = MagicMock()
        mock_agent.llm_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.llm_model = None
        mock_agent.llm_temperature = None
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="cerebras-key",
            ),
            patch(
                "pipecat.services.cerebras.llm.CerebrasLLMService",
            ) as mock_service_cls,
        ):
            await PipecatProviderFactory.get_llm(mock_agent, db_session)
            mock_service_cls.assert_called_once_with(
                api_key="cerebras-key",
                model="gpt-oss-120b",
            )

    @pytest.mark.asyncio
    async def test_get_llm_azure_openai(self, db_session: AsyncMock) -> None:
        """get_llm returns AzureLLMService for azure_openai provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "azure_openai"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {
            "model": "gpt-4o-mini",
            "endpoint": "https://example.openai.azure.com",
        }

        mock_agent = MagicMock()
        mock_agent.llm_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.llm_model = None
        mock_agent.llm_temperature = None
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="azure-openai-key",
            ),
            patch(
                "pipecat.services.azure.llm.AzureLLMService",
            ) as mock_service_cls,
        ):
            await PipecatProviderFactory.get_llm(mock_agent, db_session)
            mock_service_cls.assert_called_once_with(
                api_key="azure-openai-key",
                endpoint="https://example.openai.azure.com",
                model="gpt-4o-mini",
            )

    @pytest.mark.asyncio
    async def test_get_llm_unknown_provider_raises(self, db_session: AsyncMock) -> None:
        """get_llm raises ValueError for unknown provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "unknown_llm"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {}

        mock_agent = MagicMock()
        mock_agent.llm_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.llm_model = None
        mock_agent.llm_temperature = None
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="test-key",
            ),
        ):
            with pytest.raises(ValueError, match="Unknown LLM provider"):
                await PipecatProviderFactory.get_llm(mock_agent, db_session)

    @pytest.mark.asyncio
    async def test_get_llm_production_disables_env_fallback(self, db_session: AsyncMock) -> None:
        """Production runtime must not fall back to env provider keys."""
        from types import SimpleNamespace

        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_agent = MagicMock()
        mock_agent.llm_provider_id = None
        mock_agent.tenant_id = "tenant-id"
        mock_agent.llm_model = None
        mock_agent.llm_temperature = None
        mock_agent.id = "agent-id"

        settings = SimpleNamespace(
            DEFAULT_LLM_PROVIDER="openai",
            PROVIDER_ENV_FALLBACK_ENABLED=True,
            ENVIRONMENT="production",
        )

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("app.modules.pipeline.factory.get_settings", return_value=settings),
            patch("app.modules.pipeline.factory._get_env_api_key", return_value="sk-env-key"),
        ):
            with pytest.raises(ValueError, match="add a tenant or global provider key in the platform"):
                await PipecatProviderFactory.get_llm(mock_agent, db_session)


class TestPipecatProviderFactoryTTS:
    """Tests for PipecatProviderFactory.get_tts()."""

    @pytest.mark.asyncio
    async def test_get_tts_cartesia(self, db_session: AsyncMock) -> None:
        """get_tts returns CartesiaTTSService for cartesia provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "cartesia"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {"model": "sonic-3", "voice_id": "test-voice"}

        mock_agent = MagicMock()
        mock_agent.tts_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.voice_id = None
        mock_agent.voice_speed = None
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="cartesia-key",
            ),
            patch(
                "pipecat.services.cartesia.tts.CartesiaTTSService",
            ) as mock_service_cls,
        ):
            result = await PipecatProviderFactory.get_tts(mock_agent, db_session)
            mock_service_cls.assert_called_once_with(
                api_key="cartesia-key",
                voice_id="test-voice",
                model="sonic-3",
            )

    @pytest.mark.asyncio
    async def test_get_tts_elevenlabs(self, db_session: AsyncMock) -> None:
        """get_tts returns ElevenLabsTTSService for elevenlabs provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "elevenlabs"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {"voice_id": "rachel"}

        mock_agent = MagicMock()
        mock_agent.tts_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.voice_id = None
        mock_agent.voice_speed = None
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="el-key",
            ),
            patch(
                "pipecat.services.elevenlabs.tts.ElevenLabsTTSService",
            ) as mock_service_cls,
        ):
            result = await PipecatProviderFactory.get_tts(mock_agent, db_session)
            mock_service_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_tts_groq(self, db_session: AsyncMock) -> None:
        """get_tts returns GroqTTSService for groq_tts provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "groq_tts"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {
            "voice_id": "autumn",
            "model": "canopylabs/orpheus-v1-english",
        }

        mock_agent = MagicMock()
        mock_agent.tts_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.voice_id = None
        mock_agent.voice_speed = None
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="groq-tts-key",
            ),
            patch(
                "pipecat.services.groq.tts.GroqTTSService",
            ) as mock_service_cls,
        ):
            await PipecatProviderFactory.get_tts(mock_agent, db_session)
            mock_service_cls.assert_called_once_with(
                api_key="groq-tts-key",
                voice_id="autumn",
                model_name="canopylabs/orpheus-v1-english",
            )

    @pytest.mark.asyncio
    async def test_get_tts_inworld(self, db_session: AsyncMock) -> None:
        """get_tts returns InworldTTSService for inworld provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "inworld"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {
            "voice_id": "Ashley",
            "model": "inworld-tts-1.5-max",
        }

        mock_agent = MagicMock()
        mock_agent.tts_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.voice_id = None
        mock_agent.voice_speed = None
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="inworld-key",
            ),
            patch(
                "pipecat.services.inworld.tts.InworldTTSService",
            ) as mock_service_cls,
        ):
            await PipecatProviderFactory.get_tts(mock_agent, db_session)
            mock_service_cls.assert_called_once_with(
                api_key="inworld-key",
                voice_id="Ashley",
                model="inworld-tts-1.5-max",
            )

    @pytest.mark.asyncio
    async def test_get_tts_openai(self, db_session: AsyncMock) -> None:
        """get_tts returns OpenAITTSService for openai_tts provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "openai_tts"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {"voice_id": "alloy"}

        mock_agent = MagicMock()
        mock_agent.tts_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.voice_id = None
        mock_agent.voice_speed = None
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="openai-tts-key",
            ),
            patch(
                "pipecat.services.openai.tts.OpenAITTSService",
            ) as mock_service_cls,
        ):
            await PipecatProviderFactory.get_tts(mock_agent, db_session)
            mock_service_cls.assert_called_once_with(
                api_key="openai-tts-key",
                voice="alloy",
            )

    @pytest.mark.asyncio
    async def test_get_tts_lmnt(self, db_session: AsyncMock) -> None:
        """get_tts returns LmntTTSService for lmnt provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "lmnt"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {"voice_id": "ava"}

        mock_agent = MagicMock()
        mock_agent.tts_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.voice_id = None
        mock_agent.voice_speed = None
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="lmnt-key",
            ),
            patch(
                "pipecat.services.lmnt.tts.LmntTTSService",
            ) as mock_service_cls,
        ):
            await PipecatProviderFactory.get_tts(mock_agent, db_session)
            mock_service_cls.assert_called_once_with(
                api_key="lmnt-key",
                voice_id="ava",
            )

    @pytest.mark.asyncio
    async def test_get_tts_azure_speech(self, db_session: AsyncMock) -> None:
        """get_tts returns AzureTTSService for azure_speech provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "azure_speech"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {"region": "centralindia", "voice_id": "en-IN-NeerjaNeural"}

        mock_agent = MagicMock()
        mock_agent.tts_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.voice_id = None
        mock_agent.voice_speed = None
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="azure-speech-key",
            ),
            patch(
                "pipecat.services.azure.tts.AzureTTSService",
            ) as mock_service_cls,
        ):
            await PipecatProviderFactory.get_tts(mock_agent, db_session)

        mock_service_cls.assert_called_once_with(
            api_key="azure-speech-key",
            region="centralindia",
            voice="en-IN-NeerjaNeural",
        )

    @pytest.mark.asyncio
    async def test_get_tts_unknown_provider_raises(self, db_session: AsyncMock) -> None:
        """get_tts raises ValueError for unknown provider."""
        from app.modules.pipeline.factory import PipecatProviderFactory

        mock_key = MagicMock()
        mock_key.provider_name = "unknown_tts"
        mock_key.api_key_encrypted = "encrypted_key"
        mock_key.config = {}

        mock_agent = MagicMock()
        mock_agent.tts_provider_id = "some-id"
        mock_agent.tenant_id = "tenant-id"
        mock_agent.voice_id = None
        mock_agent.voice_speed = None
        mock_agent.id = "agent-id"

        with (
            patch(
                "app.modules.pipeline.factory._get_provider_key",
                new_callable=AsyncMock,
                return_value=mock_key,
            ),
            patch(
                "app.modules.pipeline.factory.resolve_stored_secret",
                new_callable=AsyncMock,
                return_value="test-key",
            ),
        ):
            with pytest.raises(ValueError, match="Unknown TTS provider"):
                await PipecatProviderFactory.get_tts(mock_agent, db_session)
