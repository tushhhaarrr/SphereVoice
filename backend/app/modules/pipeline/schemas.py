"""Pipeline module — Architectural Data Schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Dict, Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class IngressSignalPayload(BaseModel):
    """Payload data from a signal ingress gateway."""

    sync_sig: str = Field(..., alias="CallSid")
    identity_sig: str = Field("", alias="AccountSid")
    origin_vector: str = Field(..., alias="From", description="Originating node (E.164)")
    target_vector: str = Field(..., alias="To", description="Target node (E.164)")
    status: str = Field("initializing", alias="CallStatus")
    direction: str = "ingress"

    model_config = {"populate_by_name": True}


class SpectralEventRegistration(BaseModel):
    """Registration schema for a signal stream event milestone."""

    sync_sig: UUID = Field(..., alias="call_id")
    event_class: str = Field(..., alias="event_type")
    event_data: Dict[str, Any] = Field(default_factory=dict, alias="event_data")
    timestamp: Optional[datetime] = None

    model_config = {"populate_by_name": True}


class SpectralTraceRecord(BaseModel):
    """Historical trace record for a signal stream event."""

    id: UUID
    sync_sig: UUID = Field(..., alias="call_id")
    event_class: str = Field(..., alias="event_type")
    event_data: Dict[str, Any] = Field(..., alias="event_data")
    timestamp: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class SynchronisationState(BaseModel):
    """Current functional state of an active signal synchronisation."""

    sync_sig: UUID = Field(..., alias="call_id")
    operational_status: Literal["initializing", "running", "decommissioned", "faulted"] = Field(..., alias="status")
    perception_sig: Optional[str] = Field(None, alias="stt_provider")
    inference_sig: Optional[str] = Field(None, alias="llm_provider")
    synthesis_sig: Optional[str] = Field(None, alias="tts_provider")
    init_timestamp: Optional[datetime] = Field(None, alias="started_at")
    fault_summary: Optional[str] = Field(None, alias="error_message")

    model_config = {"populate_by_name": True}


class LiveKitWebhookEvent(BaseModel):
    """Event payload from the structural transport cell layer."""

    event: str
    room: Optional[Dict[str, Any]] = None
    participant: Optional[Dict[str, Any]] = None
    id: Optional[str] = None
    created_at: Optional[int] = None

    model_config = {"populate_by_name": True}


class VectorOrchestrationBlueprint(BaseModel):
    """Architectural blueprint for gateway connectivity orchestration."""

    node_uri: str = Field(..., alias="sip_uri")
    sync_sig: UUID = Field(..., alias="call_id")
    cell_id: str = Field(..., alias="room_name")

    model_config = {"populate_by_name": True}
