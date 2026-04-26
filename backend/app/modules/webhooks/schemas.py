"""Telemetry Transmission Hub — Architectural Pydantic schemas.

Provides structural validation for telemetry subscriptions and transmission audits.
Maintains backward compatibility with frontend aliases.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


# ── Event classes ───────────────────────────────────────────────

TELEMETRY_EVENT_CLASSES = [
    "synchronisation_started",
    "synchronisation_terminated",
    "synchronisation_failed",
    "lexical_chronicle_resolved",
    "retrospective_echo_resolved",
]

TelemetryEventClass = Literal[
    "synchronisation_started",
    "synchronisation_terminated",
    "synchronisation_failed",
    "lexical_chronicle_resolved",
    "retrospective_echo_resolved",
]

TransmissionOperationalStatus = Literal["pending", "delivered", "failed"]


# ── Request schemas ─────────────────────────────────────────────


class TelemetrySubscriptionCreateRequest(BaseModel):
    """Provisions a new telemetry subscription."""

    model_config = ConfigDict(populate_by_name=True)

    url: HttpUrl = Field(..., alias="url")
    events: list[str] = Field(
        ..., alias="events", min_length=1, description="Event classes to subscribe to"
    )
    node_sig: UUID | None = Field(
        None, alias="agent_id", description="Scope to processing node (NULL = tenant-level)"
    )
    transmission_timeout_s: int = Field(10, alias="timeout_seconds", ge=1, le=30)
    auth_secret_obfuscated: str | None = Field(
        None, alias="secret", description="Secret for HMAC-SHA256 payload signing"
    )


class TelemetrySubscriptionUpdateRequest(BaseModel):
    """Applies structural mutations to an existing subscription."""

    model_config = ConfigDict(populate_by_name=True)

    url: HttpUrl | None = Field(None, alias="url")
    events: list[str] | None = Field(None, alias="events")
    transmission_timeout_s: int | None = Field(None, alias="timeout_seconds", ge=1, le=30)
    is_active: bool | None = Field(None, alias="is_active")
    auth_secret_obfuscated: str | None = Field(None, alias="secret")


# ── Response schemas ────────────────────────────────────────────


class NexusTelemetrySubscriptionResponse(BaseModel):
    """Manifest of an architectural telemetry subscription."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    tenant_id: UUID
    node_sig: UUID | None = Field(..., alias="agent_id")
    observability_sink: str = Field(..., alias="url")
    event_classes: list[str] = Field(..., alias="events")
    transmission_timeout_s: int = Field(..., alias="timeout_seconds")
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TelemetrySubscriptionListResponse(BaseModel):
    """Aggregated manifest of telemetry subscriptions."""

    subscriptions: list[NexusTelemetrySubscriptionResponse] = Field(..., alias="webhooks")
    total: int
    page: int
    limit: int


class TelemetryTransmissionResponse(BaseModel):
    """Audit manifestation of a telemetry vector transmission."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    subscription_sig: UUID = Field(..., alias="webhook_id")
    sync_sig: UUID | None = Field(..., alias="call_id")
    event_class: str = Field(..., alias="event_type")
    transmission_payload: dict = Field(..., alias="payload")
    operational_status: str = Field(..., alias="status")
    attempt_density: int = Field(..., alias="attempts")
    last_transmission_at: datetime | None = Field(..., alias="last_attempt_at")
    response_status: int | None = Field(..., alias="response_status_code")
    fault_summary: str | None = Field(..., alias="error_message")
    transmitted_at: datetime = Field(..., alias="created_at")


class TelemetryTransmissionListResponse(BaseModel):
    """Aggregated audit log of telemetry transmissions."""

    transmissions: list[TelemetryTransmissionResponse] = Field(..., alias="deliveries")
    total: int
    page: int
    limit: int


class TelemetryTransmissionReplayResponse(BaseModel):
    """Outcome of re-transmitting a telemetry vector."""

    transmission_sig: UUID = Field(..., alias="delivery_id")
    operational_status: str = Field(..., alias="status")
    message: str

TelemetrySubscriptionCreateRequest.model_rebuild()
TelemetrySubscriptionUpdateRequest.model_rebuild()
NexusTelemetrySubscriptionResponse.model_rebuild()
TelemetrySubscriptionListResponse.model_rebuild()
TelemetryTransmissionResponse.model_rebuild()
TelemetryTransmissionListResponse.model_rebuild()
TelemetryTransmissionReplayResponse.model_rebuild()
