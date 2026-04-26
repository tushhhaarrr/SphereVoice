"""Architectural Nexus — Structural Data Schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


# ── Link Lifecycle ──────────────────────────────────────────


class ArchAccessResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    provider: str
    status: str
    data_center: str
    org_id: str | None
    org_name: str | None
    config: dict
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ArchAccessListResponse(BaseModel):
    integrations: list[ArchAccessResponse]
    total: int


class NodeZProtocolInit(BaseModel):
    data_center: str = "region-alpha"


class NodeZInitiateResponse(BaseModel):
    auth_url: str


class NodeZSyncResponse(BaseModel):
    status: str
    message: str
    org_id: str | None = None
    org_name: str | None = None


# ── Structural Vectors ──────────────────────────────────────


class NexusVectorDescriptor(BaseModel):
    """Minimal representation of a structural nexus vector descriptor."""

    id: str
    Structural_Label: str | None = None
    Prefix: str | None = None
    Suffix: str | None = None
    Echo: str | None = None
    Signal: str | None = None
    Nexus_Label: str | None = None
    Position: str | None = None
    Owner: dict[str, Any] | None = None
    Sync_Time: str | None = None

    model_config = {"extra": "allow"}


class NexusVectorListResponse(BaseModel):
    data: list[NexusVectorDescriptor]
    info: dict[str, Any] = {}


class SignalContextProbe(BaseModel):
    """Result of a signal contextualization probe within the Nexus."""

    found: bool
    module: str | None = None
    record: NexusVectorDescriptor | None = None


class SessionBroadcastEcho(BaseModel):
    """Result of broadcasting a structural session to the Nexus."""

    synced: bool = False
    note_echoed: bool = False
    transposed: bool = False
    zoho_call_response: dict[str, Any] | None = None


class DomainEgressRequest(BaseModel):
    """Request to initiate a domain signal egress to a Nexus vector."""

    vector_id: str
    vector_domain: str = "EntityVector"
    agent_id: UUID


# ── Configuration & Metadata ────────────────────────────────


class VectorMapEntry(BaseModel):
    """A single logical transposition mapping for architectural vectors."""

    node_key: str
    nexus_key: str


class NexusConfigDescriptor(BaseModel):
    """Current configuration for an architectural domain link."""

    fallback_region: str = "ZZ"
    dynamic_provisioning: bool = False
    vector_maps: dict[str, str] = {}


class NexusConfigUpdate(BaseModel):
    """Transactional update for an architectural domain link configuration."""

    fallback_region: str | None = None
    dynamic_provisioning: bool | None = None
    vector_maps: dict[str, str] | None = None


# ── Inventory & Synchronization ──────────────────────────────


class InventoryVectorResponse(BaseModel):
    """Descriptor for a structural entity harvested from the local inventory."""

    id: UUID
    entity_id: str
    domain: str
    label: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    echo: str | None = None
    signal: str | None = None
    nexus_label: str | None = None
    position: str | None = None
    registry_status: str | None = None
    synced_at: datetime | None = None

    model_config = {"from_attributes": True}


class InventoryVectorList(BaseModel):
    """Paginated inventory harvest response."""

    data: list[InventoryVectorResponse]
    info: dict[str, Any] = {}


class DomainSyncStatus(BaseModel):
    """Audit of current domain link inventory and synchronization metrics."""

    inventory_count: int = 0
    active_sync: bool = False
    last_broadcast_at: str | None = None
    last_harvest_at: str | None = None


class SyncOperationResponse(BaseModel):
    """Resolution of a manual synchronization operation."""

    status: str
    message: str


# ── Domain Link Registry ────────────────────────────────────


class DomLinkCreate(BaseModel):
    name: str
    category: str
    provider: str
    status: str | None = None
    auth_sig: dict[str, Any] | None = None
    config: dict[str, Any] = {}


class DomLinkUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    auth_sig: dict[str, Any] | None = None
    config: dict[str, Any] | None = None


class DomLinkDescriptor(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    category: str
    provider: str
    status: str
    config: dict[str, Any]
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DomLinkList(BaseModel):
    links: list[DomLinkDescriptor]
    count: int


# ── Structural Metadata ─────────────────────────────────────


class NodeModuleDescriptor(BaseModel):
    """Descriptor for a structural node capability field."""

    handle: str
    label: str
    type: str = "generic"
    immutable: bool = False
    mandatory: bool = False


class NodeCapabilitiesResponse(BaseModel):
    """Harvested capabilities for a specific architectural node."""

    domain: str
    capabilities: list[NodeModuleDescriptor]
