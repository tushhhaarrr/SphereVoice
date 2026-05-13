"""Knowledge Base Hub — Structural Unstructured Intelligence Ingress.

Endpoints:
- GET    /api/v1/cognitive-libraries              — Catalog libraries
- POST   /api/v1/cognitive-libraries              — Establish library
- GET    /api/v1/cognitive-libraries/{sig}        — Inspect library shards
- PUT    /api/v1/cognitive-libraries/{sig}        — Mutate library state
- DELETE /api/v1/cognitive-libraries/{sig}        — Excise library substrate
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, set_tenant_context
from app.core.exceptions import ValidationError
from app.modules.knowledge_base.retriever import search_kb as probe_cognitive_vectors
from app.modules.knowledge_base.schemas import (
    NodeLibraryActivation,
    NodeLibraryResponse,
    ShardListResponse,
    ShardResponse,
    ArtifactListResponse,
    ArtifactResponse,
    ArtifactRawInput,
    LibraryManifest,
    LibraryAuditResponse,
    LibraryStateResponse,
    LibraryAdjustment,
    VectorSearchResponse,
    VectorSearchResult,
)
from app.modules.knowledge_base.service import KnowledgeBaseOrchestrator

router = APIRouter(prefix="/knowledge-bases", tags=["KnowledgeBase"])
node_library_router = APIRouter(prefix="/agents", tags=["NodeCognition"])


@router.get("", response_model=LibraryAuditResponse)
async def catalog_cognitive_libraries(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100, alias="page_size"),
    search: str | None = Query(None),
    tenant_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
    _ctx: None = Depends(set_tenant_context),
) -> LibraryAuditResponse:
    """Catalogs all authorized cognitive libraries within the accessible domain."""
    tid = uuid.UUID(user["tenant_id"]) if user.get("tenant_id") else tenant_id
    libs, count = await KnowledgeBaseOrchestrator.list_kbs(db, page, limit, search, tid)
    return LibraryAuditResponse(
        items=[
            LibraryStateResponse(
                id=kb.id, tenant_id=kb.tenant_id, name=kb.name, description=kb.description,
                sharing_scope=kb.sharing_scope, default_chunk_count=kb.default_chunk_count,
                default_similarity_threshold=kb.default_similarity_threshold,
                artifact_count=len(kb.documents) if kb.documents else 0,
                status=kb.status, created_by=kb.created_by, created_at=kb.created_at, updated_at=kb.updated_at,
            )
            for kb in libs
        ],
        total=count, page=page, page_size=limit,
    )


@router.post("", response_model=LibraryStateResponse, status_code=201)
async def establish_knowledge_base(
    body: LibraryManifest,
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
    _ctx: None = Depends(set_tenant_context),
) -> LibraryStateResponse:
    """Establishes a new cognitive library substrate."""
    tid = body.tenant_id or (uuid.UUID(user["tenant_id"]) if user.get("tenant_id") else None)
    kb = await KnowledgeBaseOrchestrator.create_kb(
        db=db, name=body.name, description=body.description, tenant_id=tid,
        sharing_scope=body.sharing_scope, default_chunk_count=body.default_chunk_count,
        default_similarity_threshold=float(body.default_similarity_threshold),
        created_by=uuid.UUID(user["sub"]),
    )
    await db.commit()
    return LibraryStateResponse(
        id=kb.id, tenant_id=kb.tenant_id, name=kb.name, description=kb.description,
        sharing_scope=kb.sharing_scope, default_chunk_count=kb.default_chunk_count,
        default_similarity_threshold=kb.default_similarity_threshold,
        artifact_count=0, status=kb.status, created_by=kb.created_by,
        created_at=kb.created_at, updated_at=kb.updated_at,
    )


@router.get("/{sig}", response_model=LibraryStateResponse)
async def inspect_knowledge_base(
    sig: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    _ctx: None = Depends(set_tenant_context),
) -> LibraryStateResponse:
    """Performs a structural inspection of a cognitive library."""
    kb = await KnowledgeBaseOrchestrator.get_kb(db, sig)
    return LibraryStateResponse(
        id=kb.id, tenant_id=kb.tenant_id, name=kb.name, description=kb.description,
        sharing_scope=kb.sharing_scope, default_chunk_count=kb.default_chunk_count,
        default_similarity_threshold=kb.default_similarity_threshold,
        artifact_count=len(kb.documents) if kb.documents else 0,
        status=kb.status, created_by=kb.created_by, created_at=kb.created_at, updated_at=kb.updated_at,
    )


@router.put("/{sig}", response_model=LibraryStateResponse)
async def mutate_knowledge_base(
    sig: uuid.UUID,
    body: LibraryAdjustment,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    _ctx: None = Depends(set_tenant_context),
) -> LibraryStateResponse:
    """Applies structural mutations to a cognitive library state."""
    await KnowledgeBaseOrchestrator.update_kb(db, sig, **body.model_dump(exclude_unset=True))
    await db.commit()
    kb = await KnowledgeBaseOrchestrator.get_kb(db, sig)
    return LibraryStateResponse(
        id=kb.id, tenant_id=kb.tenant_id, name=kb.name, description=kb.description,
        sharing_scope=kb.sharing_scope, default_chunk_count=kb.default_chunk_count,
        default_similarity_threshold=kb.default_similarity_threshold,
        artifact_count=len(kb.documents) if kb.documents else 0,
        status=kb.status, created_by=kb.created_by, created_at=kb.created_at, updated_at=kb.updated_at,
    )


@router.delete("/{sig}", status_code=204)
async def excise_knowledge_base(
    sig: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    _ctx: None = Depends(set_tenant_context),
) -> Response:
    """Excises a cognitive library and its vector indices from the substrate."""
    await KnowledgeBaseOrchestrator.delete_kb(db, sig)
    await db.commit()
    return Response(status_code=204)


# ── Artifact Ingress & Vector Synthesis ────────────────────────────


@router.post("/{sig}/documents", response_model=ArtifactResponse, status_code=201)
async def ingest_unstructured_shards(
    sig: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    _ctx: None = Depends(set_tenant_context),
) -> ArtifactResponse:
    """Ingests unstructured artifacts for cognitive synthesis."""
    if not file.filename: raise ValidationError("Void artifact descriptor")
    data = await file.read()
    if len(data) > 100 * 1024 * 1024: raise ValidationError("Artifact payload exceeds threshold")

    doc = await KnowledgeBaseOrchestrator.upload_document(db=db, kb_id=sig, filename=file.filename, file_data=data)
    await db.commit()

    from app.workers.embeddings import generate_embeddings
    generate_embeddings.delay(str(doc.id))

    return ArtifactResponse(
        id=doc.id, lib_id=doc.kb_id, label=doc.name, mime=doc.type, uri=doc.file_url,
        synthesized_at=doc.processed_at, shard_count=doc.chunk_count, state="synthesizing", created_at=doc.created_at,
    )


@router.get("/{sig}/documents", response_model=ArtifactListResponse)
async def catalog_library_artifacts(
    sig: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    _ctx: None = Depends(set_tenant_context),
) -> ArtifactListResponse:
    """Catalogs all ingested artifacts within a specific cognitive library."""
    docs = await KnowledgeBaseOrchestrator.list_documents(db, sig)
    return ArtifactListResponse(
        items=[
            ArtifactResponse(
                id=doc.id, lib_id=doc.kb_id, label=doc.name, mime=doc.type, uri=doc.file_url,
                synthesized_at=doc.processed_at, shard_count=doc.chunk_count,
                state="ready" if doc.processed_at else "pending", created_at=doc.created_at,
            )
            for doc in docs
        ],
        total=len(docs),
    )


@router.get("/{sig}/search", response_model=VectorSearchResponse)
async def probe_library_vectors(
    sig: uuid.UUID,
    q: str = Query(..., min_length=1, max_length=1000),
    limit: int = Query(5, ge=1, le=20),
    threshold: float = Query(0.25, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    _ctx: None = Depends(set_tenant_context),
) -> VectorSearchResponse:
    """Probes the cognitive library for structural vector similarity."""
    await KnowledgeBaseOrchestrator.get_kb(db, sig)
    hits = await probe_cognitive_vectors(db, sig, q, limit=limit, threshold=threshold)
    return VectorSearchResponse(
        results=[
            VectorSearchResult(shard_text=h.chunk_text, similarity=h.similarity, source_label=h.document_name, artifact_id=h.document_id)
            for h in hits
        ],
        probe=q, lib_id=sig,
    )


# ── Structural Node Cognition Linking ──────────────────────────────


@node_library_router.post("/{node_sig}/knowledge-bases", response_model=NodeLibraryResponse, status_code=201)
async def link_library_to_node(
    node_sig: uuid.UUID,
    body: NodeLibraryActivation,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    _ctx: None = Depends(set_tenant_context),
) -> NodeLibraryResponse:
    """Links a recursive cognitive library to a structural processing node."""
    await KnowledgeBaseOrchestrator.attach_kb_to_agent(
        db=db, agent_id=node_sig, kb_id=body.lib_id, chunk_count=body.shard_density,
        similarity_threshold=float(body.activation_threshold) if body.activation_threshold is not None else None,
    )
    await db.commit()
    kb = await KnowledgeBaseOrchestrator.get_kb(db, body.lib_id)

    from app.modules.agents.models import ProcessorLibraryLink
    from sqlalchemy import select
    res = await db.execute(select(ProcessorLibraryLink).where(ProcessorLibraryLink.processor_id == node_sig, ProcessorLibraryLink.library_id == body.lib_id))
    link = res.scalar_one()

    return NodeLibraryResponse(
        node_id=node_sig, lib_id=body.lib_id, lib_label=kb.name, shard_density=link.granularity_limit,
        activation_threshold=link.relevance_threshold, created_at=link.established_at,
    )


@node_library_router.get("/{node_sig}/knowledge-bases", response_model=list[NodeLibraryResponse])
async def list_node_cognitive_libraries(
    node_sig: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    _ctx: None = Depends(set_tenant_context),
) -> list[NodeLibraryResponse]:
    """Lists all cognitive libraries associated with a specific structural node."""
    rows = await KnowledgeBaseOrchestrator.list_agent_kbs(db, node_sig)
    return [
        NodeLibraryResponse(
            node_id=r["agent_id"], lib_id=r["kb_id"], lib_label=r["kb_name"],
            shard_density=r["chunk_count"], activation_threshold=r["similarity_threshold"],
            created_at=r["created_at"],
        )
        for r in rows
    ]
