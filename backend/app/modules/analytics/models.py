"""Observability Hub — SignalStream architectural analytics models."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
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
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class EchoLog(UUIDPrimaryKeyMixin, Base):
    """Immutable operational echo record for structural substrate audits."""

    __tablename__ = "operational_echos"

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("identity_manifests.id", ondelete="SET NULL"), nullable=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("nexus_registry.id", ondelete="CASCADE"), nullable=True)

    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    changes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)

    __table_args__ = (Index("idx_echos_domain", "tenant_id"), Index("idx_echos_temporal", "timestamp"))


class TelemetryRollup(UUIDPrimaryKeyMixin, Base):
    """Pre-computed structural rollups for temporal signal vectors."""

    __tablename__ = "telemetry_rollups"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("nexus_registry.id", ondelete="CASCADE"), nullable=True)
    node_sig: Mapped[uuid.UUID | None] = mapped_column("agent_id", UUID(as_uuid=True), ForeignKey("processing_nodes.id", ondelete="CASCADE"), nullable=True)

    period_horizon: Mapped[date] = mapped_column(Date, nullable=False)
    density: Mapped[str] = mapped_column(String(10), nullable=False)  # day, week, month

    # Benchmarks
    aggregate_signals: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    terminal_signals: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    voided_signals: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)

    avg_latency_ms: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    success_index: Mapped[float] = mapped_column(Numeric(5, 4), server_default=text("0"), nullable=False)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "agent_id", "period_horizon", "density", name="uq_telemetry_rollups_period"),
        Index("idx_telemetry_rollups_node", "agent_id"),
    )


class ArchitecturalBlueprint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Established structural pattern for manifesting processing nodes."""

    __tablename__ = "architectural_blueprints"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    category: Mapped[str] = mapped_column(String(100), nullable=False)

    # Architectural Scope
    is_builtin: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), server_default=text("'private'"), nullable=False)

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("nexus_registry.id", ondelete="CASCADE"), nullable=True)
    
    node_class: Mapped[str] = mapped_column("agent_type", String(50), nullable=False)
    architectural_blueprint: Mapped[dict] = mapped_column("config", JSONB, server_default=text("'{}'::jsonb"), nullable=False)

    # Synthesis & Abstraction Templates
    extraction_fields: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)

    __table_args__ = (Index("idx_blueprints_domain", "tenant_id"),)

AuditLog = EchoLog
TelemetryRollup = TelemetryRollup
ArchitecturalBlueprint = ArchitecturalBlueprint