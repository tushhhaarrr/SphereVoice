"""Perception (STT) service substrate for the SignalStream manifold."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable, NamedTuple

import structlog

logger = structlog.get_logger(__name__)


class PerceptionEngineConfiguration(NamedTuple):
    """Configuration blueprint for a perception (STT) engine vector."""

    provider: str
    model: str
    language: str | None = None
    smart_format: bool = True
    interim_results: bool = True
    endpointing: int | None = None
    description: str = ""


# ── Perception Provider Presets ────────────────────────────────

DEEPGRAM_NOVA_2 = PerceptionEngineConfiguration(
    provider="deepgram",
    model="nova-2",
    language="en-US",
    description="Deepgram Nova-2 — balanced speed/accuracy",
)

DEEPGRAM_NOVA_3 = PerceptionEngineConfiguration(
    provider="deepgram",
    model="nova-3",
    language="en-US",
    description="Deepgram Nova-3 — latest low-latency vector",
)

DEEPGRAM_FLUX = PerceptionEngineConfiguration(
    provider="deepgram",
    model="flux",
    language="en-US",
    description="Deepgram Flux — highest lexical accuracy",
)


class PerceptionSignalCollector:
    """Collects perception events for lexical chronicle persistence."""

    def __init__(self, sync_sig: str) -> None:
        self.sync_sig = sync_sig
        self.ingress_partials: list[dict[str, object]] = []
        self.lexical_finalisations: list[dict[str, object]] = []
        self.on_activity: Callable[[], None] | None = None

    def on_ingress_partial(self, text: str, confidence: float | None = None) -> None:
        self.ingress_partials.append({"text": text, "confidence": confidence})

    def on_ingress_final(self, text: str, confidence: float | None = None) -> None:
        self.lexical_finalisations.append({
            "text": text, "confidence": confidence, "originator": "user",
            "timestamp": datetime.now(UTC).isoformat(),
        })
        if self.on_activity: self.on_activity()

    def on_egress_signal_quiescence(self, text: str) -> None:
        if not text or not text.strip(): return
        self.lexical_finalisations.append({
            "text": text.strip(), "originator": "node",
            "timestamp": datetime.now(UTC).isoformat(),
        })
        if self.on_activity: self.on_activity()

    def get_chronicle(self) -> list[dict[str, object]]:
        return self.lexical_finalisations


def create_perception_analyzer(
    stop_secs: float = 0.15,
    start_secs: float = 0.15,
    min_volume: float = 0.5,
    confidence: float = 0.7,
) -> object:
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.audio.vad.vad_analyzer import VADParams

    return SileroVADAnalyzer(
        params=VADParams(stop_secs=stop_secs, start_secs=start_secs, min_volume=min_volume, confidence=confidence)
    )
