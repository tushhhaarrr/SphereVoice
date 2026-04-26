"""Telemetry Transmission Hub — SignalStream architectural models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class NexusTelemetrySubscription(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Architectural subscription for telemetry vector delivery."""

    __tablename__ = "telemetry_subscriptions"

    node_sig: Mapped[uuid.UUID | None] = mapped_column(
        "agent_id",
        UUID(as_uuid=True),
        ForeignKey("processing_nodes.id", ondelete="CASCADE"),
        nullable=True,
    )

    observability_sink: Mapped[str] = mapped_column("url", Text, nullable=False)
    event_classes: Mapped[list[str]] = mapped_column("events", ARRAY(Text), nullable=False)
    transmission_timeout_s: Mapped[int] = mapped_column(
        "timeout_seconds", Integer, server_default=text("10"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )

    # Security
    auth_secret_obfuscated: Mapped[str | None] = mapped_column("secret", Text, nullable=True)

    # Relationships
    transmissions: Mapped[list["TelemetryVectorTransmission"]] = relationship(
        "TelemetryVectorTransmission", back_populates="subscription", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_subscriptions_node", "agent_id"),
    )


class TelemetryVectorTransmission(UUIDPrimaryKeyMixin, Base):
    """Audit record for a single telemetry vector transmission attempt."""

    __tablename__ = "telemetry_transmissions"

    subscription_sig: Mapped[uuid.UUID] = mapped_column(
        "webhook_id",
        UUID(as_uuid=True),
        ForeignKey("telemetry_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    sync_sig: Mapped[uuid.UUID | None] = mapped_column(
        "call_id",
        UUID(as_uuid=True),
        ForeignKey("signal_synchronisations.id", ondelete="CASCADE"),
        nullable=True,
    )

    event_class: Mapped[str] = mapped_column("event_type", String(50), nullable=False)
    transmission_payload: Mapped[dict] = mapped_column("payload", JSONB, nullable=False)

    # Delivery status
    operational_status: Mapped[str] = mapped_column("status", String(20), nullable=False)
    attempt_density: Mapped[int] = mapped_column(
        "attempts", Integer, server_default=text("0"), nullable=False
    )
    last_transmission_at: Mapped[datetime | None] = mapped_column(
        "last_attempt_at", DateTime(timezone=True), nullable=True
    )
    response_status: Mapped[int | None] = mapped_column("response_status_code", Integer, nullable=True)
    fault_summary: Mapped[str | None] = mapped_column("error_message", Text, nullable=True)

    transmitted_at: Mapped[datetime] = mapped_column(
        "created_at",
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )

    # Relationships
    subscription: Mapped["NexusTelemetrySubscription"] = relationship(
        "NexusTelemetrySubscription", back_populates="transmissions"
    )

    __table_args__ = (
        Index("idx_transmissions_subscription", "webhook_id"),
        Index("idx_transmissions_sync", "call_id"),
        Index("idx_transmissions_status", "status"),
    )
