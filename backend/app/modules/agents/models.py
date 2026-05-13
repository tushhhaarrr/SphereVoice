"""Cognitive Node module — Architectural Agent Models.

Defines the structure for autonomous cognitive entities and their 
versioned behavioral configurations.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class CognitiveNode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The core definition of a cognitive entity (Agent)."""

    __tablename__ = "processing_nodes"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nexus_registry.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    # Relationships
    versions: Mapped[list[NodeVersion]] = relationship(
        "NodeVersion", back_populates="node", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CognitiveNode(id={self.id}, name='{self.name}')>"


class NodeVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Versioned configuration for a cognitive node's logic and personality."""

    __tablename__ = "node_state_archives"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("processing_nodes.id", ondelete="CASCADE"), index=True
    )
    version_label: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_manifest: Mapped[str] = mapped_column(Text, nullable=False)
    config_params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    is_published: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))

    # Relationships
    node: Mapped[CognitiveNode] = relationship("CognitiveNode", back_populates="versions")

    def __repr__(self) -> str:
        return f"<NodeVersion(id={self.id}, label='{self.version_label}')>"


class NodeKnowledge(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Mapping between nodes and their specific knowledge base vectors."""

    __tablename__ = "node_knowledge_matrices"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("processing_nodes.id", ondelete="CASCADE"), primary_key=True
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), primary_key=True
    )
    priority: Mapped[int] = mapped_column(server_default=text("0"))


class NodePrompt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Specific prompt templates assigned to cognitive nodes."""
    
    # Not sure if this table exists in DB, leaving as is for now unless it causes errors.
    __tablename__ = "agent_prompts"
    
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("processing_nodes.id", ondelete="CASCADE")
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class BehavioralProbe(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Monitoring and evaluation metrics for agent behavior quality."""
    
    __tablename__ = "behavioral_probes"
    
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("processing_nodes.id", ondelete="CASCADE")
    )
    probe_type: Mapped[str] = mapped_column(String(50), nullable=False)
    probe_result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=True)


# ── ALIASES FOR FULL COMPATIBILITY ──────────────────────────────────────────
# Existing Aliases
NodeKnowledgeMatrix = NodeKnowledge
Agent = CognitiveNode
AgentVersion = NodeVersion
AgentKnowledgeBase = NodeKnowledge
AgentPrompt = NodePrompt

# MISSING ALIASES CAUSING THE ERROR:
ProcessingNode = CognitiveNode
NodeStateArchive = NodeVersion  # Or your specific state model
ProbeTelemetry = BehavioralProbe
AgentBehavioralProbe = BehavioralProbe