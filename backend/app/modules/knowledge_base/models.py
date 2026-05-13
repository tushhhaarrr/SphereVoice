"""Knowledge Base module — SQLAlchemy models.

Tables:
- knowledge_bases: KB containers with retrieval settings
- kb_documents: Individual documents (file or text)
- kb_embeddings: Vector chunks for RAG retrieval (pgvector)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base

# pgvector column type
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None  # type: ignore


class KnowledgeBase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Knowledge base container for RAG documents."""

    __tablename__ = "knowledge_bases"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nexus_registry.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sharing_scope: Mapped[str] = mapped_column(
        String(20), server_default=text("'private'"), nullable=False
    )

    # Retrieval settings
    default_chunk_count: Mapped[int] = mapped_column(
        Integer, server_default=text("3"), nullable=False
    )
    default_similarity_threshold: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), server_default=text("0.7"), nullable=False
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_manifests.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'ready'"), nullable=False
    )

    # Relationships
    documents: Mapped[list["KBDocument"]] = relationship(
        "KBDocument", back_populates="knowledge_base", cascade="all, delete-orphan"
    )

    # ── FIX: REMOVED back_populates="shard" ──────────────────────────
    # This prevents the mapper crash because AgentKnowledgeBase doesn't 
    # use the attribute name 'shard'.
    associated_nodes: Mapped[list["NodeKnowledgeMatrix"]] = relationship(
        "NodeKnowledgeMatrix", cascade="all, delete-orphan"
    )
    # ──────────────────────────────────────────────────────────────────

    __table_args__ = (
        Index("idx_kb_tenant", "tenant_id"),
        Index("idx_kb_scope", "sharing_scope"),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBase(id={self.id}, name='{self.name}')>"


class KBDocument(UUIDPrimaryKeyMixin, Base):
    """Individual document in a knowledge base."""

    __tablename__ = "kb_documents"

    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )

    # Relationships
    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        "KnowledgeBase", back_populates="documents"
    )
    embeddings: Mapped[list["KBEmbedding"]] = relationship(
        "KBEmbedding", back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_kb_docs_kb", "kb_id"),)

    def __repr__(self) -> str:
        return f"<KBDocument(id={self.id}, name='{self.name}', type='{self.type}')>"


class KBEmbedding(UUIDPrimaryKeyMixin, Base):
    """Vector embedding chunk for RAG retrieval."""

    __tablename__ = "kb_embeddings"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kb_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )

    # Relationships
    document: Mapped["KBDocument"] = relationship(
        "KBDocument", back_populates="embeddings"
    )

    __table_args__ = (
        Index("idx_kb_embeddings_doc", "document_id"),
        Index("idx_kb_embeddings_kb", "kb_id"),
    )

    def __repr__(self) -> str:
        return f"<KBEmbedding(id={self.id}, doc={self.document_id}, chunk={self.chunk_index})>"