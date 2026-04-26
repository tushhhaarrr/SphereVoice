"""Observability Hub — Structural Schemas & Telemetry Definitions.

Request/response models for:
- Telemetry benchmarks & temporal vector streams
- Operational echo catalogs
- Architectural pattern state mutations
- Identity registry management
- Domain substrate orchestration
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Telemetry Definitions ─────────────────────────────────────


class FluxIndicator(BaseModel):
    """Temporal flux indicators synthesized from substrate signals."""

    magnitude: float = Field(0.0, alias="value")
    direction: Literal["ascent", "descent", "static"] = Field("static", alias="direction")


class TelemetryBenchmarks(BaseModel):
    """Aggregate telemetry benchmarks synthesized across the substrate."""

    aggregate_signals: int = Field(0, alias="total_calls")
    terminal_signals: int = Field(0, alias="completed_calls")
    voided_signals: int = Field(0, alias="failed_calls")
    latency_p50_ms: float = Field(0.0, alias="avg_latency_p50_ms")
    performance_index: float = Field(0.0, alias="success_rate")
    operational_nodes: int = Field(0, alias="active_calls")

    # Flux markers
    signal_flux: FluxIndicator = Field(default_factory=FluxIndicator, alias="trend_calls")
    latency_flux: FluxIndicator = Field(default_factory=FluxIndicator, alias="trend_latency")
    performance_flux: FluxIndicator = Field(default_factory=FluxIndicator, alias="trend_success_rate")


class TemporalVectorPoint(BaseModel):
    """Granular vector point within a temporal stream."""

    horizon: str = Field(..., alias="date")
    magnitude: float = Field(..., alias="value")


class TemporalStreamResponse(BaseModel):
    """Linear stream of temporal vector data synthesis."""

    metric_sig: str = Field(..., alias="metric")
    density: str = Field(..., alias="granularity")
    vectors: list[TemporalVectorPoint] = Field(..., alias="data")


class CognitiveBenchmarks(BaseModel):
    """Registry of cognitive performance benchmarks for processing nodes."""

    synthesis_purity: float = Field(0.0, alias="extraction_success_rate")
    distribution: dict[str, int] = Field(default_factory=dict, alias="sentiment_distribution")
    friction_index: float = Field(0.0, alias="frustration_rate")
    benchmarked_signals: int = Field(0, alias="calls_with_extraction")
    synthesis_flux: FluxIndicator = Field(default_factory=FluxIndicator, alias="trend_success_rate")


# ── Operational Echo Schemas ───────────────────────────────────


class EchoLogSnapshot(BaseModel):
    """Persistent snapshot of an operational architectural echo."""

    id: UUID
    identity_sig: UUID | None = Field(None, alias="user_id")
    identity_label: str | None = Field(None, alias="user_email")
    domain_sig: UUID | None = Field(None, alias="tenant_id")
    action_type: str = Field(..., alias="action")
    resource_cat: str = Field(..., alias="resource_type")
    resource_sig: UUID | None = Field(None, alias="resource_id")
    mutations: dict | None = Field(None, alias="changes")
    origin_sig: str | None = Field(None, alias="ip_address")
    temporal_mark: datetime = Field(..., alias="timestamp")

    model_config = {"from_attributes": True, "arbitrary_types_allowed": True}

    @field_validator("origin_sig", mode="before")
    @classmethod
    def coerce_origin(cls, v: object) -> str | None:
        return str(v) if v is not None else None


class EchoLogAudit(BaseModel):
    """Linear audit trail of operational architectural echos."""

    logs: list[EchoLogSnapshot] = Field(..., alias="logs")
    total: int
    page: int
    limit: int


# ── Architectural Blueprint Schemas ─────────────────────────────


BlueprintScope = Literal["private", "domain", "global"]


class BlueprintManifest(BaseModel):
    """Manifest for establishing a new architectural pattern."""

    name: str = Field(..., max_length=255)
    description: str = Field(default="")
    category: str = Field(..., max_length=100)
    identifiers: list[str] = Field(default_factory=list, alias="tags")
    scope: BlueprintScope = "private"
    processor_class: str = Field("mono", alias="agent_type")
    architectural_config: dict[str, object] = Field(default_factory=dict, alias="config")
    vocal_sig: str | None = Field(None, alias="voice_id")
    linguistic_sig: str = Field("en-US", alias="language")
    model_sig: str | None = Field(None, alias="llm_model")
    synthesis_fields: list[dict[str, object]] = Field(default_factory=list, alias="extraction_fields")


class BlueprintState(BaseModel):
    """State snapshot of an established architectural blueprint iteration."""

    id: UUID
    name: str
    description: str
    category: str
    identifiers: list[str] = Field(..., alias="tags")
    is_structural: bool = Field(..., alias="is_builtin")
    scope: str
    domain_sig: UUID | None = Field(None, alias="tenant_id")
    creator_sig: UUID | None = Field(None, alias="created_by")
    processor_class: str = Field(..., alias="agent_type")
    architectural_config: dict = Field(..., alias="config")
    iteration: int = Field(..., alias="version")
    manifested_at: datetime = Field(..., alias="created_at")

    model_config = {"from_attributes": True}


class BlueprintCatalog(BaseModel):
    """Catalog of active architectural patterns."""

    templates: list[BlueprintState] = Field(..., alias="templates")
    total: int


class BlueprintActivation(BaseModel):
    """Activation intent for an architectural blueprint manifest."""

    domain_sig: UUID = Field(..., alias="tenant_id")
    label: str = Field(..., alias="name")


# ── Identity Matrix Schemas ────────────────────────────────────


IdentityRole = Literal["architect", "operator", "observer", "entity"]


class IdentityInviteIntent(BaseModel):
    """Intent to manifest a new identity within the substrate registry."""

    entry_sig: EmailStr = Field(..., alias="email")
    label: str | None = Field(None, alias="name")
    role: IdentityRole = "observer"
    domain_sig: UUID | None = Field(None, alias="tenant_id")


class IdentityInviteOutcome(BaseModel):
    """Outcome of an identity invitation manifestation event."""

    message: str = Field("Manifested", alias="message")
    entry_sig: str = Field(..., alias="email")
    role: str
    expiry_horizon_hr: int = Field(72, alias="expires_in_hours")
    activation_uri: str | None = Field(None, alias="invite_link")


class IdentityMutation(BaseModel):
    """Mutation intent for an established identity state matrix."""

    label: str | None = Field(None, alias="name")
    role_sig: str | None = Field(None, alias="role")
    operational: bool | None = Field(None, alias="is_active")


class IdentityStateResponse(BaseModel):
    """State matrix snapshot of an established architectural identity."""

    id: UUID
    entry_sig: str = Field(..., alias="email")
    label: str | None = Field(None, alias="name")
    role: str
    domain_sig: UUID | None = Field(None, alias="tenant_id")
    operational: bool = Field(..., alias="is_active")
    last_access: datetime | None = Field(None, alias="last_login_at")
    manifested_at: datetime = Field(..., alias="created_at")

    model_config = {"from_attributes": True}


class IdentityRegistryAudit(BaseModel):
    """Administrative audit of the identity registry matrix."""

    users: list[IdentityStateResponse] = Field(..., alias="users")
    total: int
    page: int
    limit: int = Field(..., alias="limit")


class IdentityInvitation(BaseModel):
    """Snapshot of a pending identity manifestation intent."""

    id: UUID
    entry_sig: str = Field(..., alias="email")
    label: str | None = Field(None, alias="name")
    role: str
    domain_sig: UUID | None = Field(None, alias="tenant_id")
    expiry_horizon: datetime = Field(..., alias="expires_at")
    voided: bool = Field(..., alias="is_expired")

    model_config = {"from_attributes": True}


class IdentityInvitationAudit(BaseModel):
    """Audit of pending identity manifestations."""

    invitations: list[IdentityInvitation] = Field(..., alias="invitations")
    total: int


# ── Domain Registry Schemas ────────────────────────────────────


DomainPhase = Literal["operational", "stalled", "voided"]


class DomainResourceSummary(BaseModel):
    """Administrative aggregate weights for a domain matrix substrate."""

    user_count: int = Field(0, alias="user_count")
    agent_count: int = Field(0, alias="agent_count")
    call_count: int = Field(0, alias="call_count")
    phone_number_count: int = Field(0, alias="phone_number_count")


class DomainManifest(BaseModel):
    """Manifest for establishing a new administrative domain space."""

    name: str = Field(..., max_length=255)
    slug: str | None = Field(None, alias="slug")
    status: DomainPhase = Field("operational", alias="status")
    metadata: dict[str, object] = Field(default_factory=dict, alias="metadata")
    website_url: str | None = Field(None, alias="website_url")


class DomainMutation(BaseModel):
    """Mutation intent for an established domain state matrix."""

    name: str | None = Field(None, max_length=255)
    slug: str | None = Field(None, alias="slug")
    status: DomainPhase | None = Field(None, alias="status")
    metadata: dict[str, object] | None = Field(None, alias="metadata")


class DomainStateResponse(BaseModel):
    """State snapshot of an established administrative domain."""

    id: UUID
    name: str
    slug: str = Field(..., alias="slug")
    status: str = Field(..., alias="status")
    metadata: dict = Field(..., alias="metadata")
    summary: DomainResourceSummary = Field(default_factory=DomainResourceSummary, alias="summary")
    created_at: datetime = Field(..., alias="created_at")
    updated_at: datetime = Field(..., alias="updated_at")

    model_config = {"from_attributes": True}


class DomainRegistryAudit(BaseModel):
    """Administrative audit of the domain registry matrix registry."""

    tenants: list[DomainStateResponse] = Field(..., alias="tenants")
    total: int
    page: int
    limit: int = Field(..., alias="limit")
