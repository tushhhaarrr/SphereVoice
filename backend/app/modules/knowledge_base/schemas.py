"""Architectural Knowledge Base — Structural Shard Schemas.

Request/response models for library manifestation, artifact ingestion, 
vector probing, and structural node activation.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


# ── Shard & Vector Structures ──────────────────────────────


class ShardResponse(BaseModel):
    """Encapsulates a granular cognitive shard with its text substrate."""

    id: uuid.UUID
    index: int = Field(..., alias="chunk_index")
    text: str = Field(..., alias="chunk_text")
    created_at: datetime

    model_config = {"from_attributes": True}


class ShardListResponse(BaseModel):
    """Aggregate collection of shards associated with an artifact."""

    items: list[ShardResponse]
    total: int
    artifact_label: str = Field(..., alias="document_name")


class VectorSearchResult(BaseModel):
    """Terminal outcome of a vector similarity probe."""

    shard_text: str = Field(..., alias="chunk_text")
    similarity: float
    source_label: str = Field(..., alias="document_name")
    artifact_id: uuid.UUID = Field(..., alias="document_id")
    metadata: dict[str, object] = Field(default_factory=dict)


class VectorSearchResponse(BaseModel):
    """Aggregation of vector probe outcomes."""

    results: list[VectorSearchResult]
    probe: str = Field(..., alias="query")
    lib_id: uuid.UUID = Field(..., alias="kb_id")


# ── Artifact Manifestations ─────────────────────────────────


class ArtifactRawInput(BaseModel):
    """Substrate for a text-based artifact manifestation."""

    label: str = Field(..., min_length=1, max_length=255, alias="name")
    substrate: str = Field(..., min_length=1, max_length=50000, alias="content")


class ArtifactResponse(BaseModel):
    """State capture of an ingested cognitive artifact."""

    id: uuid.UUID
    lib_id: uuid.UUID = Field(..., alias="kb_id")
    label: str = Field(..., alias="name")
    mime: str = Field(..., alias="type")
    uri: str | None = Field(None, alias="file_url")
    synthesized_at: datetime | None = Field(None, alias="processed_at")
    shard_count: int = Field(0, alias="chunk_count")
    state: str = Field("pending", alias="status")
    created_at: datetime

    model_config = {"from_attributes": True}


class ArtifactListResponse(BaseModel):
    """Inventory of artifacts associated with a cognitive library."""

    items: list[ArtifactResponse]
    total: int


# ── Knowledge Base Substrates ───────────────────────────


class LibraryManifest(BaseModel):
    """Intent to establish a new cognitive library substrate."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    tenant_id: uuid.UUID | None = None
    sharing_scope: Literal["private", "tenant", "global"] = "private"
    default_shard_density: int = Field(3, ge=1, le=10, alias="default_chunk_count")
    default_activation_threshold: Decimal = Field(
        Decimal("0.7"), ge=Decimal("0.0"), le=Decimal("1.0"), alias="default_similarity_threshold"
    )


class LibraryAdjustment(BaseModel):
    """Intent to mutate an existing cognitive library state."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    sharing_scope: Literal["private", "tenant", "global"] | None = None
    default_shard_density: int | None = Field(None, ge=1, le=10, alias="default_chunk_count")
    default_activation_threshold: Decimal | None = Field(
        None, ge=Decimal("0.0"), le=Decimal("1.0"), alias="default_similarity_threshold"
    )


class LibraryStateResponse(BaseModel):
    """Current state capture of a cognitive library."""

    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    name: str
    description: str | None = None
    sharing_scope: str
    default_shard_density: int = Field(..., alias="default_chunk_count")
    default_activation_threshold: Decimal = Field(..., alias="default_similarity_threshold")
    artifact_count: int = Field(0, alias="document_count")
    status: str = "ready"
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LibraryAuditResponse(BaseModel):
    """Audited collection of cognitive libraries."""

    items: list[LibraryStateResponse]
    total: int
    page: int
    page_size: int


# ── Structural Node Linkages ──────────────────────────────


class NodeLibraryActivation(BaseModel):
    """Intent to activate a library substrate for a structural node."""

    lib_id: uuid.UUID = Field(..., alias="kb_id")
    shard_density: int | None = Field(None, ge=1, le=10, alias="chunk_count")
    activation_threshold: Decimal | None = Field(
        None, ge=Decimal("0.0"), le=Decimal("1.0"), alias="similarity_threshold"
    )


class NodeLibraryResponse(BaseModel):
    """State snapshot of a node-library activation."""

    node_id: uuid.UUID = Field(..., alias="agent_id")
    lib_id: uuid.UUID = Field(..., alias="kb_id")
    lib_label: str = Field(..., alias="kb_name")
    shard_density: int | None = Field(None, alias="chunk_count")
    activation_threshold: Decimal | None = Field(None, alias="similarity_threshold")
    created_at: datetime

    model_config = {"from_attributes": True}
