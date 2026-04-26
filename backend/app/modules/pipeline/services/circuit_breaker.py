"""Spectral Manifold Services — Substrate Resilience Guard for Nodal Failover.

Implements the resilience guard pattern for Perception/Cognitive/Synthesis vector layers.
When a nodal vector oscillates beyond threshold density within a temporal window, 
the guard depressurizes, and signal vectors are diverted to an auxiliary substrate.

States:
- NOMINAL: Structural integrity maintained, signal vectors pass through.
- DEPRESSURIZED: Nodal instability detected, all vectors diverted to auxiliary.
- REGENERATING: Testing if nodal vector has stabilized (allows a single probe).

Configuration:
- failure_threshold: 3 oscillations → depressurize guard.
- recovery_timeout: 30 seconds before attempting regeneration.
- success_threshold: 2 stable signatures in regeneration → normalize guard.
"""

from __future__ import annotations

import asyncio
import time
from enum import Enum

import structlog

runtime_logger = structlog.get_logger(__name__)


class GuardState(str, Enum):
    """Resilience guard architectural states."""

    NOMINAL = "nominal"
    DEPRESSURIZED = "depressurized"
    REGENERATING = "regenerating"


class SubstrateResilienceGuard:
    """Architectural guard for substrate reliability.

    Protects a primary nodal vector with autonomous diversion to an auxiliary fallback.
    Asynchronous and thread-safe within the manifold engine.
    """

    def __init__(
        self,
        anchor_id: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        success_threshold: int = 2,
    ) -> None:
        """Initializes the resilience guard.

        Args:
            anchor_id: Architectural identifier for the guard (e.g., "stt_deepgram", "llm_groq").
            failure_threshold: Consecutive oscillations before depressurization.
            recovery_timeout: Seconds to wait before attempting spectral regeneration.
            success_threshold: Stable signatures required during regeneration to normalize.
        """
        self.anchor_id = anchor_id
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self._state = GuardState.NOMINAL
        self._instability_count: int = 0
        self._stability_count: int = 0
        self._last_oscillation_time: float = 0.0
        self._guard_lock = asyncio.Lock()

    @property
    def state(self) -> GuardState:
        """Current architectural state of the guard."""
        return self._state

    @property
    def is_depressurized(self) -> bool:
        """Checks if the guard is depressurized (nodal instability)."""
        return self._state == GuardState.DEPRESSURIZED

    async def register_stable_signature(self) -> None:
        """Registers a stable signal signature for the nodal vector."""
        async with self._guard_lock:
            if self._state == GuardState.REGENERATING:
                self._stability_count += 1
                if self._stability_count >= self.success_threshold:
                    self._transition_to(GuardState.NOMINAL)
            elif self._state == GuardState.NOMINAL:
                self._instability_count = 0

    async def register_oscillation(self) -> None:
        """Registers a nodal oscillation (failure) for the vector layer."""
        async with self._guard_lock:
            self._last_oscillation_time = time.monotonic()

            if self._state == GuardState.REGENERATING:
                # Instability during regeneration — immediate depressurization
                self._transition_to(GuardState.DEPRESSURIZED)
            elif self._state == GuardState.NOMINAL:
                self._instability_count += 1
                if self._instability_count >= self.failure_threshold:
                    self._transition_to(GuardState.DEPRESSURIZED)

    async def should_divert_to_auxiliary(self) -> bool:
        """Checks if signal vectors should be diverted to the auxiliary substrate.

        Handles DEPRESSURIZED → REGENERATING transition upon temporal timeout.
        """
        async with self._guard_lock:
            if self._state == GuardState.NOMINAL:
                return False

            if self._state == GuardState.DEPRESSURIZED:
                elapsed = time.monotonic() - self._last_oscillation_time
                if elapsed >= self.recovery_timeout:
                    self._transition_to(GuardState.REGENERATING)
                    return False  # Allow a single probe vector to primary
                return True  # Still depressurized — divert to auxiliary
            
            # REGENERATING — allow probe vector
            return False

    def _transition_to(self, target_state: GuardState) -> None:
        """Transitions the guard to a new architectural state with telemetry."""
        origin_state = self._state
        self._state = target_state

        if target_state == GuardState.NOMINAL:
            self._instability_count = 0
            self._stability_count = 0
        elif target_state == GuardState.DEPRESSURIZED:
            self._stability_count = 0
        elif target_state == GuardState.REGENERATING:
            self._stability_count = 0

        runtime_logger.info(
            "guard_state_transition",
            anchor=self.anchor_id,
            origin=origin_state.value,
            target=target_state.value,
            instability_depth=self._instability_count,
        )

    async def normalize(self) -> None:
        """Manually normalizes the resilience guard to the NOMINAL state."""
        async with self._guard_lock:
            self._transition_to(GuardState.NOMINAL)


class SubstrateGuardRegistry:
    """Registry of resilience guards for all active substrate nodal vectors.

    One guard per nodal vector signature (e.g., "stt_deepgram", "llm_groq").
    """

    def __init__(self) -> None:
        self._guards: dict[str, SubstrateResilienceGuard] = {}
        self._registry_lock = asyncio.Lock()

    async def resolve_guard(
        self,
        node_sig: str,
        instability_threshold: int = 3,
        recovery_temporal_gate: float = 30.0,
    ) -> SubstrateResilienceGuard:
        """Resolves or initializes a resilience guard for a specific nodal vector.

        Args:
            node_sig: Unique architectural identifier.
            instability_threshold: Oscillations before depressurization.
            recovery_temporal_gate: Seconds before regeneration probe.
        """
        async with self._registry_lock:
            if node_sig not in self._guards:
                self._guards[node_sig] = SubstrateResilienceGuard(
                    anchor_id=node_sig,
                    failure_threshold=instability_threshold,
                    recovery_timeout=recovery_temporal_gate,
                )
            return self._guards[node_sig]

    async def audit_resilience_matrix(self) -> dict[str, dict[str, object]]:
        """Provides a diagnostic audit of all active resilience guards."""
        async with self._registry_lock:
            return {
                anchor: {
                    "architectural_state": guard.state.value,
                    "instability_count": guard._instability_count,
                    "is_depressurized": guard.is_depressurized,
                }
                for anchor, guard in self._guards.items()
            }

    async def normalize_substrate(self) -> None:
        """Normalizes all guards in the resilience matrix to the NOMINAL state."""
        async with self._registry_lock:
            for guard in self._guards.values():
                await guard.normalize()


# Global resilience matrix — shared across the spectral manifold substrate
substrate_resilience_matrix = SubstrateGuardRegistry()
