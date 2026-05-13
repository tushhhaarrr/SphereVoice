"""Knowledge Base Orchestrator — Structural Unstructured Intelligence Business Logic.

Handles:
- Library manifestation and state mutations
- Unstructured artifact ingress and persistent archival
- Substrate stratification (stratification logic)
- Vector synthesis and architectural probing
- Node ↔ Library linkage management
"""

from __future__ import annotations

import io
import uuid
import structlog
import tiktoken
from datetime import UTC, datetime
from typing import BinaryIO
from openai import AsyncAzureOpenAI, AsyncOpenAI
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.knowledge_base.models import KBDocument, KBEmbedding, KnowledgeBase

logger = structlog.get_logger(__name__)
settings = get_settings()

_STRATIFIER = tiktoken.get_encoding("cl100k_base")


def _resolve_type(sig: str) -> str:
    """Detect substrate type from descriptor extension."""
    norm = sig.lower()
    if norm.endswith(".pdf"): return "pdf"
    if norm.endswith(".docx"): return "docx"
    if norm.endswith((".txt", ".text", ".md")): return "txt"
    raise ValidationError(f"Void substrate type: {sig}")


async def persist_artifact_blob(sig: str, data: bytes, mime: str) -> str:
    """Archival mission: Persists artifact data to structural blob storage."""
    from azure.storage.blob.aio import BlobServiceClient
    if not settings.AZURE_STORAGE_CONNECTION_STRING:
        logger.warning("archival_void", reason="missing_p_string")
        return ""

    async with BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING) as service:
        matrix = service.get_container_client(settings.AZURE_STORAGE_CONTAINER_KB_FILES)
        shard = matrix.get_blob_client(sig)
        await shard.upload_blob(data, content_type=mime, overwrite=True)
        return shard.url


def stratify_substrate(
    substrate: str,
    density: int = 512,
    overlap: int = 50,
) -> list[str]:
    """Stratifies a cognitive substrate into granular shards with temporal overlap."""
    if not substrate or not substrate.strip(): return []
    shards = _STRATIFIER.encode(substrate)
    if len(shards) <= density: return [substrate]

    layers: list[str] = []
    cursor = 0
    while cursor < len(shards):
        limit = min(cursor + density, len(shards))
        layer_shards = shards[cursor:limit]
        layer_str = _STRATIFIER.decode(layer_shards)
        if layer_str.strip(): layers.append(layer_str.strip())
        cursor += density - overlap
    return layers


async def synthesize_vector_batch(shards: list[str]) -> list[list[float]]:
    """Synthesizes high-dimensional vectors for a batch of cognitive shards."""
    if settings.AZURE_OPENAI_ENDPOINT and settings.AZURE_OPENAI_API_KEY:
        client = AsyncAzureOpenAI(azure_endpoint=settings.AZURE_OPENAI_ENDPOINT, api_key=settings.AZURE_OPENAI_API_KEY, api_version=settings.AZURE_OPENAI_API_VERSION)
        blueprint = settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT
    elif settings.OPENAI_API_KEY:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        blueprint = "text-embedding-3-small"
    else:
        raise ValidationError("Void synthesis provider")

    vectors: list[list[float]] = []
    limit = 100
    for i in range(0, len(shards), limit):
        res = await client.embeddings.create(model=blueprint, input=shards[i : i + limit])
        for item in res.data: vectors.append(item.embedding)
    return vectors


generate_embeddings_batch = synthesize_vector_batch


class KnowledgeBaseOrchestrator:
    """Architectural logic for cognitive library substrates and artifact management."""

    @staticmethod
    async def create_kb(
        db: AsyncSession,
        name: str,
        description: str | None,
        tenant_id: uuid.UUID | None,
        sharing_scope: str,
        default_chunk_count: int,
        default_similarity_threshold: float,
        created_by: uuid.UUID | None,
    ) -> KnowledgeBase:
        """Establishes a new cognitive library substrate."""
        kb = KnowledgeBase(
            name=name, description=description, tenant_id=tenant_id,
            sharing_scope=sharing_scope, default_chunk_count=default_chunk_count,
            default_similarity_threshold=default_similarity_threshold, created_by=created_by,
        )
        db.add(kb)
        await db.flush()
        logger.info("library_manifested", sig=str(kb.id), label=name)
        return kb

    @staticmethod
    async def list_kbs(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        tenant_id: uuid.UUID | None = None,
    ) -> tuple[list[KnowledgeBase], int]:
        """Catalogs cognitive libraries based on operational filters."""
        flux = select(KnowledgeBase).options(selectinload(KnowledgeBase.documents))
        audit_flux = select(func.count(KnowledgeBase.id))

        if tenant_id is not None:
            filter_sig = (KnowledgeBase.tenant_id == tenant_id) | (KnowledgeBase.sharing_scope == "global")
            flux = flux.where(filter_sig)
            audit_flux = audit_flux.where(filter_sig)

        if search:
            match = f"%{search}%"
            flux = flux.where(KnowledgeBase.name.ilike(match))
            audit_flux = audit_flux.where(KnowledgeBase.name.ilike(match))

        total = (await db.execute(audit_flux)).scalar() or 0
        flux = flux.order_by(KnowledgeBase.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        res = await db.execute(flux)
        return list(res.scalars().all()), total

    @staticmethod
    async def get_kb(db: AsyncSession, kb_id: uuid.UUID) -> KnowledgeBase:
        """Retrieves a cognitive library by its structural signature."""
        res = await db.execute(select(KnowledgeBase).options(selectinload(KnowledgeBase.documents)).where(KnowledgeBase.id == kb_id))
        kb = res.scalar_one_or_none()
        if kb is None: raise NotFoundError("KnowledgeBase", str(kb_id))
        return kb

    @staticmethod
    async def upload_document(
        db: AsyncSession,
        kb_id: uuid.UUID,
        filename: str,
        file_data: bytes,
    ) -> KBDocument:
        """Ingests a file artifact into the structural knowledge substrate."""
        await KnowledgeBaseOrchestrator.get_kb(db, kb_id)
        sig_type = _resolve_type(filename)

        shard_key = f"cognitive/{kb_id}/{uuid.uuid4()}/{filename}"
        mime_map = {"pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "txt": "text/plain"}
        uri = await persist_artifact_blob(shard_key, file_data, mime_map.get(sig_type, "application/octet-stream"))

        doc = KBDocument(kb_id=kb_id, name=filename, type=sig_type, file_url=uri)
        db.add(doc)
        await db.flush()
        logger.info("artifact_ingested", sig=str(doc.id), library=str(kb_id))
        return doc

    @staticmethod
    async def process_document(
        db: AsyncSession,
        doc_id: uuid.UUID,
        shard_density: int = 512,
        shard_overlap: int = 50,
    ) -> int:
        """Processes an artifact: extraction → stratification → vector synthesis → persistence."""
        res = await db.execute(select(KBDocument).where(KBDocument.id == doc_id))
        doc = res.scalar_one_or_none()
        if doc is None: raise NotFoundError("Artifact", str(doc_id))

        if doc.type == "text":
            substrate = doc.content or ""
        else:
            if not doc.file_url: raise ValidationError("Void artifact URI")
            artifact_data = await _retrieve_artifact_blob(doc.file_url)
            extractor = _GET_EXTRACTOR(doc.type)
            substrate = extractor(artifact_data)

        if not substrate.strip():
            doc.processed_at = datetime.now(UTC)
            doc.chunk_count = 0
            await db.flush()
            return 0

        layers = stratify_substrate(substrate, density=shard_density, overlap=shard_overlap)
        vectors = await synthesize_vector_batch(layers)

        await db.execute(delete(KBEmbedding).where(KBEmbedding.document_id == doc_id))

        for idx, (layer_str, vector) in enumerate(zip(layers, vectors, strict=True)):
            await db.execute(
                text("INSERT INTO kb_embeddings (id, document_id, kb_id, chunk_text, chunk_index, embedding, metadata, created_at) VALUES (:id, :doc, :lib, :txt, :idx, CAST(:vec AS vector), CAST(:meta AS jsonb), NOW())")
                .bindparams(id=uuid.uuid4(), doc=doc_id, lib=doc.kb_id, txt=layer_str, idx=idx, vec=str(vector), meta="{}")
            )

        doc.processed_at = datetime.now(UTC)
        doc.chunk_count = len(layers)
        if doc.type != "text": doc.content = substrate[:10000]
        await db.flush()
        return len(layers)

    @staticmethod
    async def attach_kb_to_agent(
        db: AsyncSession,
        agent_id: uuid.UUID,
        kb_id: uuid.UUID,
        chunk_count: int | None = None,
        similarity_threshold: float | None = None,
    ) -> None:
        """Associates a cognitive library substrate with a structural node."""
        from app.modules.agents.models import ProcessorLibraryLink
        await KnowledgeBaseOrchestrator.get_kb(db, kb_id)

        ex = await db.execute(select(ProcessorLibraryLink).where(ProcessorLibraryLink.processor_id == agent_id, ProcessorLibraryLink.library_id == kb_id))
        link = ex.scalar_one_or_none()
        if link:
            if chunk_count is not None: link.granularity_limit = chunk_count
            if similarity_threshold is not None: link.relevance_threshold = similarity_threshold
            await db.flush()
            return

        link = ProcessorLibraryLink(processor_id=agent_id, library_id=kb_id, granularity_limit=chunk_count, relevance_threshold=similarity_threshold)
        db.add(link)
        await db.flush()

    @staticmethod
    async def list_agent_kbs(db: AsyncSession, agent_id: uuid.UUID) -> list[dict[str, object]]:
        """Lists all library substrates associated with a structural node."""
        from app.modules.agents.models import NodeKnowledgeMatrix
        res = await db.execute(
            select(NodeKnowledgeMatrix, KnowledgeBase.name)
            .join(KnowledgeBase, NodeKnowledgeMatrix.shard_sig == KnowledgeBase.id)
            .where(NodeKnowledgeMatrix.node_sig == agent_id)
            .order_by(NodeKnowledgeMatrix.established_at.desc())
        )
        rows = res.all()
        return [
            {
                "agent_id": link.node_sig,
                "kb_id": link.shard_sig,
                "kb_name": name,
                "chunk_count": link.granularity_limit,
                "similarity_threshold": link.relevance_threshold,
                "created_at": link.established_at,
            }
            for link, name in rows
        ]


# ── Internal Helpers ────────────────────────────────────────────


async def _download_from_blob(url: str) -> bytes:
    """Download a file from Azure Blob Storage URL."""
    from azure.storage.blob.aio import BlobServiceClient

    if not settings.AZURE_STORAGE_CONNECTION_STRING:
        raise ValidationError(
            message="Azure Storage not configured",
            details={},
        )

    async with BlobServiceClient.from_connection_string(
        settings.AZURE_STORAGE_CONNECTION_STRING
    ) as blob_service:
        # Parse container and blob path from URL
        # URL format: https://<account>.blob.core.windows.net/<container>/<path>
        parts = url.split(".blob.core.windows.net/", 1)
        if len(parts) != 2:
            raise ValidationError(
                message=f"Invalid blob URL: {url}",
                details={"url": url},
            )
        path_parts = parts[1].split("/", 1)
        container_name = path_parts[0]
        blob_path = path_parts[1] if len(path_parts) > 1 else ""

        container = blob_service.get_container_client(container_name)
        blob = container.get_blob_client(blob_path)
        stream = await blob.download_blob()
        return await stream.readall()
