"""Nodal Access Conduit — SignalStream architectural substrate schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


ConduitTemporalPreset = Literal["15m", "1h", "24h", "7d", "30d", "never"]


# ── Manifest Request ──────────────────────────────────────────


class ConduitManifestRequest(BaseModel):
    """Nodal ingress conduit manifestation parameters."""

    label: str | None = Field(None, max_length=255)
    temporal_threshold: ConduitTemporalPreset = Field("15m", alias="expiry")
    quota_ceiling: int | None = Field(None, ge=1, le=10_000, alias="max_uses")
    operational_vectors: dict[str, object] = Field(
        default_factory=dict,
        alias="dynamic_variables",
        description="Pre-set template vectors injected into the operational pipeline",
    )

    model_config = {"populate_by_name": True}


# ── Snapshot Response ─────────────────────────────────────────


class ConduitSnapshot(BaseModel):
    """Snapshot of a nodal access conduit."""

    id: UUID
    node_sig: UUID = Field(..., alias="agent_id")
    credential: str = Field(..., alias="token")
    label: str | None
    terminal_timestamp: datetime | None = Field(..., alias="expires_at")
    quota_ceiling: int | None = Field(..., alias="max_uses")
    cycle_count: int = Field(..., alias="use_count")
    active_mark: bool = Field(..., alias="is_active")
    operational_vectors: dict[str, object] = Field(default_factory=dict, alias="dynamic_variables")
    manifest_timestamp: datetime = Field(..., alias="created_at")

    model_config = {"from_attributes": True, "populate_by_name": True}


class ConduitRegistrySnapshot(BaseModel):
    """Aggregate snapshot of available nodal access conduits."""
    conduits: list[ConduitSnapshot] = Field(..., alias="links")

    model_config = {"populate_by_name": True}


# ── public ingress Resolution ──────────────────────────────────


class Integrations(BaseModel):
    """Resolved parameters for an egress conduit sequence."""

    node_sig: str = Field(..., alias="agent_id")
    node_label: str = Field(..., alias="agent_name")
    credential: str = Field(..., alias="token")
    terminal_timestamp: datetime | None = Field(..., alias="expires_at")

    model_config = {"populate_by_name": True}


class EgressConduitSyncRequest(BaseModel):
    """Initial synchronization request through an egress conduit."""

    signal_identity: str | None = Field(None, max_length=128, alias="visitor_id")

    model_config = {"populate_by_name": True}


class EgressConduitSyncSnapshot(BaseModel):
    """Synchronization credentials for substrate ingress."""

    signal_sig: str = Field(..., alias="call_id")
    credential: str = Field(..., alias="token")
    spectral_chamber: str = Field(..., alias="room_name")
    substrate_endpoint: str = Field(..., alias="livekit_url")

    model_config = {"populate_by_name": True}
