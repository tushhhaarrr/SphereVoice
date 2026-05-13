"""Voice Engine — SignalStream architectural substrate models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class SynchronisationTelemetry(UUIDPrimaryKeyMixin, Base):
    """Reflects a granular state transition or telemetry event captured within a synchronisation cycle."""

    __tablename__ = "synchronisation_telemetry"

    voice_engine_id: Mapped[uuid.UUID] = mapped_column(
        "sync_sig",
        UUID(as_uuid=True),
        ForeignKey("voice_engines.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column("event_class", String(50), nullable=False)
    payload: Mapped[dict] = mapped_column("telemetry_payload", JSONB, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )

    # Architectural Linkage
    synchronisation: Mapped["VoiceEngine"] = relationship("VoiceEngine", back_populates="telemetry_stream")

    __table_args__ = (
        Index("idx_telemetry_parent", "sync_sig"),
        Index("idx_telemetry_class", "event_class"),
        Index("idx_telemetry_ts", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<SynchronisationTelemetry(id={self.id}, type='{self.event_type}')>"


class VoiceEngine(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Persistent log of a synchronous architectural interaction involving a processing node."""

    __tablename__ = "voice_engines"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        "node_sig",
        UUID(as_uuid=True),
        ForeignKey("processing_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    phone_number_id: Mapped[uuid.UUID | None] = mapped_column(
        "ingress_conduit_sig",
        UUID(as_uuid=True),
        ForeignKey("ingress_conduits.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Signal Vectors
    origin: Mapped[str] = mapped_column("origin_vector", String(20), nullable=False)
    destination: Mapped[str] = mapped_column("destination_vector", String(20), nullable=False)
    direction: Mapped[str] = mapped_column("topology_direction", String(20), nullable=False)

    # Temporal Phasing
    initiation_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column("operational_status", String(20), nullable=False)
    termination_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration: Mapped[int | None] = mapped_column("duration_interval", Integer, nullable=True)
    disposition: Mapped[str | None] = mapped_column("termination_logic", String(100), nullable=True)

    # Archival Streams
    archival_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    archival_duration_interval: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transcript: Mapped[dict | None] = mapped_column("lexical_chronicle", JSONB, nullable=True)

    # Transmission Metrics
    vector_cycle_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    avg_transmission_delay: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[dict] = mapped_column(
        "abstracted_manifest", JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    summary_finalized_at: Mapped[datetime | None] = mapped_column(
        "abstraction_finalised_at", DateTime(timezone=True), nullable=True
    )

    # Architectural Overhead
    ingress_conversion_overhead: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    inference_overhead: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    egress_synthesis_overhead: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    transport_overhead: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    aggregate_overhead: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    utilization_matrix: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )

    # Contextual Anchors
    architectural_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    dynamic_nodal_vectors: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    downstream_identity_sig: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    downstream_sync_phase: Mapped[str | None] = mapped_column(String(20), nullable=True)
    downstream_sync_fault: Mapped[str | None] = mapped_column(Text, nullable=True)
    downstream_sync_finalised_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Telemetry Streams
    telemetry_stream: Mapped[list["SynchronisationTelemetry"]] = relationship(
        "SynchronisationTelemetry", back_populates="synchronisation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_sync_nexus", "tenant_id"),
        Index("idx_sync_node", "node_sig"),
        Index("idx_sync_phase", "operational_status"),
        Index("idx_sync_initiation", "initiation_timestamp"),
        Index("idx_sync_topology", "topology_direction"),
        Index(
            "idx_sync_manifest",
            "abstracted_manifest",
            postgresql_using="gin",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<VoiceEngine(id={self.id}, "
            f"direction='{self.direction}', "
            f"status='{self.status}')>"
        )
# ── ALIASES FOR FULL COMPATIBILITY ──────────────────────────────────────────
# Map legacy names used in Alembic to your new architectural classes

Call = VoiceEngine
CallEvent = SynchronisationTelemetry