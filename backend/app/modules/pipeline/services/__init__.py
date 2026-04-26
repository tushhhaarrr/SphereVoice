"""Pipeline services — Provider-specific Pipecat service wrappers.

Public API for the services sub-package:
- STT: create_perception_analyzer, PerceptionSignalCollector, PerceptionEngineConfiguration
- LLM: CognitiveNexusBlueprint, build_nodal_action_shards, get_cognitive_default_blueprint
- TTS: SynthesisNexusBlueprint, resolve_vocal_signature, resolve_resonance_cadence
- Recording: EgressSignalArchive, initiate_signal_archival, terminate_signal_archival, get_recording_url
- Circuit Breaker: SubstrateResilienceGuard, substrate_resilience_matrix
"""

from app.modules.pipeline.services.stt import (
    PerceptionEngineConfiguration,
    PerceptionSignalCollector,
    create_perception_analyzer,
    DEEPGRAM_FLUX,
    DEEPGRAM_NOVA_3,
)
from app.modules.pipeline.services.llm import (
    CognitiveNexusBlueprint,
    build_nodal_action_shards,
    get_cognitive_default_blueprint,
)
from app.modules.pipeline.services.tts import (
    SynthesisNexusBlueprint,
    resolve_vocal_signature,
    resolve_resonance_cadence,
)
from app.modules.pipeline.services.recording import (
    EgressSignalArchive,
    get_recording_url,
    initiate_signal_archival,
    terminate_signal_archival,
)
from app.modules.pipeline.services.circuit_breaker import (
    SubstrateResilienceGuard,
    substrate_resilience_matrix,
)

__all__ = [
    # Perception (STT/VAD)
    "PerceptionEngineConfiguration",
    "PerceptionSignalCollector",
    "create_perception_analyzer",
    "DEEPGRAM_FLUX",
    "DEEPGRAM_NOVA_3",
    # Cognition (LLM)
    "CognitiveNexusBlueprint",
    "build_nodal_action_shards",
    "get_cognitive_default_blueprint",
    # Synthesis (TTS)
    "SynthesisNexusBlueprint",
    "resolve_vocal_signature",
    "resolve_resonance_cadence",
    # Recording
    "EgressSignalArchive",
    "get_recording_url",
    "initiate_signal_archival",
    "terminate_signal_archival",
    # Substrate Stability
    "SubstrateResilienceGuard",
    "substrate_resilience_matrix",
]
