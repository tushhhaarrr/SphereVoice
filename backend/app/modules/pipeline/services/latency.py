"""Spectral Manifold — Real-time signal synchronisation telemetry."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
import time
from typing import Callable, Awaitable

_log = logging.getLogger(__name__)

from pipecat.frames.frames import (
    BotStartedSpeakingFrame, BotStoppedSpeakingFrame, Frame,
    InterimTranscriptionFrame, LLMFullResponseEndFrame, LLMFullResponseStartFrame,
    MetricsFrame, OutputTransportMessageFrame, TextFrame, TTSTextFrame,
    TTSStartedFrame, TranscriptionFrame, UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame, VADUserStartedSpeakingFrame, VADUserStoppedSpeakingFrame,
)
from pipecat.metrics.metrics import ProcessingMetricsData, TTFBMetricsData
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

_STAGE_LABELS = {"perception": "Perception", "inference": "Inference", "synthesis": "Synthesis"}


@dataclass
class VectorLatencyBench:
    stage: str
    label: str
    response_latency_ms: float | None = None
    processing_latency_ms: float | None = None
    ttfb_latency_ms: float | None = None
    processor: str | None = None
    model: str | None = None

    def as_payload(self) -> dict[str, object]:
        return {
            "stage": self.stage, "label": self.label,
            "response_latency_ms": _round_ms(self.response_latency_ms),
            "processing_latency_ms": _round_ms(self.processing_latency_ms),
            "ttfb_latency_ms": _round_ms(self.ttfb_latency_ms),
            "processor": self.processor, "model": self.model,
        }


@dataclass
class CycleLatencyBench:
    cycle_id: int
    started_at_monotonic: float
    perception_at_monotonic: float | None = None
    inference_started_at_monotonic: float | None = None
    synthesis_started_at_monotonic: float | None = None
    vectors: dict[str, VectorLatencyBench] = field(
        default_factory=lambda: {s: VectorLatencyBench(stage=s, label=l) for s, l in _STAGE_LABELS.items()}
    )


class SynchronisationLatencyOrchestrator:
    def __init__(self, sync_sig: str, clock: Callable[[], float], timestamp_factory: Callable[[], str]):
        self.sync_sig = sync_sig
        self.clock = clock
        self.timestamp_factory = timestamp_factory
        self.on_direct_emit: Callable[[dict[str, object]], Awaitable[None]] | None = None
        self.cycle_counter = 0
        self.current_cycle: CycleLatencyBench | None = None
        self.current_user_entry_id: str | None = None
        self.current_node_entry_id: str | None = None
        self.current_node_text: list[str] = []

    def start_cycle(self) -> CycleLatencyBench:
        self.cycle_counter += 1
        self.current_cycle = CycleLatencyBench(cycle_id=self.cycle_counter, started_at_monotonic=self.clock())
        return self.current_cycle

    def ensure_cycle(self) -> CycleLatencyBench:
        return self.current_cycle or self.start_cycle()

    def apply_metrics(self, frame: MetricsFrame, allowed_stages: set[str]) -> bool:
        cycle = self.current_cycle
        if not cycle: return False
        updated = False
        for metric in frame.data:
            stage = detect_stage(metric.processor)
            if stage in allowed_stages:
                v = cycle.vectors[stage]
                v.processor = metric.processor.split("#", 1)[0]
                if isinstance(metric, ProcessingMetricsData): v.processing_latency_ms = metric.value * 1000
                elif isinstance(metric, TTFBMetricsData): v.ttfb_latency_ms = metric.value * 1000
                updated = True
        return updated

    def build_latency_payload(self) -> dict[str, object] | None:
        c = self.current_cycle
        if not c: return None
        return {
            "type": "latency_update", "sync_sig": self.sync_sig, "cycle_id": c.cycle_id,
            "services": {s: v.as_payload() for s, v in c.vectors.items()},
        }

    def build_user_chronicle_payload(self, frame: TranscriptionFrame | InterimTranscriptionFrame) -> dict[str, object]:
        if not self.current_user_entry_id: self.current_user_entry_id = f"user-{self.cycle_counter}"
        is_final = isinstance(frame, TranscriptionFrame)
        payload = {
            "type": "chronicle_update", "sync_sig": self.sync_sig, "originator": "user",
            "text": frame.text, "is_final": is_final, "entry_id": self.current_user_entry_id,
        }
        if is_final: self.current_user_entry_id = None
        return payload

    def build_node_partial_payload(self, frame: TextFrame) -> dict[str, object]:
        if not self.current_node_entry_id: self.current_node_entry_id = f"node-{self.cycle_counter}"
        self.current_node_text.append(frame.text)
        return {
            "type": "chronicle_update", "sync_sig": self.sync_sig, "originator": "node",
            "text": "".join(self.current_node_text), "is_final": False, "entry_id": self.current_node_entry_id,
        }


def _round_ms(v: float | None) -> float | None:
    return round(v, 1) if v is not None else None


def detect_stage(p_name: str | None) -> str | None:
    if not p_name: return None
    n = p_name.lower()
    if any(t in n for t in ("stt", "deepgram", "assemblyai")): return "perception"
    if any(t in n for t in ("llm", "openai", "groq", "anthropic")): return "inference"
    if any(t in n for t in ("tts", "elevenlabs", "cartesia", "azuretts")): return "synthesis"
    return None