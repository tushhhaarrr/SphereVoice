"""Spectral Manifold Substrate — Signal Transmission Overhead Audit.

Accrues signal transmission magnitude metrics during a synchronization cycle.
Collects volumetric data across:
- Perception: Temporal duration of signal ingress
- Cognition: Lexical token density (ingress/egress)
- Synthesis: Grapheme mass of synthesized signals

At cycle quiescence, ``synthesize_overhead_manifest()`` returns a 
``TransmissionUsageManifest`` for structural overhead calculation.

The ``TransmissionOverheadObserver`` intercepts ``MetricsFrame`` signals 
to ensure atomic precision of lexical and grapheme counts across the substrate.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Dict, List, Optional, Set

import structlog

if TYPE_CHECKING:
    from app.modules.pricing.schemas import TransmissionUsageManifest

runtime_logger = structlog.get_logger(__name__)


class TransmissionOverheadAudit:
    """Accrues signal transmission magnitude metrics for a single synchronisation cycle."""

    def __init__(
        self,
        sync_sig: str,
        perception_provider: str | None = None,
        perception_model: str | None = None,
        cognitive_provider: str | None = None,
        cognitive_model: str | None = None,
        synthesis_provider: str | None = None,
        synthesis_model: str | None = None,
        substrate_provider: str | None = None,
    ) -> None:
        self.sync_sig = sync_sig
        self._lock = threading.Lock()

        # Architectural provider metadata
        self.perception_provider = perception_provider
        self.perception_model = perception_model
        self.cognitive_provider = cognitive_provider
        self.cognitive_model = cognitive_model
        self.synthesis_provider = synthesis_provider
        self.synthesis_model = synthesis_model
        self.substrate_provider = substrate_provider

        # Accrued magnitude metrics
        self._perception_duration_s: float = 0.0
        self._cognitive_ingress_tokens: int = 0
        self._cognitive_egress_tokens: int = 0
        self._synthesis_grapheme_mass: int = 0
        self._substrate_duration_s: float = 0.0

    # ── Signal Perception ────────────────────────────────────

    def record_perception_duration(self, seconds: float) -> None:
        """Accrues signal perception temporal duration (user speech)."""
        with self._lock:
            self._perception_duration_s += seconds

    # ── Cognitive Inference ──────────────────────────────────

    def record_cognitive_usage(
        self,
        ingress_tokens: int = 0,
        egress_tokens: int = 0,
        model: str | None = None,
    ) -> None:
        """Accrues cognitive lexical token density for a single inference cycle."""
        with self._lock:
            self._cognitive_ingress_tokens += ingress_tokens
            self._cognitive_egress_tokens += egress_tokens
            if model and not self.cognitive_model:
                self.cognitive_model = model

    # ── Signal Synthesis ─────────────────────────────────────

    def record_synthesis_mass(self, graphemes: int) -> None:
        """Accrues grapheme mass of synthesized signals."""
        with self._lock:
            self._synthesis_grapheme_mass += graphemes

    # ── Substrate Connectivity ───────────────────────────────

    def set_substrate_transmission_s(self, seconds: float) -> None:
        """Sets the total temporal duration of the substrate synchronization."""
        with self._lock:
            self._substrate_duration_s = seconds

    # ── Analytical Reports ───────────────────────────────────

    def synthesize_overhead_manifest(self) -> TransmissionUsageManifest:
        """Synthesizes a structural overhead manifest for cost calculation."""
        from app.modules.pricing.schemas import TransmissionUsageManifest

        with self._lock:
            return TransmissionUsageManifest(
                stt_provider=self.perception_provider,
                stt_model=self.perception_model,
                perception_duration_s=self._perception_duration_s,
                llm_provider=self.cognitive_provider,
                llm_model=self.cognitive_model,
                cognitive_ingress_tokens=self._cognitive_ingress_tokens,
                cognitive_egress_tokens=self._cognitive_egress_tokens,
                tts_provider=self.synthesis_provider,
                tts_model=self.synthesis_model,
                synthesis_character_count=self._synthesis_grapheme_mass,
                telephony_provider=self.substrate_provider,
                substrate_transmission_s=self._substrate_duration_s,
            )

    def to_dict(self) -> dict:
        """Returns the accrued magnitude matrix as a serializable dictionary."""
        report = self.synthesize_overhead_manifest()
        return {
            "perception": {
                "provider": report.stt_provider,
                "model": report.stt_model,
                "duration_seconds": round(report.perception_duration_s, 2),
            },
            "cognition": {
                "provider": report.llm_provider,
                "model": report.llm_model,
                "ingress_tokens": report.cognitive_ingress_tokens,
                "egress_tokens": report.cognitive_egress_tokens,
            },
            "synthesis": {
                "provider": report.tts_provider,
                "model": report.tts_model,
                "grapheme_mass": report.synthesis_character_count,
            },
            "substrate": {
                "provider": report.telephony_provider,
                "duration_seconds": round(report.substrate_transmission_s, 2),
            },
        }

    _BATCH_PERCEPTION_LAYERS = frozenset({"groq_whisper", "openai_whisper", "sambanova"})

    def estimate_from_chronicle(
        self,
        chronicle: List[Dict[str, object]],
        substrate_duration_s: float,
        blueprint_mass_chars: int = 500,
    ) -> None:
        """Interpolates usage magnitudes from the lexical chronicle as a fallback mechanism."""
        with self._lock:
            if self._perception_duration_s == 0:
                is_batch = self.perception_provider in self._BATCH_PERCEPTION_LAYERS
                if is_batch:
                    user_chars = 0
                    user_turns = 0
                    for entry in chronicle:
                        if entry.get("role") == "user" and entry.get("content"):
                            user_chars += len(str(entry["content"]))
                            user_turns += 1
                    # ~12 chars/sec heuristic
                    estimated_secs = user_chars / 12.0
                    self._perception_duration_s = max(
                        float(user_turns), min(estimated_secs, substrate_duration_s)
                    )
                else:
                    self._perception_duration_s = substrate_duration_s

            if self._synthesis_grapheme_mass == 0:
                total_chars = 0
                for entry in chronicle:
                    if entry.get("role") == "assistant" and entry.get("content"):
                        total_chars += len(str(entry["content"]))
                self._synthesis_grapheme_mass = total_chars

            if self._cognitive_ingress_tokens == 0 and self._cognitive_egress_tokens == 0:
                egress_chars = 0
                egress_turns = 0
                ingress_chars = blueprint_mass_chars
                context_sum = blueprint_mass_chars

                for entry in chronicle:
                    text = str(entry.get("content", ""))
                    if entry.get("role") == "assistant":
                        egress_chars += len(text)
                        egress_turns += 1
                        context_sum += len(text)
                    elif entry.get("role") == "user":
                        context_sum += len(text)

                if egress_turns > 0:
                    avg_context = (blueprint_mass_chars + context_sum) // 2
                    ingress_chars = avg_context * egress_turns

                self._cognitive_ingress_tokens = max(1, ingress_chars // 4)
                self._cognitive_egress_tokens = max(1, egress_chars // 4) if egress_chars > 0 else 0


class TransmissionOverheadObserver:
    """Substrate observer that accrues cognitive and synthesis magnitudes via real-time signals."""

    def __init__(self, audit: TransmissionOverheadAudit) -> None:
        self._audit = audit
        self._seen_signal_ids: Set[str] = set()
        self._perception_start_ts: float | None = None

    async def on_push_frame(self, data: object) -> None:
        from pipecat.frames.frames import (
            MetricsFrame,
            VADUserStartedSpeakingFrame,
            VADUserStoppedSpeakingFrame,
        )
        from pipecat.metrics.metrics import LLMUsageMetricsData, TTSUsageMetricsData

        frame = getattr(data, "frame", None)
        if frame is None:
            return

        if isinstance(frame, VADUserStartedSpeakingFrame):
            self._perception_start_ts = frame.timestamp - frame.start_secs
            return
        
        if isinstance(frame, VADUserStoppedSpeakingFrame):
            if self._perception_start_ts is not None:
                perception_end = frame.timestamp - frame.stop_secs
                duration = max(0.0, perception_end - self._perception_start_ts)
                if duration > 0:
                    self._audit.record_perception_duration(duration)
                self._perception_start_ts = None
            return

        if not isinstance(frame, MetricsFrame):
            return

        sig_id = str(frame.id)
        if sig_id in self._seen_signal_ids:
            return
        self._seen_signal_ids.add(sig_id)

        for item in frame.data:
            if isinstance(item, LLMUsageMetricsData):
                usage = item.value
                self._audit.record_cognitive_usage(
                    ingress_tokens=usage.prompt_tokens,
                    egress_tokens=usage.completion_tokens,
                )
            elif isinstance(item, TTSUsageMetricsData):
                self._audit.record_synthesis_mass(item.value)

    async def on_process_frame(self, data: object) -> None:
        pass

    async def on_pipeline_started(self) -> None:
        pass

    async def cleanup(self) -> None:
        pass
