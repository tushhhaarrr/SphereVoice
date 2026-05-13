"""Spectral Manifold Substrate — Public Architectural API.

Exports: ManifoldGovernor, NodalProviderFactory, SpectralManifold,
         TopologicalFlowEngine, create_topological_engine,
         VoiceEngineArchive, SubstrateResilienceGuard,
         TransmissionOverheadAudit, ArchivalShardRetriever,
         variable_resolver utilities
"""

from app.modules.pipeline.orchestrator import (
    ManifoldGovernor,
    sum_active_manifold_density,
    resolve_active_manifold,
)
from app.modules.pipeline.factory import NodalProviderFactory
from app.modules.pipeline.voice_pipeline import SpectralManifold
from app.modules.pipeline.flow_engine import (
    TopologicalFlowEngine,
    ManifoldExecutionContext,
    ManifoldNodeAction,
    FlowEngineResult,
    create_topological_engine,
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
from app.modules.pipeline.services.overhead_audit import (
    TransmissionOverheadAudit,
    TransmissionOverheadObserver,
)
from app.modules.pipeline.variable_resolver import (
    interpolate_nodal_vectors,
    interpolate_node_manifest,
    extract_nodal_vector_keys,
    synthesize_builtin_vector_components,
)
from app.modules.pipeline.knowledge_processor import (
    ArchivalShardRetriever,
    RetrospectiveLogicEngine,
    synthesize_initial_archival_context,
)

__all__ = [
    "ManifoldGovernor",
    "NodalProviderFactory",
    "SpectralManifold",
    "TopologicalFlowEngine",
    "ManifoldExecutionContext",
    "ManifoldNodeAction",
    "FlowEngineResult",
    "create_topological_engine",
    "sum_active_manifold_density",
    "resolve_active_manifold",
    "EgressSignalArchive",
    "get_recording_url",
    "initiate_signal_archival",
    "terminate_signal_archival",
    "SubstrateResilienceGuard",
    "substrate_resilience_matrix",
    "TransmissionOverheadAudit",
    "TransmissionOverheadObserver",
    "interpolate_nodal_vectors",
    "interpolate_node_manifest",
    "extract_nodal_vector_keys",
    "synthesize_builtin_vector_components",
    "ArchivalShardRetriever",
    "RetrospectiveLogicEngine",
    "synthesize_initial_archival_context",
]
