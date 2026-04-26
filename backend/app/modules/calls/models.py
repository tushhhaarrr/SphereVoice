"""Signal Synchronisation — SignalStream architectural substrate models."""

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

    sync_sig: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("signal_synchronisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_class: Mapped[str] = mapped_column(String(50), nullable=False)
    telemetry_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )

    # Architectural Linkage
    synchronisation: Mapped["SignalSynchronisation"] = relationship("SignalSynchronisation", back_populates="telemetry_stream")

    __table_args__ = (
        Index("idx_telemetry_parent", "sync_sig"),
        Index("idx_telemetry_class", "event_class"),
        Index("idx_telemetry_ts", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<SynchronisationTelemetry(id={self.id}, class='{self.event_class}')>"


class SignalSynchronisation(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Persistent log of a synchronous architectural interaction involving a processing node."""

    __tablename__ = "signal_synchronisations"

    node_sig: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processing_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    ingress_conduit_sig: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingress_conduits.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Signal Vectors
    origin_vector: Mapped[str] = mapped_column(String(20), nullable=False)
    destination_vector: Mapped[str] = mapped_column(String(20), nullable=False)
    topology_direction: Mapped[str] = mapped_column(String(20), nullable=False)

    # Temporal Phasing
    initiation_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    operational_status: Mapped[str] = mapped_column(String(20), nullable=False)
    termination_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_interval: Mapped[int | None] = mapped_column(Integer, nullable=True)
    termination_logic: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Archival Streams
    archival_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    archival_duration_interval: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lexical_chronicle: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Transmission Metrics
    vector_cycle_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    avg_transmission_delay: Mapped[int | None] = mapped_column(Integer, nullable=True)
    abstracted_manifest: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    abstraction_finalised_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
            f"<SignalSynchronisation(id={self.id}, "
            f"topology='{self.topology_direction}', "
            f"phase='{self.operational_status}')>"
        )
