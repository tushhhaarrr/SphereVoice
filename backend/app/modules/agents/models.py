from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class ProbeTelemetry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Encapsulates telemetry synthesized from a behavioral probe cycle."""

    __tablename__ = "probe_telemetry"

    probe_sig: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("behavioral_probes.id", ondelete="CASCADE"),
        nullable=False,
    )
    sync_sig: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("signal_synchronisations.id", ondelete="SET NULL"),
        nullable=True,
    )
    node_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    captured_matrix: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    performance_metrics: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    evaluation_logic: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    is_terminal_success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vector_density: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    aligned_vectors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Architectural Linkage
    probe: Mapped["BehavioralProbe"] = relationship(
        "BehavioralProbe", back_populates="telemetry_outcomes"
    )

    __table_args__ = (
        Index("idx_probe_telemetry_parent", "probe_sig"),
        Index("idx_probe_telemetry_sync", "sync_sig"),
    )


class NodeKnowledgeMatrix(Base):
    """Establishes a structural association between a processing node and an archival shard."""

    __tablename__ = "node_knowledge_matrices"

    node_sig: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processing_nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    shard_sig: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Retrieval Thresholds
    granularity_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relevance_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2), nullable=True
    )

    established_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )

    # Architectural Linkage
    node: Mapped["ProcessingNode"] = relationship("ProcessingNode", back_populates="knowledge_matrices")
    shard: Mapped["KnowledgeBase"] = relationship(  # type: ignore
        "KnowledgeBase", back_populates="associated_nodes"
    )

    __table_args__ = (
        Index("idx_matrix_node", "node_sig"),
        Index("idx_matrix_shard", "shard_sig"),
    )


class ProcessingNode(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Core logic manifest for architectural signal processing entities."""

    __tablename__ = "processing_nodes"

    node_label: Mapped[str] = mapped_column(String(255), nullable=False)
    node_class: Mapped[str] = mapped_column(String(50), nullable=False)
    node_phase: Mapped[str] = mapped_column(
        String(20), server_default=text("'draft'"), nullable=False
    )
    vector_direction: Mapped[str] = mapped_column(
        String(20), server_default=text("'inbound'"), nullable=False
    )

    # Structural Providers
    ingress_transcription_sig: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provider_keys.id"), nullable=True
    )
    inference_matrix_sig: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provider_keys.id"), nullable=True
    )
    egress_synthesis_sig: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provider_keys.id"), nullable=True
    )
    transport_nexus_sig: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provider_keys.id"), nullable=True
    )

    # Macro Blueprint
    architectural_blueprint: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )

    # Synthesis Parameters
    locale_sig: Mapped[str] = mapped_column(
        String(10), server_default=text("'en-US'"), nullable=False
    )
    vocal_spectral_sig: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transmission_velocity: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), server_default=text("1.0"), nullable=False
    )
    transmission_amplitude: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), server_default=text("1.0"), nullable=False
    )

    # Logic Determinants
    inference_model_sig: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stochastic_coefficient: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), server_default=text("0.7"), nullable=False
    )
    quantum_ceiling: Mapped[int] = mapped_column(
        Integer, server_default=text("1024"), nullable=False
    )

    # Temporal Thresholds
    temporal_ceiling: Mapped[int] = mapped_column(
        Integer, server_default=text("240"), nullable=False
    )
    silence_threshold: Mapped[int] = mapped_column(
        Integer, server_default=text("10"), nullable=False
    )
    alert_horizon: Mapped[int] = mapped_column(
        Integer, server_default=text("30"), nullable=False
    )
    fallback_logic: Mapped[str] = mapped_column(
        String(20), server_default=text("'hang_up'"), nullable=False
    )

    # Data Manifest Logic
    synthesis_logic: Mapped[list] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False
    )

    # Observability
    observability_sink: Mapped[str | None] = mapped_column(Text, nullable=True)
    telemetry_events: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'"), nullable=False
    )

    # Temporal Snapshotting
    revision: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    activation_mark: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    creator_sig: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_manifests.id"), nullable=True
    )

    # Architectural Linkage
    state_archives: Mapped[list["NodeStateArchive"]] = relationship(
        "NodeStateArchive", back_populates="node", cascade="all, delete-orphan"
    )
    knowledge_matrices: Mapped[list["NodeKnowledgeMatrix"]] = relationship(
        "NodeKnowledgeMatrix", back_populates="node", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_node_domain", "tenant_id"),
        Index("idx_node_class", "node_class"),
        Index("idx_node_phase", "node_phase"),
    )

    def __repr__(self) -> str:
        return f"<ProcessingNode(id={self.id}, label='{self.node_label}')>"


class NodeStateArchive(UUIDPrimaryKeyMixin, Base):
    """Immutable state capture of a processing node at a specific architectural revision."""

    __tablename__ = "node_state_archives"

    node_sig: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processing_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    architectural_blueprint: Mapped[dict] = mapped_column(JSONB, nullable=False)
    archive_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    author_sig: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_manifests.id"), nullable=True
    )

    # Architectural Linkage
    node: Mapped["ProcessingNode"] = relationship("ProcessingNode", back_populates="state_archives")

    __table_args__ = (
        UniqueConstraint("node_sig", "revision", name="uq_node_archive_revision"),
        Index("idx_node_archive_main", "node_sig"),
    )


class BehavioralProbe(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Encapsulates a structural context for processing node validation."""

    __tablename__ = "behavioral_probes"

    node_sig: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processing_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    injected_parameters: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    benchmark_metrics: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    author_sig: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_manifests.id"), nullable=True
    )

    # Architectural Linkage
    node: Mapped["ProcessingNode"] = relationship("ProcessingNode")
    telemetry_outcomes: Mapped[list["ProbeTelemetry"]] = relationship(
        "ProbeTelemetry", back_populates="probe", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_probe_node", "node_sig"),
    )
