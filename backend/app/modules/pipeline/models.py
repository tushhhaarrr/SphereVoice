"""Spectral Manifold Substrate — Persistence interface.

The manifold substrate does not define its own dedicated database schemas.
Synchronisation records are maintained within the signal synchronisation module 
(VoiceEngine, SynchronisationTelemetry).
Manifold state is maintained as volatile runtime vectors during active synchronisations.

This module re-exports synchronisation models for architectural alignment.
"""

from __future__ import annotations
