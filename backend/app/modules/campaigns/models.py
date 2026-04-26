"""Signal Propagation Campaigns — SignalStream architectural models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class SignalPropagationCampaign(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A bulk egress signal propagation campaign definition."""

    __tablename__ = "signal_propagation_campaigns"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    node_sig: Mapped[uuid.UUID] = mapped_column("agent_id", UUID(as_uuid=True), nullable=False)
    operational_status: Mapped[str] = mapped_column("status", String(20), nullable=False, server_default=text("'draft'"))

    # Source configuration
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'crm'"))
    source_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    # Vector mapping: CRM field → nodal {{vector}}
    vector_mapping: Mapped[dict[str, Any]] = mapped_column("variable_mapping", JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    # Write-back mapping: abstracted_manifest field → CRM field
    writeback_mapping: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    # Propagation configuration
    origin_vector: Mapped[str | None] = mapped_column("from_number", String(20), nullable=True)
    max_concurrent: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5"))
    signals_per_minute: Mapped[int] = mapped_column("calls_per_minute", Integer, nullable=False, server_default=text("10"))
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("2"))

    # Schedule
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Benchmarks
    total_targets: Mapped[int] = mapped_column("total_contacts", Integer, nullable=False, server_default=text("0"))
    finalised_signals: Mapped[int] = mapped_column("completed_calls", Integer, nullable=False, server_default=text("0"))
    successful_signals: Mapped[int] = mapped_column("successful_calls", Integer, nullable=False, server_default=text("0"))
    voided_signals: Mapped[int] = mapped_column("failed_calls", Integer, nullable=False, server_default=text("0"))

    # A/B testing
    variant_node_sig: Mapped[uuid.UUID | None] = mapped_column("variant_agent_id", UUID(as_uuid=True), nullable=True)
    ab_split_percent: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("50"))

    # Relationships
    targets: Mapped[list["PropagationTarget"]] = relationship("PropagationTarget", back_populates="campaign", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_campaign_status", "status"),
        Index("idx_campaign_node", "agent_id"),
    )


class PropagationTarget(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A single propagation target in a campaign."""

    __tablename__ = "propagation_targets"

    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("signal_propagation_campaigns.id", ondelete="CASCADE"), nullable=False)

    # Target identity
    destination_vector: Mapped[str] = mapped_column("phone_number", String(30), nullable=False)
    crm_record_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Snapshot of CRM data
    target_data: Mapped[dict[str, Any]] = mapped_column("contact_data", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))

    # A/B testing variant
    assigned_node_sig: Mapped[uuid.UUID | None] = mapped_column("assigned_agent_id", UUID(as_uuid=True), nullable=True)

    # Synchronisation linkage
    sync_sig: Mapped[uuid.UUID | None] = mapped_column("call_id", UUID(as_uuid=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Results
    abstracted_manifest: Mapped[dict[str, Any] | None] = mapped_column("extracted_data", JSONB, nullable=True, server_default=text("'{}'::jsonb"))
    interface_results: Mapped[list[dict[str, Any]] | None] = mapped_column("tool_results", JSONB, nullable=True, server_default=text("'[]'::jsonb"))

    # Relationships
    campaign: Mapped["SignalPropagationCampaign"] = relationship("SignalPropagationCampaign", back_populates="targets")

    __table_args__ = (
        Index("idx_target_campaign_status", "campaign_id", "status"),
        Index("idx_target_vector", "phone_number"),
    )
