from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

# ── Authority & Dimensional Logic ─────────────────────────────

CognitiveNodeClass = Literal["structural_flow", "monolith_nexus", "conversation_flow", "single_prompt"]
OperationalPhase = Literal["draft", "published", "archived"]


class NodeActivationOutcome(BaseModel):
    sig: UUID
    phase: str
    iteration: int
    temporal_mark: datetime


class NodeClusteredRegistry(BaseModel):
    nodes: list[NodeStateSnapshot] = Field(..., alias="agents", serialization_alias="agents")
    total_count: int = Field(..., alias="total", serialization_alias="total")
    cursor_position: int = Field(..., alias="page", serialization_alias="page")
    limit_bound: int = Field(..., alias="limit", serialization_alias="limit")

    model_config = ConfigDict(populate_by_name=True)


class NodeArchitecturalAdjustment(BaseModel):
    label: str | None = Field(None, alias="node_label")
    node_phase: OperationalPhase | None = None
    architectural_blueprint: dict[str, object] | None = Field(None, alias="architecture")
    # ... other fields as needed ...
    model_config = ConfigDict(populate_by_name=True)


class RevisionReversionIntent(BaseModel):
    revision: int


class VectorMappingSnapshot(BaseModel):
    agent_id: UUID
    kb_id: UUID
    kb_name: str
    chunk_count: int | None
    similarity_threshold: Decimal | None
    created_at: datetime


class VectorMappingConfiguration(BaseModel):
    kb_id: UUID
    chunk_count: int = Field(5, ge=1, le=20)
    similarity_threshold: Decimal = Field(Decimal("0.75"), ge=0, le=1)


class StructuralViolation(BaseModel):
    block_sig: str
    logic_code: str
    narrative: str


class ArchitecturalAuditResult(BaseModel):
    is_integral: bool
    violations: list[StructuralViolation]
    alerts: list[StructuralViolation]
    block_density: int
    vector_density: int


class BehavioralProbeDefinition(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)
    narrative: str | None = None
    injected_parameters: dict[str, object] = Field(default_factory=dict)
    benchmark_metrics: dict[str, object] = Field(default_factory=dict)


class ProbeTelemetryChronicle(BaseModel):
    telemetry: list[ProbeTelemetrySnapshot]
    total_count: int


class SyntheticManifestationIntent(BaseModel):
    intent_narrative: str
    target_locale: str = "en-US"
    acoustic_profile: Literal["masculine", "feminine"] = "feminine"
    flow_vector: Literal["inbound", "outbound"] = "inbound"
    context_bridge: str | None = None
    domain_fields: list[str] = Field(default_factory=list)


class SyntheticBlueprintResult(BaseModel):
    label: str
    internal_logic: str
    initial_signal: str
    suggested_vectors: list[str]

# ── State Snapshots & Outcomes ──────────────────────────────


class NodeStateSnapshot(BaseModel):
    """Encapsulates the current granular state matrix of a processing node."""

    id: UUID
    domain_sig: UUID = Field(..., alias="tenant_id", serialization_alias="tenant_id")
    label: str = Field(..., alias="node_label", serialization_alias="name")
    node_class: str = Field(..., alias="node_class", serialization_alias="type")
    node_phase: str = Field(..., alias="node_phase", serialization_alias="status")
    vector_direction: str = Field(..., alias="vector_direction", serialization_alias="call_direction")
    ingress_transcription_sig: UUID | None = Field(None, serialization_alias="stt_provider_id")
    inference_matrix_sig: UUID | None = Field(None, serialization_alias="llm_provider_id")
    egress_synthesis_sig: UUID | None = Field(None, serialization_alias="tts_provider_id")
    transport_nexus_sig: UUID | None = Field(None, serialization_alias="telephony_provider_id")
    architectural_blueprint: dict[str, object] = Field(..., serialization_alias="config")
    locale_sig: str = Field(..., alias="locale_sig", serialization_alias="language")
    vocal_spectral_sig: str | None = Field(None, serialization_alias="voice_id")
    transmission_velocity: Decimal = Field(..., alias="transmission_velocity", serialization_alias="voice_speed")
    transmission_amplitude: Decimal = Field(..., alias="transmission_amplitude", serialization_alias="voice_volume")
    inference_model_sig: str | None = Field(None, serialization_alias="llm_model")
    stochastic_coefficient: Decimal = Field(..., alias="stochastic_coefficient", serialization_alias="llm_temperature")
    quantum_ceiling: int = Field(..., serialization_alias="llm_max_tokens")
    temporal_ceiling: int = Field(..., serialization_alias="max_call_duration_seconds")
    silence_threshold: int = Field(..., serialization_alias="end_on_silence_seconds")
    alert_horizon: int = Field(..., serialization_alias="ring_duration_seconds")
    fallback_logic: str = Field(..., serialization_alias="voicemail_detection")
    synthesis_logic: list[dict[str, object]] = Field(..., serialization_alias="extraction_fields")
    observability_sink: str | None = Field(None, serialization_alias="webhook_url")
    telemetry_events: list[str] = Field(..., serialization_alias="webhook_events")
    revision: int = Field(..., serialization_alias="version")
    activation_mark: datetime | None = Field(None, serialization_alias="published_at")
    creator_sig: UUID | None = Field(None, serialization_alias="created_by")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class NodeManifestDefinition(BaseModel):
    """Encapsulates the intent to manifest a new processing node."""

    domain_sig: UUID = Field(..., alias="tenant_id")
    label: str = Field(..., min_length=1, max_length=255, alias="name")
    node_class: CognitiveNodeClass = Field(..., alias="type")
    vector_direction: Literal["inbound", "outbound"] = Field("inbound", alias="call_direction")

    ingress_transcription_sig: UUID | None = Field(None, alias="stt_provider_id")
    inference_matrix_sig: UUID | None = Field(None, alias="llm_provider_id")
    egress_synthesis_sig: UUID | None = Field(None, alias="tts_provider_id")
    transport_nexus_sig: UUID | None = Field(None, alias="telephony_provider_id")

    architectural_blueprint: dict[str, object] = Field(default_factory=dict, alias="config")
    locale_sig: str = Field("en-US", alias="language")
    vocal_spectral_sig: str | None = Field(None, alias="voice_id")
    transmission_velocity: Decimal = Field(Decimal("1.0"), alias="voice_speed")
    transmission_amplitude: Decimal = Field(Decimal("1.0"), alias="voice_volume")
    inference_model_sig: str | None = Field(None, alias="llm_model")
    stochastic_coefficient: Decimal = Field(Decimal("0.7"), alias="llm_temperature")
    temporal_ceiling: int = Field(240, ge=60, le=7200, alias="max_call_duration_seconds")
    silence_threshold: int = Field(8, ge=5, le=1800, alias="end_on_silence_seconds")
    fallback_logic: str = Field("hang_up", alias="voicemail_detection")
    observability_sink: str | None = Field(None, alias="webhook_url")
    telemetry_events: list[str] = Field(default_factory=list, alias="webhook_events")

    model_config = ConfigDict(populate_by_name=True)


class NodeChronicle(BaseModel):
    archives: list[NodeTemporalArchive]

    model_config = ConfigDict(populate_by_name=True)


class NodeTemporalArchive(BaseModel):
    id: UUID
    revision: int
    archive_timestamp: datetime
    author_sig: UUID | None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class BehavioralProbeSnapshot(BaseModel):
    id: UUID
    node_sig: UUID = Field(..., alias="agent_id")
    label: str = Field(..., alias="node_label")
    narrative: str | None = None
    injected_parameters: dict[str, object] = Field(default_factory=dict)
    benchmark_metrics: dict[str, object] = Field(default_factory=dict)
    author_sig: UUID | None = Field(None, alias="creator_sig")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ProbeTelemetrySnapshot(BaseModel):
    id: UUID
    probe_sig: UUID = Field(..., alias="scenario_id")
    sync_sig: UUID | None = Field(None, alias="call_id")
    node_revision: int | None = Field(None, alias="agent_version")
    captured_matrix: dict[str, object]
    performance_metrics: dict[str, object]
    evaluation_logic: dict[str, object]
    is_terminal_success: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
