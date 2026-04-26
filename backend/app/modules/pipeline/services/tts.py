"""Pipeline services — Synthesis (TTS) service wrappers for Pipecat.

Provides configuration blueprints, vocal presets, and resonance output settings 
for all supported synthesis vectors:
- Cartesia (Sonic-3) — lowest TTFB (~60ms), recommended
- ElevenLabs (Turbo v2.5) — highest quality (~100ms TTFB)
- Azure Speech — enterprise, multi-language

Tech PRD §7.3 — NodalProviderFactory maps manifold config → Pipecat synthesis services.
"""

from __future__ import annotations

from typing import NamedTuple

import structlog

logger = structlog.get_logger(__name__)


class SynthesisNexusBlueprint(NamedTuple):
    """Configuration blueprint for a synthesis (vocalization) vector."""

    provider: str
    model: str
    default_vocal_sig: str
    sample_rate: int
    description: str


# ── Synthesis Provider Presets ────────────────────────────────


# Cartesia — Lowest TTFB (~60ms P50)
CARTESIA_SONIC3 = SynthesisNexusBlueprint(
    provider="cartesia",
    model="sonic-3",
    default_vocal_sig="79a125e8-cd45-4c13-8a67-188112f4dd22",
    sample_rate=16000,
    description="Cartesia Sonic-3 — lowest magnitude synchronization",
)

# ElevenLabs — Highest synthesis quality
ELEVENLABS_TURBO = SynthesisNexusBlueprint(
    provider="elevenlabs",
    model="eleven_turbo_v2_5",
    default_vocal_sig="21m00Tcm4TlvDq8ikWAM",
    sample_rate=16000,
    description="ElevenLabs Turbo v2.5 — highest quality resonance",
)

# Default blueprints per synthesis provider
DEFAULT_BLUEPRINTS: dict[str, SynthesisNexusBlueprint] = {
    "cartesia": CARTESIA_SONIC3,
    "elevenlabs": ELEVENLABS_TURBO,
}


def get_synthesis_default_blueprint(provider_name: str) -> SynthesisNexusBlueprint:
    """Get default synthesis blueprint for a provider."""
    blueprint = DEFAULT_BLUEPRINTS.get(provider_name)
    if blueprint is None:
        raise ValueError(f"Unknown synthesis provider: {provider_name}")
    return blueprint


# ── Vocal Signature Resolution ────────────────────────────────


def resolve_vocal_signature(
    node_vocal_sig: str | None,
    provider_config: dict[str, object],
    provider_name: str,
) -> str:
    """Resolve the vocal signature to use for synthesis.

    Priority:
    1. Node-level vocal_sig
    2. Provider config vocal_sig
    3. Provider default vocal_sig
    """
    if node_vocal_sig:
        return node_vocal_sig

    config_sig = provider_config.get("voice_id")
    if config_sig and isinstance(config_sig, str):
        return config_sig

    default_blueprint = DEFAULT_BLUEPRINTS.get(provider_name)
    if default_blueprint:
        return default_blueprint.default_vocal_sig

    return "default"


def resolve_resonance_cadence(node: object) -> float:
    """Resolve resonance cadence (speed) from node config. Default 1.0."""
    cadence = getattr(node, "voice_speed", None)
    if cadence is not None:
        return float(cadence)
    return 1.0


def resolve_amplitude_magnitude(node: object) -> float:
    """Resolve amplitude magnitude (volume) from node config. Default 1.0.

    Clamps to [0.1, 2.0] to prevent signal distortion or dangerous peaks.
    """
    amplitude = getattr(node, "voice_volume", None)
    if amplitude is not None:
        v = float(amplitude)
        return max(0.1, min(v, 2.0))
    return 1.0


class AmplitudeMagnitudeProcessor:
    """Pipecat FrameProcessor that applies PCM amplitude gain to synthesis audio frames.

    Inserts between synthesis service and transport output to scale the audio
    magnitude by `node.voice_volume`. 
    """

    def __init__(self, magnitude: float) -> None:
        from pipecat.processors.frame_processor import FrameProcessor

        class _MagnitudeProcessor(FrameProcessor):
            def __init__(self_inner) -> None:  # noqa: N805
                super().__init__()
                self_inner._magnitude = magnitude

            async def process_frame(self_inner, frame: object, direction: object) -> None:  # noqa: N805
                await super(_MagnitudeProcessor, self_inner).process_frame(frame, direction)
                from pipecat.frames.frames import TTSAudioRawFrame
                if isinstance(frame, TTSAudioRawFrame) and self_inner._magnitude != 1.0:
                    try:
                        import numpy as np
                        samples = np.frombuffer(frame.audio, dtype=np.int16).copy()
                        scaled = np.clip(samples.astype(np.float32) * self_inner._magnitude, -32768, 32767)
                        frame = TTSAudioRawFrame(
                            audio=scaled.astype(np.int16).tobytes(),
                            sample_rate=frame.sample_rate,
                            num_channels=frame.num_channels,
                        )
                    except Exception:
                        pass
                await self_inner.push_frame(frame, direction)

        self._processor = _MagnitudeProcessor()

    def get_processor(self) -> object:
        """Return the inner Pipecat magnitude processor instance."""
        return self._processor
