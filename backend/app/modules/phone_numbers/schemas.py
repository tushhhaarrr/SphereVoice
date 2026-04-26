"""Ingress Conduit module — Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


ConduitStatus = Literal["active", "inactive"]


# ── Search (Substrate available vectors) ────────────────────────


class ConduitSearchManifest(BaseModel):
    """Query params for searching available ingress vectors from substrate."""

    country: str = Field("US", max_length=2, description="ISO country code")
    area_code: str | None = Field(None, max_length=10)
    contains: str | None = Field(None, max_length=20, description="Pattern to match")
    capabilities: list[str] | None = Field(None, description="voice, sms, mms")
    limit: int = Field(10, ge=1, le=30)


class AvailableVector(BaseModel):
    """A single available signal vector from the substrate."""

    ingress_vector: str
    country_code: str
    capabilities: dict[str, bool] = Field(default_factory=dict)
    subscription_benchmark: Decimal
    substrate_provider: str = "twilio"


class ConduitSearchResponse(BaseModel):
    """Response from searching available ingress vectors."""

    vectors: list[AvailableVector]


# ── Provisioning ───────────────────────────────────────────────


class ConduitProvisionRequest(BaseModel):
    """POST /api/v1/conduits/provision — provision a new ingress vector."""

    ingress_vector: str = Field(..., max_length=20)
    tenant_id: UUID | None = None
    substrate_provider: str = Field("twilio", max_length=50)


class IngressConduitManifest(BaseModel):
    """Standard ingress conduit response manifest."""

    id: UUID
    tenant_id: UUID
    ingress_vector: str
    country_code: str | None
    substrate_provider: str
    substrate_metadata_sig: str | None
    node_sig: UUID | None
    fallback_vector: str | None
    nexus_webhook_url: str | None
    capabilities: dict[str, bool]
    subscription_benchmark: Decimal | None
    is_default_egress: bool = False
    conduit_status: str
    provisioned_at: datetime
    created_at: datetime
    
    # Enriched fields
    tenant_name: str | None = None
    node_label: str | None = None

    model_config = {"from_attributes": True, "populate_by_name": True}


# ── Nodal Mapping ─────────────────────────────────────────────


class ConduitMappingRequest(BaseModel):
    """PUT /api/v1/conduits/{id}/map — map to a processing node."""

    node_sig: UUID | None = Field(
        None,
        description="Processing Node signature to map. None to unmap.",
    )


class ConduitMappingResponse(BaseModel):
    """Response after nodal mapping."""

    id: UUID
    ingress_vector: str
    node_sig: UUID | None

    model_config = {"from_attributes": True}


# ── Update Routing ────────────────────────────────────────────


class ConduitMutationRequest(BaseModel):
    """PATCH /api/v1/conduits/{id} — update routing or status."""

    fallback_vector: str | None = None
    nexus_webhook_url: str | None = None
    conduit_status: ConduitStatus | None = None


# ── Aggregation ──────────────────────────────────────────────


class ConduitArchiveList(BaseModel):
    """GET /api/v1/conduits response body."""

    conduits: list[IngressConduitManifest]
    total: int
    page: int
    limit: int


# ── Synchronisation ────────────────────────────────────────────


class ConduitSyncSnapshot(BaseModel):
    """POST /api/v1/conduits/sync/substrate response body."""

    imported_conduits: list[IngressConduitManifest]
    total_imported: int
