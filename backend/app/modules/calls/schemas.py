"""Signal Synchronisation — SignalStream architectural substrate schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TopologyDirection = Literal["inbound", "outbound"]
SynchronisationPhase = Literal[
    "queued",
    "ringing",
    "in_progress",
    "completed",
    "failed",
    "no_answer",
    "voicemail",
    "cancelled",
]


class LexicalTurnShard(BaseModel):
    """Reflects a single lexical turn within a signal vector."""

    signal_origin: Literal["node", "user"] = Field(..., alias="speaker")
    signal_payload: str = Field(..., alias="text")
    timestamp: datetime | None = Field(None, alias="timestamp")
    clarity_index: float | None = Field(None, alias="confidence")

    model_config = ConfigDict(populate_by_name=True)


class SignalSynchronisationManifest(BaseModel):
    """Manifestation of a captured signal synchronisation chronicle."""

    id: UUID
    nexus_sig: UUID = Field(..., alias="tenant_id")
    node_sig: UUID = Field(..., alias="agent_id")
    ingress_conduit_sig: UUID | None = Field(None, alias="phone_number_id")
    origin_vector: str = Field(..., alias="from_number")
    destination_vector: str = Field(..., alias="to_number")
    topology: TopologyDirection = Field(..., alias="direction")
    initiation_timestamp: datetime = Field(..., alias="started_at")
    termination_timestamp: datetime | None = Field(None, alias="ended_at")
    duration_interval: int | None = Field(None, alias="duration_seconds")
    operational_status: SynchronisationPhase = Field(..., alias="status")
    termination_logic: str | None = Field(None, alias="disconnection_reason")
    archival_url: str | None = Field(None, alias="recording_url")
    lexical_chronicle: list[LexicalTurnShard] | None = Field(None, alias="transcript")
    abstracted_manifest: dict[str, object] = Field(..., alias="extracted_data")
    abstraction_finalised_at: datetime | None = Field(None, alias="extraction_completed_at")
    transmission_delay: int | None = Field(None, alias="avg_latency_ms")
    vector_cycle_count: int = Field(..., alias="turn_count")
    utilization_matrix: dict[str, object] | None = Field(None, alias="usage_metrics")
    downstream_sync_phase: str | None = Field(None, alias="writeback_status")
    inception_timestamp: datetime = Field(..., alias="created_at")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SignalSynchronisationArchive(BaseModel):
    """Aggregated synchronisation manifests for architectural inspection."""

    synchronisations: list[SignalSynchronisationManifest] = Field(..., alias="sessions")
    total_count: int = Field(..., alias="total")
    page_index: int = Field(..., alias="page")
    limit_bound: int = Field(..., alias="limit")

    model_config = ConfigDict(populate_by_name=True)


class PropagationManifest(BaseModel):
    """Architectural parameters for initiating an external signal vector propagation."""

    node_sig: UUID = Field(..., alias="agent_id")
    destination_vector: str = Field(..., max_length=20, alias="to_number")
    origin_vector: str = Field(..., max_length=20, alias="from_number")
    dynamic_nodal_vectors: dict[str, object] = Field(default_factory=dict, alias="dynamic_variables")

    model_config = ConfigDict(populate_by_name=True)


class PropagationResolution(BaseModel):
    """Verification of a successful signal vector propagation."""

    sync_sig: UUID = Field(..., alias="call_id")
    operational_status: SynchronisationPhase = Field(..., alias="status")
    initiation_timestamp: datetime = Field(..., alias="started_at")

    model_config = ConfigDict(populate_by_name=True)


class SyntheticIngressBlueprint(BaseModel):
    """Requirements for initiating a synthetic ingress environmental stream."""

    node_sig: UUID = Field(..., alias="agent_id")
    dynamic_nodal_vectors: dict[str, object] = Field(default_factory=dict, alias="dynamic_variables")
    behavioral_probe_sig: UUID | None = Field(None, alias="scenario_id")
    node_revision: int | None = Field(None, alias="agent_version")

    model_config = ConfigDict(populate_by_name=True)


class SpectralCellCoordinates(BaseModel):
    """Network coordinates and access vectors for a synthetic architectural stream."""

    sync_sig: UUID = Field(..., alias="call_id")
    access_token: str = Field(..., alias="token")
    spectral_cell_sig: str = Field(..., alias="room_name")
    substrate_nexus_url: str = Field(..., alias="livekit_url")

    model_config = ConfigDict(populate_by_name=True)
