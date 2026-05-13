"""Voice Engine — SignalStream architectural substrate schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Direction = Literal["inbound", "outbound"]
CallStatus = Literal[
    "queued",
    "ringing",
    "in_progress",
    "completed",
    "failed",
    "no_answer",
    "voicemail",
    "cancelled",
]


class TranscriptTurn(BaseModel):
    """Reflects a single turn within a call transcript."""

    speaker: Literal["node", "user"]
    text: str
    timestamp: datetime | None = None
    confidence: float | None = None

    model_config = ConfigDict(populate_by_name=True)


class CallResponse(BaseModel):
    """Manifestation of a captured call record."""

    id: UUID
    tenant_id: UUID
    agent_id: UUID
    phone_number_id: UUID | None = None
    origin: str = Field(..., alias="from_number")
    destination: str = Field(..., alias="to_number")
    direction: Direction
    initiation_timestamp: datetime = Field(..., alias="started_at")
    termination_timestamp: datetime | None = Field(None, alias="ended_at")
    duration: int | None = Field(None, alias="duration_seconds")
    status: CallStatus
    disposition: str | None = Field(None, alias="disconnection_reason")
    archival_url: str | None = Field(None, alias="recording_url")
    transcript: list[TranscriptTurn] | None = None
    summary: dict[str, object] = Field(..., alias="extracted_data")
    summary_finalized_at: datetime | None = Field(None, alias="extraction_completed_at")
    avg_latency_ms: int | None = Field(None, alias="avg_transmission_delay")
    turns_count: int = Field(..., alias="vector_cycle_count")
    usage_metrics: dict[str, object] | None = Field(None, alias="utilization_matrix")
    writeback_status: str | None = Field(None, alias="downstream_sync_phase")
    created_at: datetime = Field(..., alias="inception_timestamp")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class CallListResponse(BaseModel):
    """Aggregated call records for list responses."""

    sessions: list[CallResponse]
    total: int = Field(..., alias="total_count")
    page: int = Field(..., alias="page_index")
    limit: int = Field(..., alias="limit_bound")

    model_config = ConfigDict(populate_by_name=True)


class CreateCallRequest(BaseModel):
    """Parameters for initiating an outbound call."""

    agent_id: UUID
    to_number: str = Field(..., max_length=20, alias="destination_vector")
    from_number: str = Field(..., max_length=20, alias="origin_vector")
    dynamic_variables: dict[str, object] = Field(default_factory=dict, alias="dynamic_nodal_vectors")

    model_config = ConfigDict(populate_by_name=True)


class CreateCallResponse(BaseModel):
    """Response after initiating a call."""

    call_id: UUID = Field(..., alias="sync_sig")
    status: CallStatus = Field(..., alias="operational_status")
    started_at: datetime = Field(..., alias="initiation_timestamp")

    model_config = ConfigDict(populate_by_name=True)


class CreateSimulationRequest(BaseModel):
    """Requirements for initiating a simulation (synthetic ingress)."""

    agent_id: UUID = Field(..., alias="node_sig")
    dynamic_variables: dict[str, object] = Field(default_factory=dict, alias="dynamic_nodal_vectors")
    scenario_id: UUID | None = Field(None, alias="behavioral_probe_sig")
    agent_version: int | None = Field(None, alias="node_revision")

    model_config = ConfigDict(populate_by_name=True)


class SimulationResponse(BaseModel):
    """Network coordinates and access vectors for a simulation."""

    call_id: UUID = Field(..., alias="sync_sig")
    token: str = Field(..., alias="access_token")
    room_name: str = Field(..., alias="spectral_cell_sig")
    livekit_url: str = Field(..., alias="substrate_nexus_url")

    model_config = ConfigDict(populate_by_name=True)
