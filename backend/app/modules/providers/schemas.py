"""Backend Resolution module — Architectural Data Schemas.

Request/response models for signal vector provisioning, modification, and connectivity audits.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Dict, Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


VectorDomain = Literal["perception", "cognitive", "synthesis", "transport"]


# ── Response Schemas ─────────────────────────────────────────


class VectorDescriptor(BaseModel):
    """Architectural descriptor for a signal vector. Never exposes the raw access signature."""

    id: UUID
    tenant_id: Optional[UUID]
    vector_id: str = Field(..., alias="provider_name")
    vector_domain: str = Field(..., alias="provider_category")
    vector_family: str = Field("", alias="provider_family")
    vector_variant: Optional[str] = Field(None, alias="provider_variant")
    is_default: bool
    is_active: bool
    config: Dict[str, Any]
    last_validated_at: Optional[datetime] = Field(None, alias="last_tested_at")
    health_status: Optional[str] = Field(None, alias="test_status")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class VectorRegistryCatalog(BaseModel):
    """Catalog of registered signal vectors within the architectural nexus."""

    vectors: list[VectorDescriptor] = Field(..., alias="providers")
    load: int = Field(..., alias="total")

    model_config = {"populate_by_name": True}


class VectorConnectivityAudit(BaseModel):
    """Audit report for signal vector connectivity verification."""

    state: str = Field(..., alias="status")  # "synchronized" or "faulted"
    latency_ms: Optional[int] = None
    trace_message: str = Field(..., alias="message")

    model_config = {"populate_by_name": True}


# ── Request Schemas ──────────────────────────────────────────


class VectorProvisionRequest(BaseModel):
    """Request to provision a new signal vector."""

    vector_id: str = Field(..., min_length=1, max_length=100, alias="provider_name")
    vector_domain: VectorDomain = Field(..., alias="provider_category")
    auth_sig: str = Field(..., min_length=1, alias="api_key", description="Plaintext signature — obfuscated before storage")
    is_default: bool = False
    tenant_id: Optional[UUID] = None
    config: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class VectorModificationRequest(BaseModel):
    """Request to modify an existing signal vector configuration."""

    vector_id: Optional[str] = Field(None, max_length=100, alias="provider_name")
    vector_domain: Optional[VectorDomain] = Field(None, alias="provider_category")
    auth_sig: Optional[str] = Field(None, alias="api_key", description="New signature — re-obfuscated if provided")
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None

    model_config = {"populate_by_name": True}
