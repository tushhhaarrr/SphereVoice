#
# Pipecat Voice Agent — Configuration UI Server
# FastAPI backend that manages bot lifecycle and configuration
#

import asyncio
import json
import os
import signal
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from livekit import api as lk_api, rtc
from loguru import logger
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Pipecat imports
# ---------------------------------------------------------------------------
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    InterimTranscriptionFrame,
    TTSSpeakFrame,
    TTSTextFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.frames.frames import MetricsFrame
from pipecat.metrics.metrics import (
    LLMUsageMetricsData,
    ProcessingMetricsData,
    TTFBMetricsData,
    TTSUsageMetricsData,
)
from pipecat.observers.base_observer import BaseObserver, FramePushed
from pipecat.observers.loggers.debug_log_observer import DebugLogObserver
from pipecat.observers.user_bot_latency_observer import UserBotLatencyObserver
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport
from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import (
    SpeechTimeoutUserTurnStopStrategy,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
CONFIGS_DIR = BASE_DIR / "configs"
CONFIGS_DIR.mkdir(exist_ok=True)
STATIC_DIR = BASE_DIR / "static"

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class LLMConfig(BaseModel):
    provider: str = "azure"  # azure, openai, anthropic, groq, together, ollama, deepseek, google, cerebras, fireworks, openrouter
    api_key: str = ""
    endpoint: str = ""       # For Azure / custom endpoints
    model: str = ""
    api_version: str = "2024-10-21"  # Azure only
    base_url: str = ""       # For non-Azure providers

class STTConfig(BaseModel):
    provider: str = "azure"  # azure, deepgram, openai, assemblyai, gladia, groq, whisper
    api_key: str = ""
    region: str = ""         # Azure only
    language: str = "en-US"
    url: str = ""            # Deepgram custom URL
    model: str = ""          # For providers that support model selection

class TTSConfig(BaseModel):
    provider: str = "azure"  # azure, elevenlabs, cartesia, openai, deepgram, playht, rime, google, groq, sarvam, smallest, svara, svara_stream, svara_elevenlabs, inworld, inworld_ws
    api_key: str = ""
    region: str = ""         # Azure only
    voice: str = ""
    model: str = ""
    language: str = ""       # For providers like sarvam, smallest (e.g. "hi", "en")
    url: str = ""            # Svara: WebSocket base URL (e.g. ws://host:port)
    aggregate_sentences: bool = True  # Aggregate into sentences before synthesis

class VADConfig(BaseModel):
    stop_secs: float = 0.15
    start_secs: float = 0.15
    min_volume: float = 0.5
    confidence: float = 0.7

class TurnConfig(BaseModel):
    strategy: str = "speech_timeout"  # speech_timeout, turn_analyzer
    speech_timeout: float = 0.4

class AgentConfig(BaseModel):
    name: str = "default"
    system_prompt: str = "You are a helpful voice assistant. Keep responses very short, one to two sentences max. Be direct and conversational."
    greeting: str = "Hello! How can I help you today?"
    llm: LLMConfig = LLMConfig()
    stt: STTConfig = STTConfig()
    tts: TTSConfig = TTSConfig()
    vad: VADConfig = VADConfig()
    turn: TurnConfig = TurnConfig()

class SaveConfigRequest(BaseModel):
    name: str
    config: AgentConfig

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
bot_process: Optional[asyncio.Task] = None
bot_runner: Optional[PipelineRunner] = None
bot_task: Optional[PipelineTask] = None
current_config: Optional[AgentConfig] = None
bot_status = {"running": False, "room": "", "error": ""}
log_connections: list[WebSocket] = []

# SIP call tracking: room_name -> {task, runner, process}
sip_bots: dict[str, dict] = {}

# SIP room watcher state
sip_watcher_task: Optional[asyncio.Task] = None
sip_watcher_enabled = True   # enabled by default so inbound calls are always handled
sip_seen_rooms: set[str] = set()

# ---------------------------------------------------------------------------
# Service factory functions
# ---------------------------------------------------------------------------

def create_llm_service(cfg: LLMConfig):
    """Create an LLM service from config."""
    if cfg.provider == "azure":
        from pipecat.services.azure.llm import AzureLLMService
        return AzureLLMService(
            api_key=cfg.api_key,
            endpoint=cfg.endpoint,
            model=cfg.model,
            api_version=cfg.api_version,
        )
    elif cfg.provider == "openai":
        from pipecat.services.openai.llm import OpenAILLMService
        return OpenAILLMService(
            api_key=cfg.api_key,
            model=cfg.model,
            base_url=cfg.base_url or None,
        )
    elif cfg.provider == "anthropic":
        from pipecat.services.anthropic.llm import AnthropicLLMService
        return AnthropicLLMService(
            api_key=cfg.api_key,
            model=cfg.model,
        )
    elif cfg.provider == "groq":
        from pipecat.services.groq.llm import GroqLLMService
        return GroqLLMService(
            api_key=cfg.api_key,
            model=cfg.model,
        )
    elif cfg.provider == "together":
        from pipecat.services.together.llm import TogetherLLMService
        return TogetherLLMService(
            api_key=cfg.api_key,
            model=cfg.model,
        )
    elif cfg.provider == "ollama":
        from pipecat.services.ollama.llm import OLLamaLLMService
        return OLLamaLLMService(
            model=cfg.model,
            base_url=cfg.base_url or "http://localhost:11434/v1",
        )
    elif cfg.provider == "deepseek":
        from pipecat.services.deepseek.llm import DeepSeekLLMService
        return DeepSeekLLMService(
            api_key=cfg.api_key,
            model=cfg.model,
        )
    elif cfg.provider == "google":
        from pipecat.services.google.llm import GoogleLLMService
        return GoogleLLMService(
            api_key=cfg.api_key,
            model=cfg.model,
        )
    elif cfg.provider == "cerebras":
        from pipecat.services.cerebras.llm import CerebrasLLMService
        return CerebrasLLMService(
            api_key=cfg.api_key,
            model=cfg.model,
        )
    elif cfg.provider == "fireworks":
        from pipecat.services.fireworks.llm import FireworksLLMService
        return FireworksLLMService(
            api_key=cfg.api_key,
            model=cfg.model,
        )
    elif cfg.provider == "openrouter":
        from pipecat.services.openrouter.llm import OpenRouterLLMService
        return OpenRouterLLMService(
            api_key=cfg.api_key,
            model=cfg.model,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {cfg.provider}")


def create_stt_service(cfg: STTConfig):
    """Create an STT service from config."""
    from pipecat.transcriptions.language import Language

    # Parse the language string into a Language enum (e.g. "en-US" -> Language.EN_US)
    stt_language: Language = Language.EN
    if cfg.language:
        lang_str = cfg.language.strip()
        # Try exact match first, then base language code
        for member in Language:
            if member.value == lang_str:
                stt_language = member
                break
        else:
            # Try base code (e.g. "en" from "en-US")
            base = lang_str.split("-")[0].lower()
            for member in Language:
                if member.value == base:
                    stt_language = member
                    break

    logger.info(f"Creating STT: provider={cfg.provider}, language={stt_language.value}")

    if cfg.provider == "azure":
        from pipecat.services.azure.stt import AzureSTTService
        return AzureSTTService(
            api_key=cfg.api_key,
            region=cfg.region,
            language=stt_language,
        )
    elif cfg.provider == "deepgram":
        from pipecat.services.deepgram.stt import DeepgramSTTService
        from deepgram import LiveOptions
        return DeepgramSTTService(
            api_key=cfg.api_key,
            live_options=LiveOptions(language=stt_language),
        )
    elif cfg.provider == "openai":
        from pipecat.services.openai.stt import OpenAISTTService
        return OpenAISTTService(
            api_key=cfg.api_key,
            model=cfg.model or "whisper-1",
            language=stt_language,
        )
    elif cfg.provider == "assemblyai":
        from pipecat.services.assemblyai.stt import AssemblyAISTTService
        return AssemblyAISTTService(
            api_key=cfg.api_key,
        )
    elif cfg.provider == "gladia":
        from pipecat.services.gladia.stt import GladiaSTTService
        return GladiaSTTService(
            api_key=cfg.api_key,
        )
    elif cfg.provider == "groq":
        from pipecat.services.groq.stt import GroqSTTService
        return GroqSTTService(
            api_key=cfg.api_key,
            model=cfg.model or "whisper-large-v3-turbo",
            language=stt_language,
        )
    elif cfg.provider == "whisper":
        from pipecat.services.whisper.stt import WhisperSTTService
        return WhisperSTTService(
            model=cfg.model or "tiny",
            language=stt_language,
        )
    else:
        raise ValueError(f"Unknown STT provider: {cfg.provider}")


def create_tts_service(cfg: TTSConfig):
    """Create a TTS service from config."""
    logger.info(f"Creating TTS: provider={cfg.provider}, aggregate_sentences={cfg.aggregate_sentences}")
    if cfg.provider == "azure":
        from pipecat.services.azure.tts import AzureTTSService
        return AzureTTSService(
            api_key=cfg.api_key,
            region=cfg.region,
            voice=cfg.voice or "en-US-SaraNeural",
            aggregate_sentences=cfg.aggregate_sentences,
        )
    elif cfg.provider == "elevenlabs":
        from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
        return ElevenLabsTTSService(
            api_key=cfg.api_key,
            voice_id=cfg.voice,
            model=cfg.model or "eleven_turbo_v2_5",
            aggregate_sentences=cfg.aggregate_sentences,
        )
    elif cfg.provider == "cartesia":
        from pipecat.services.cartesia.tts import CartesiaTTSService
        return CartesiaTTSService(
            api_key=cfg.api_key,
            voice_id=cfg.voice,
            aggregate_sentences=cfg.aggregate_sentences,
        )
    elif cfg.provider == "openai":
        from pipecat.services.openai.tts import OpenAITTSService
        return OpenAITTSService(
            api_key=cfg.api_key,
            voice=cfg.voice or "alloy",
            model=cfg.model or "tts-1",
            aggregate_sentences=cfg.aggregate_sentences,
        )
    elif cfg.provider == "deepgram":
        from pipecat.services.deepgram.tts import DeepgramTTSService
        return DeepgramTTSService(
            api_key=cfg.api_key,
            voice=cfg.voice or "aura-asteria-en",
            aggregate_sentences=cfg.aggregate_sentences,
        )
    elif cfg.provider == "playht":
        from pipecat.services.playht.tts import PlayHTTTSService
        return PlayHTTTSService(
            api_key=cfg.api_key,
            voice_url=cfg.voice,
            aggregate_sentences=cfg.aggregate_sentences,
        )
    elif cfg.provider == "rime":
        from pipecat.services.rime.tts import RimeTTSService
        return RimeTTSService(
            api_key=cfg.api_key,
            voice_id=cfg.voice or "mist",
            model=cfg.model or "mist",
            aggregate_sentences=cfg.aggregate_sentences,
        )
    elif cfg.provider == "google":
        from pipecat.services.google.tts import GoogleTTSService
        return GoogleTTSService(
            voice_id=cfg.voice,
            aggregate_sentences=cfg.aggregate_sentences,
        )
    elif cfg.provider == "groq":
        from pipecat.services.groq.tts import GroqTTSService
        return GroqTTSService(
            api_key=cfg.api_key,
            voice_id=cfg.voice or "autumn",
            model_name=cfg.model or "canopylabs/orpheus-v1-english",
            aggregate_sentences=cfg.aggregate_sentences,
        )
    elif cfg.provider == "sarvam":
        from pipecat.services.sarvam.tts import SarvamTTSService
        from pipecat.transcriptions.language import Language
        # Map language string to Language enum (default Hindi)
        lang_map = {"hi": Language.HI, "en": Language.EN, "bn": Language.BN,
                    "gu": Language.GU, "kn": Language.KN, "ml": Language.ML,
                    "mr": Language.MR, "or": Language.OR, "pa": Language.PA,
                    "ta": Language.TA, "te": Language.TE}
        lang = lang_map.get(cfg.language or "hi", Language.HI)
        return SarvamTTSService(
            api_key=cfg.api_key,
            model=cfg.model or "bulbul:v2",
            voice_id=cfg.voice or "manisha",
            params=SarvamTTSService.InputParams(language=lang),
        )
    elif cfg.provider == "smallest":
        import aiohttp as _aiohttp
        from pipecat.services.smallest.tts import SmallestTTSService
        from pipecat.transcriptions.language import Language
        lang_map = {"hi": Language.HI, "en": Language.EN, "mr": Language.MR,
                    "kn": Language.KN, "ta": Language.TA, "bn": Language.BN,
                    "gu": Language.GU, "de": Language.DE, "fr": Language.FR,
                    "es": Language.ES, "it": Language.IT, "pl": Language.PL,
                    "nl": Language.NL, "ru": Language.RU, "ar": Language.AR,
                    "he": Language.HE}
        lang = lang_map.get(cfg.language or "hi", Language.HI)
        # Create a module-level aiohttp session for Smallest TTS
        session = _aiohttp.ClientSession()
        return SmallestTTSService(
            api_key=cfg.api_key,
            aiohttp_session=session,
            model=cfg.model or "lightning",
            voice_id=cfg.voice or "emily",
            params=SmallestTTSService.InputParams(language=lang),
        )
    elif cfg.provider == "svara":
        from custom_ws_tts import SvaraTTSService
        return SvaraTTSService(
            base_url=cfg.url or "ws://172.203.82.11:9113",
            voice=cfg.voice or "en_female",
            aggregate_sentences=cfg.aggregate_sentences,
        )
    elif cfg.provider == "svara_stream":
        from custom_ws_tts import SvaraStreamingTTSService
        return SvaraStreamingTTSService(
            base_url=cfg.url or "ws://172.203.82.11:9113",
            voice=cfg.voice or "en_female",
            aggregate_sentences=cfg.aggregate_sentences,
        )
    elif cfg.provider == "svara_elevenlabs":
        from custom_ws_tts import SvaraElevenLabsTTSService
        return SvaraElevenLabsTTSService(
            base_url=cfg.url or "ws://172.203.82.11:9113",
            voice=cfg.voice or "English+Female",
            aggregate_sentences=cfg.aggregate_sentences,
        )
    elif cfg.provider == "inworld":
        import aiohttp as _aiohttp
        from pipecat.services.inworld.tts import InworldHttpTTSService
        session = _aiohttp.ClientSession()
        # Map short language codes to Inworld languageCode format
        lang_code = None
        if cfg.language:
            inworld_lang_map = {
                "hi": "hi-IN", "en": "en-US", "de": "de-DE", "es": "es-ES",
                "fr": "fr-FR", "it": "it-IT", "ja": "ja-JP", "ko": "ko-KR",
                "nl": "nl-NL", "pl": "pl-PL", "pt": "pt-BR", "ru": "ru-RU",
                "zh": "zh-CN",
            }
            lang_code = inworld_lang_map.get(cfg.language, cfg.language)
        return InworldHttpTTSService(
            api_key=cfg.api_key,
            aiohttp_session=session,
            voice_id=cfg.voice or "Ashley",
            model=cfg.model or "inworld-tts-1.5-max",
            streaming=True,
            params=InworldHttpTTSService.InputParams(language_code=lang_code),
        )
    elif cfg.provider == "inworld_ws":
        from pipecat.services.inworld.tts import InworldTTSService
        return InworldTTSService(
            api_key=cfg.api_key,
            voice_id=cfg.voice or "Ashley",
            model=cfg.model or "inworld-tts-1.5-max",
            url=cfg.url or "wss://api.inworld.ai/tts/v1/voice:streamBidirectional",
        )
    else:
        raise ValueError(f"Unknown TTS provider: {cfg.provider}")


# ---------------------------------------------------------------------------
# Bot lifecycle
# ---------------------------------------------------------------------------

async def broadcast_log(message: str):
    """Send log message to all connected WebSocket clients."""
    dead = []
    for ws in log_connections:
        try:
            await ws.send_json({"type": "log", "message": message})
        except Exception:
            dead.append(ws)
    for ws in dead:
        log_connections.remove(ws)


async def broadcast_ws(data: dict):
    """Send arbitrary JSON data to all connected WebSocket clients."""
    dead = []
    for ws in log_connections:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        log_connections.remove(ws)


class TranscriptBroadcastObserver(BaseObserver):
    """Observer that broadcasts transcription and bot speech to the UI WebSocket."""

    async def on_push_frame(self, data: FramePushed):
        frame = data.frame
        if isinstance(frame, TranscriptionFrame) and frame.text:
            await broadcast_ws({
                "type": "transcription",
                "text": frame.text,
            })
        elif isinstance(frame, TTSTextFrame) and frame.text:
            await broadcast_ws({
                "type": "bot_speech",
                "text": frame.text,
            })


class MetricsBroadcastObserver(BaseObserver):
    """Observer that captures MetricsFrame data and broadcasts TTFB/processing/usage metrics."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._seen: set[str] = set()
        self._user_speaking_start: float | None = None

    async def on_push_frame(self, data: FramePushed):
        frame = data.frame

        # Track user speaking duration for STT cost estimation
        if isinstance(frame, UserStartedSpeakingFrame):
            import time
            self._user_speaking_start = time.monotonic()
            return
        if isinstance(frame, UserStoppedSpeakingFrame):
            import time
            if self._user_speaking_start is not None:
                dur = time.monotonic() - self._user_speaking_start
                self._user_speaking_start = None
                await broadcast_ws({
                    "type": "usage",
                    "service": "stt",
                    "audio_secs": round(dur, 3),
                })
            return

        if not isinstance(frame, MetricsFrame):
            return
        if frame.id in self._seen:
            return
        self._seen.add(frame.id)

        for m in frame.data:
            if isinstance(m, TTFBMetricsData):
                await broadcast_ws({
                    "type": "metric",
                    "metric": "ttfb",
                    "processor": m.processor,
                    "model": m.model,
                    "value": round(m.value, 4),
                })
            elif isinstance(m, ProcessingMetricsData):
                await broadcast_ws({
                    "type": "metric",
                    "metric": "processing",
                    "processor": m.processor,
                    "model": m.model,
                    "value": round(m.value, 4),
                })
            elif isinstance(m, LLMUsageMetricsData):
                await broadcast_ws({
                    "type": "usage",
                    "service": "llm",
                    "prompt_tokens": m.value.prompt_tokens,
                    "completion_tokens": m.value.completion_tokens,
                    "total_tokens": m.value.total_tokens,
                })
            elif isinstance(m, TTSUsageMetricsData):
                await broadcast_ws({
                    "type": "usage",
                    "service": "tts",
                    "characters": m.value,
                })


async def start_bot(config: AgentConfig) -> dict:
    """Start the pipecat bot with the given config."""
    global bot_process, bot_runner, bot_task, current_config, bot_status

    if bot_status["running"]:
        await stop_bot()
        await asyncio.sleep(1)

    current_config = config

    room_name = os.getenv("LIVEKIT_ROOM_NAME", "pipecat-test")
    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not url or not api_key or not api_secret:
        raise ValueError("LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET must be set in .env")

    # Generate tokens
    agent_token = lk_api.AccessToken(api_key, api_secret)
    agent_token.with_identity("Pipecat Agent").with_name("Pipecat Agent").with_grants(
        lk_api.VideoGrants(room_join=True, room=room_name, agent=True)
    )

    user_token = lk_api.AccessToken(api_key, api_secret)
    user_token.with_identity("User").with_name("User").with_grants(
        lk_api.VideoGrants(
            room_join=True, room=room_name,
            can_publish=True, can_subscribe=True, can_publish_data=True,
        )
    )

    agent_jwt = agent_token.to_jwt()
    user_jwt = user_token.to_jwt()

    async def run_bot():
        global bot_runner, bot_task, bot_status
        try:
            # Set audio output sample rate based on TTS provider
            if config.tts.provider == "groq":
                audio_out_rate = 48000
            elif config.tts.provider == "sarvam":
                audio_out_rate = 22050 if (config.tts.model or "bulbul:v2") == "bulbul:v2" else 24000
            elif config.tts.provider == "smallest":
                audio_out_rate = 24000
            else:
                audio_out_rate = None

            transport = LiveKitTransport(
                url=url,
                token=agent_jwt,
                room_name=room_name,
                params=LiveKitParams(
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                    audio_out_sample_rate=audio_out_rate,
                ),
            )

            stt = create_stt_service(config.stt)
            llm = create_llm_service(config.llm)
            tts = create_tts_service(config.tts)

            messages = [
                {"role": "system", "content": config.system_prompt},
            ]

            context = LLMContext(messages)
            user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
                context,
                user_params=LLMUserAggregatorParams(
                    vad_analyzer=SileroVADAnalyzer(
                        params=VADParams(
                            stop_secs=config.vad.stop_secs,
                            start_secs=config.vad.start_secs,
                            min_volume=config.vad.min_volume,
                            confidence=config.vad.confidence,
                        )
                    ),
                    user_turn_strategies=UserTurnStrategies(
                        stop=[SpeechTimeoutUserTurnStopStrategy(
                            user_speech_timeout=config.turn.speech_timeout,
                        )],
                    ),
                ),
            )

            pipeline = Pipeline(
                [
                    transport.input(),
                    stt,
                    user_aggregator,
                    llm,
                    tts,
                    transport.output(),
                    assistant_aggregator,
                ]
            )

            # --- Latency & metrics observers ---
            latency_observer = UserBotLatencyObserver()

            @latency_observer.event_handler("on_latency_measured")
            async def on_latency(observer, latency_seconds):
                ms = round(latency_seconds * 1000)
                await broadcast_ws({
                    "type": "metric",
                    "metric": "e2e_latency",
                    "processor": "pipeline",
                    "model": None,
                    "value": round(latency_seconds, 4),
                })
                await broadcast_log(f"⚡ E2E latency: {ms} ms")

            metrics_observer = MetricsBroadcastObserver()
            transcript_observer = TranscriptBroadcastObserver()

            bot_task = PipelineTask(
                pipeline,
                params=PipelineParams(
                    enable_metrics=True,
                    enable_usage_metrics=True,
                ),
                idle_timeout_secs=None,
                observers=[
                    DebugLogObserver(
                        frame_types=(
                            UserStartedSpeakingFrame,
                            UserStoppedSpeakingFrame,
                            TranscriptionFrame,
                            InterimTranscriptionFrame,
                        ),
                    ),
                    latency_observer,
                    metrics_observer,
                    transcript_observer,
                ],
            )

            @transport.event_handler("on_first_participant_joined")
            async def on_first_participant_joined(transport, participant_id):
                await asyncio.sleep(0.5)
                if config.greeting:
                    await bot_task.queue_frame(TTSSpeakFrame(config.greeting))

            bot_runner = PipelineRunner()
            bot_status = {"running": True, "room": room_name, "error": ""}
            await broadcast_log(f"Bot started in room: {room_name}")
            await bot_runner.run(bot_task)

        except Exception as e:
            logger.error(f"Bot error: {e}")
            bot_status = {"running": False, "room": "", "error": str(e)}
            await broadcast_log(f"Bot error: {e}")
        finally:
            bot_status["running"] = False
            await broadcast_log("Bot stopped")

    bot_process = asyncio.create_task(run_bot())

    # Wait a bit for it to start
    await asyncio.sleep(3)

    return {
        "status": "started",
        "room": room_name,
        "livekit_url": url,
        "user_token": user_jwt,
    }


async def stop_bot():
    """Stop the running bot."""
    global bot_process, bot_runner, bot_task, bot_status

    if bot_task:
        try:
            await bot_task.cancel()
        except Exception as e:
            logger.warning(f"Error cancelling task: {e}")

    if bot_process and not bot_process.done():
        bot_process.cancel()
        try:
            await bot_process
        except asyncio.CancelledError:
            pass

    bot_task = None
    bot_runner = None
    bot_process = None
    bot_status = {"running": False, "room": "", "error": ""}


# ---------------------------------------------------------------------------
# SIP inbound call bot spawner
# ---------------------------------------------------------------------------
async def start_sip_bot(room_name: str, caller_number: str = ""):
    """Spawn a Pipecat bot into the given room for a SIP call."""
    global sip_bots

    if room_name in sip_bots:
        logger.warning(f"SIP bot already running in room {room_name}, skipping")
        return

    # Use current_config if available, else load the default preset
    config = current_config
    if config is None:
        default_preset = CONFIGS_DIR / "groq-llm-azure-tts.json"
        if not default_preset.exists():
            # fallback to first available config
            presets = sorted(CONFIGS_DIR.glob("*.json"))
            default_preset = presets[0] if presets else None
        if default_preset:
            data = json.loads(default_preset.read_text())
            config = AgentConfig(**data)
            logger.info(f"SIP: loaded config from {default_preset.name}")
        else:
            logger.error("SIP: no config available for bot")
            return

    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    # Generate agent token for this specific SIP room
    agent_token = lk_api.AccessToken(api_key, api_secret)
    agent_token.with_identity(f"pipecat-sip-{room_name}").with_name("Pipecat Agent").with_grants(
        lk_api.VideoGrants(room_join=True, room=room_name, agent=True)
    ).with_sip_grants(
        lk_api.SIPGrants(call=True, admin=True)
    )
    agent_jwt = agent_token.to_jwt()

    async def run_sip_bot():
        try:
            # SIP calls: set audio output sample rate based on TTS provider
            if config.tts.provider == "groq":
                audio_out_rate = 48000
            elif config.tts.provider in ("azure", "smallest"):
                audio_out_rate = 24000
            elif config.tts.provider == "sarvam":
                audio_out_rate = 22050 if (config.tts.model or "bulbul:v2") == "bulbul:v2" else 24000
            else:
                audio_out_rate = None

            transport = LiveKitTransport(
                url=url,
                token=agent_jwt,
                room_name=room_name,
                params=LiveKitParams(
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                    audio_out_sample_rate=audio_out_rate,
                ),
            )

            stt = create_stt_service(config.stt)
            llm = create_llm_service(config.llm)
            tts = create_tts_service(config.tts)

            sip_prompt = config.system_prompt
            if caller_number:
                sip_prompt += f"\n\nThe caller's phone number is {caller_number}."

            messages = [{"role": "system", "content": sip_prompt}]
            context = LLMContext(messages)
            # SIP audio: lower VAD thresholds for phone-quality audio
            sip_vad_confidence = min(config.vad.confidence, 0.5)
            sip_vad_min_volume = min(config.vad.min_volume, 0.25)
            logger.info(f"SIP VAD: confidence={sip_vad_confidence}, min_volume={sip_vad_min_volume}, stop_secs={config.vad.stop_secs}")
            user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
                context,
                user_params=LLMUserAggregatorParams(
                    vad_analyzer=SileroVADAnalyzer(
                        params=VADParams(
                            stop_secs=config.vad.stop_secs,
                            start_secs=config.vad.start_secs,
                            min_volume=sip_vad_min_volume,
                            confidence=sip_vad_confidence,
                        )
                    ),
                    user_turn_strategies=UserTurnStrategies(
                        stop=[SpeechTimeoutUserTurnStopStrategy(
                            user_speech_timeout=config.turn.speech_timeout,
                        )],
                    ),
                ),
            )

            pipeline = Pipeline([
                transport.input(),
                stt,
                user_aggregator,
                llm,
                tts,
                transport.output(),
                assistant_aggregator,
            ])

            latency_observer = UserBotLatencyObserver()

            @latency_observer.event_handler("on_latency_measured")
            async def on_latency(observer, latency_seconds):
                ms = round(latency_seconds * 1000)
                await broadcast_ws({
                    "type": "metric",
                    "metric": "e2e_latency",
                    "processor": "pipeline",
                    "model": None,
                    "value": round(latency_seconds, 4),
                })
                await broadcast_log(f"⚡ SIP [{room_name}] E2E latency: {ms} ms")

            metrics_observer = MetricsBroadcastObserver()

            sip_task = PipelineTask(
                pipeline,
                params=PipelineParams(
                    enable_metrics=True,
                    enable_usage_metrics=True,
                ),
                idle_timeout_secs=None,
                observers=[
                    DebugLogObserver(
                        frame_types=(
                            UserStartedSpeakingFrame,
                            UserStoppedSpeakingFrame,
                            TranscriptionFrame,
                            InterimTranscriptionFrame,
                        ),
                    ),
                    latency_observer,
                    metrics_observer,
                ],
            )

            # Track whether greeting has been sent
            greeting_sent = False

            async def _send_greeting():
                """Send the greeting once after a short stabilisation delay."""
                nonlocal greeting_sent
                if greeting_sent:
                    return
                greeting_sent = True
                # Small delay for the media path to stabilise after call is answered
                await asyncio.sleep(0.5)
                greeting = config.greeting or "Hello, how can I help you?"
                logger.info(f"SIP [{room_name}]: sending greeting")
                await sip_task.queue_frame(TTSSpeakFrame(greeting))

            @transport.event_handler("on_first_participant_joined")
            async def on_first_participant_joined(transport_obj, participant_id):
                # Listen for SIP attribute changes on the Room to detect when
                # the callee actually picks up the phone.  The attribute
                # sip.callStatus transitions to "active" at that point.
                # For INBOUND calls, callStatus is already "active" on join.
                # NOTE: Audio tracks appear during ringing (early media) so
                # they are NOT reliable for detecting call answer.
                lk_room = transport_obj._client.room

                # Log ALL remote participants and their attributes for debugging
                for pid, p in lk_room.remote_participants.items():
                    logger.info(f"SIP [{room_name}]: remote participant {p.identity} "
                                f"kind={p.kind} attrs={dict(p.attributes)}")

                def _on_attributes_changed(changed_attrs, participant):
                    status = changed_attrs.get("sip.callStatus")
                    if status:
                        logger.info(f"SIP [{room_name}]: callStatus → {status} "
                                    f"(participant={participant.identity})")
                    if status == "active":
                        asyncio.ensure_future(_send_greeting())
                    elif status == "hangup":
                        logger.info(f"SIP [{room_name}]: call hung up by {participant.identity}")

                lk_room.on("participant_attributes_changed")(_on_attributes_changed)

                # Check if the participant is already in "active" state.
                # This is the normal case for INBOUND calls where the caller
                # is already on the line when the bot joins.
                for p in lk_room.remote_participants.values():
                    call_status = p.attributes.get("sip.callStatus", "")
                    logger.info(f"SIP [{room_name}]: checking participant {p.identity} "
                                f"callStatus={call_status!r}")
                    if call_status == "active":
                        logger.info(f"SIP [{room_name}]: participant already active on join "
                                    f"(inbound call) → sending greeting")
                        asyncio.ensure_future(_send_greeting())
                        return

                # Fallback: if callStatus=active never arrives (some trunks
                # don't report it), greet after 8s so the call isn't silent.
                # (reduced from 12s for faster inbound experience)
                async def _fallback_greeting():
                    await asyncio.sleep(8.0)
                    if not greeting_sent:
                        logger.warning(f"SIP [{room_name}]: fallback greeting "
                                       f"(no callStatus=active within 8s)")
                        await _send_greeting()

                asyncio.ensure_future(_fallback_greeting())

            sip_runner = PipelineRunner()
            sip_bots[room_name] = {"task": sip_task, "runner": sip_runner}
            await broadcast_log(f"📞 SIP bot joined room: {room_name} (caller: {caller_number or 'unknown'})")
            await sip_runner.run(sip_task)

        except Exception as e:
            logger.error(f"SIP bot error in {room_name}: {e}")
            await broadcast_log(f"📞 SIP bot error [{room_name}]: {e}")
        finally:
            sip_bots.pop(room_name, None)
            await broadcast_log(f"📞 SIP bot left room: {room_name}")

    asyncio.create_task(run_sip_bot())


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Pipecat Voice Agent UI")

# Serve static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main UI page."""
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text())


@app.get("/api/status")
async def get_status():
    """Get current bot status."""
    return bot_status


@app.post("/api/start")
async def api_start_bot(config: AgentConfig):
    """Start the bot with the given configuration."""
    try:
        result = await start_bot(config)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stop")
async def api_stop_bot():
    """Stop the running bot."""
    await stop_bot()
    return {"status": "stopped"}


@app.get("/api/configs")
async def list_configs():
    """List all saved configurations."""
    configs = []
    for f in sorted(CONFIGS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            configs.append({"name": f.stem, "config": data})
        except Exception:
            pass
    return configs


@app.post("/api/configs")
async def save_config(req: SaveConfigRequest):
    """Save a configuration to disk."""
    name = req.name.replace(" ", "_").replace("/", "_")
    path = CONFIGS_DIR / f"{name}.json"
    path.write_text(req.config.model_dump_json(indent=2))
    return {"status": "saved", "name": name}


@app.delete("/api/configs/{name}")
async def delete_config(name: str):
    """Delete a saved configuration."""
    path = CONFIGS_DIR / f"{name}.json"
    if path.exists():
        path.unlink()
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Config not found")


@app.get("/api/configs/{name}")
async def get_config(name: str):
    """Load a saved configuration."""
    path = CONFIGS_DIR / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    raise HTTPException(status_code=404, detail="Config not found")


@app.get("/api/env_defaults")
async def get_env_defaults():
    """Return default values from .env for pre-filling the UI."""
    return {
        "livekit_url": os.getenv("LIVEKIT_URL", ""),
        # Azure Speech (STT + TTS)
        "azure_speech_api_key": os.getenv("AZURE_SPEECH_API_KEY", ""),
        "azure_speech_region": os.getenv("AZURE_SPEECH_REGION", ""),
        # Azure OpenAI
        "azure_openai_api_key": os.getenv("AZURE_CHATGPT_API_KEY", ""),
        "azure_openai_endpoint": os.getenv("AZURE_CHATGPT_ENDPOINT", ""),
        "azure_openai_model": os.getenv("AZURE_CHATGPT_MODEL", ""),
        "openai_api_version": os.getenv("OPENAI_API_VERSION", "2024-10-21"),
        # Groq
        "groq_api_key": os.getenv("GROQ_API_KEY", ""),
        # Cerebras
        "cerebras_api_key": os.getenv("CEREBRAS_API_KEY", ""),
        # OpenAI
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        # Anthropic
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        # Google
        "google_api_key": os.getenv("GOOGLE_API_KEY", ""),
        # Deepgram
        "deepgram_api_key": os.getenv("DEEPGRAM_API_KEY", ""),
        # ElevenLabs
        "elevenlabs_api_key": os.getenv("ELEVENLABS_API_KEY", ""),
        # Together
        "together_api_key": os.getenv("TOGETHER_API_KEY", ""),
        # DeepSeek
        "deepseek_api_key": os.getenv("DEEPSEEK_API_KEY", ""),
        # Fireworks
        "fireworks_api_key": os.getenv("FIREWORKS_API_KEY", ""),
        # Cartesia
        "cartesia_api_key": os.getenv("CARTESIA_API_KEY", ""),
        # Sarvam AI
        "sarvam_api_key": os.getenv("SARVAM_API_KEY", ""),
        # Smallest AI
        "smallest_api_key": os.getenv("SMALLEST_API_KEY", ""),
        # Inworld AI
        "inworld_api_key": os.getenv("INWORLD_API_KEY", ""),
    }


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket endpoint for live logs."""
    await websocket.accept()
    log_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in log_connections:
            log_connections.remove(websocket)


# ---------------------------------------------------------------------------
# LiveKit Webhook (for SIP inbound calls)
# ---------------------------------------------------------------------------
@app.post("/livekit-webhook")
async def livekit_webhook(request: Request):
    """Receive LiveKit webhook events. When a SIP participant joins a call-* room,
    automatically spawn a Pipecat bot to handle the conversation."""
    api_key = os.getenv("LIVEKIT_API_KEY", "")
    api_secret = os.getenv("LIVEKIT_API_SECRET", "")

    body = (await request.body()).decode("utf-8")
    auth_token = request.headers.get("Authorization", "")

    # Debug: log incoming webhook details
    logger.info(f"Webhook received: content-type={request.headers.get('content-type')}, "
                f"auth_token_len={len(auth_token)}, body_len={len(body)}")
    logger.debug(f"Webhook body preview: {body[:200]}")

    try:
        receiver = lk_api.WebhookReceiver(
            lk_api.TokenVerifier(api_key, api_secret)
        )
        event = receiver.receive(body, auth_token)
    except Exception as e:
        logger.warning(f"Webhook verification failed: {e}")
        logger.warning(f"Auth token (first 50 chars): {auth_token[:50]}")
        # Fallback: try to parse without verification for debugging
        try:
            from google.protobuf.json_format import Parse
            from livekit.protocol.webhook import WebhookEvent
            event = Parse(body, WebhookEvent(), ignore_unknown_fields=True)
            logger.warning(f"Webhook parsed (UNVERIFIED): event={event.event}, "
                          f"room={event.room.name if event.room else 'N/A'}")
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type = event.event
    logger.info(f"LiveKit webhook: {event_type}")

    if event_type == "participant_joined":
        room_name = event.room.name if event.room else ""
        participant = event.participant
        identity = participant.identity if participant else ""
        kind_val = participant.kind if participant else 0

        # kind=1 is SIP participant (AGENT=2, STANDARD=0, SIP=1, EGRESS=3)
        # Also match room prefix "call-" from dispatch rule
        is_sip = kind_val == 1 or room_name.startswith("call-")
        is_agent = "pipecat" in identity.lower() or kind_val == 2

        if is_sip and not is_agent and room_name:
            caller_number = identity  # SIP identity is usually the phone number
            logger.info(f"SIP call detected: room={room_name}, caller={caller_number}")
            await broadcast_log(f"📞 Incoming SIP call: {caller_number} → room {room_name}")
            await start_sip_bot(room_name, caller_number)

    elif event_type == "room_finished":
        room_name = event.room.name if event.room else ""
        if room_name in sip_bots:
            bot_info = sip_bots[room_name]
            try:
                if bot_info.get("task"):
                    await bot_info["task"].cancel()
            except Exception as e:
                logger.warning(f"Error cleaning up SIP bot: {e}")
            sip_bots.pop(room_name, None)

    return {"status": "ok"}


@app.get("/api/sip/status")
async def sip_status():
    """Get status of active SIP call bots."""
    return {
        "active_calls": len(sip_bots),
        "rooms": list(sip_bots.keys()),
        "watcher_enabled": sip_watcher_enabled,
    }


@app.post("/api/sip/toggle")
async def sip_toggle():
    """Enable or disable the SIP room watcher."""
    global sip_watcher_enabled
    sip_watcher_enabled = not sip_watcher_enabled
    status = "enabled" if sip_watcher_enabled else "disabled"
    await broadcast_log(f"📞 SIP watcher {status}")
    logger.info(f"SIP watcher {status}")
    return {"sip_watcher_enabled": sip_watcher_enabled}


# ---------------------------------------------------------------------------
# SIP room watcher (polls LiveKit for new call-* rooms)
# ---------------------------------------------------------------------------
async def sip_room_watcher():
    """Background task that polls LiveKit Room API for new SIP call rooms
    and spawns bots automatically. No webhook configuration needed."""
    global sip_seen_rooms

    url = os.getenv("LIVEKIT_URL", "")
    api_key = os.getenv("LIVEKIT_API_KEY", "")
    api_secret = os.getenv("LIVEKIT_API_SECRET", "")

    if not url or not api_key or not api_secret:
        logger.error("SIP watcher: LIVEKIT_URL/API_KEY/API_SECRET not set")
        return

    lk = lk_api.LiveKitAPI(url=url, api_key=api_key, api_secret=api_secret)
    logger.info("SIP room watcher started (polls every 1s for call-* rooms, "
                f"watcher_enabled={sip_watcher_enabled})")

    try:
        while True:
            await asyncio.sleep(1)  # Fast poll: 1s for quicker inbound detection

            if not sip_watcher_enabled:
                continue

            try:
                rooms_resp = await lk.room.list_rooms(lk_api.ListRoomsRequest())
            except Exception as e:
                logger.warning(f"SIP watcher: list_rooms error: {e}")
                await asyncio.sleep(3)
                continue

            current_rooms = set()

            for room in rooms_resp.rooms:
                if not room.name.startswith("call-"):
                    continue

                current_rooms.add(room.name)

                # Skip rooms we already spawned a bot for
                if room.name in sip_seen_rooms or room.name in sip_bots:
                    continue

                # Per-room try/except so one stale room doesn't block others
                try:
                    # Check participants to find the SIP caller
                    parts_resp = await lk.room.list_participants(
                        lk_api.ListParticipantsRequest(room=room.name)
                    )

                    has_agent = False
                    caller_number = ""
                    sip_status = ""
                    for p in parts_resp.participants:
                        if p.kind == 2:  # AGENT
                            has_agent = True
                        elif p.kind == 1:  # SIP
                            caller_number = p.identity
                            # Read SIP attributes from participant
                            attrs = dict(p.attributes) if p.attributes else {}
                            sip_status = attrs.get("sip.callStatus", "")
                        elif "pipecat" in p.identity.lower():
                            has_agent = True

                    if not has_agent:
                        sip_seen_rooms.add(room.name)
                        caller = caller_number or "unknown"
                        logger.info(f"SIP watcher: new call in {room.name} "
                                    f"from {caller} (callStatus={sip_status!r})")
                        await broadcast_log(
                            f"📞 SIP watcher: incoming call from {caller} → {room.name}"
                        )
                        await start_sip_bot(room.name, caller_number)

                except Exception as e:
                    # Don't let one room's error block others
                    logger.warning(f"SIP watcher: error checking {room.name}: {e}")
                    continue

            # Clean up seen rooms that no longer exist
            sip_seen_rooms = sip_seen_rooms & current_rooms

    except asyncio.CancelledError:
        logger.info("SIP room watcher stopped")
    finally:
        await lk.aclose()


@app.on_event("startup")
async def on_startup():
    """Start the SIP room watcher on server startup."""
    global sip_watcher_task
    sip_watcher_task = asyncio.create_task(sip_room_watcher())
    logger.info(f"SIP room watcher background task created "
                f"(enabled={sip_watcher_enabled}, toggle with POST /api/sip/toggle)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8890, log_level="info")
