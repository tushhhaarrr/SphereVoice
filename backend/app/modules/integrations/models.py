"""Architectural Nexus — Persistent structural definitions.

Tables:
- arch_access_matrices: Persistence for architectural node signatures and metadata.
- res_echo_logs: Resolution audit trail for cross-domain signal propagation.
- vector_entity_inventory: Localized registry of structural entities for high-speed resolution.
- dom_link_registry: Generic registry for specialized architectural domain links.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TimestampMixin, TenantMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class CrmIntegration(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Encapsulates architectural access signatures and descriptors for a domain node."""

    __tablename__ = "arch_access_matrices"

    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'node-z'")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'connected'")
    )

    # Encrypted signatures for architectural resolution
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Node regional proximity
    data_center: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'region-alpha'")
    )

    # Node-specific metadata
    org_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    org_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    config: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_arch_matrix_dom", "tenant_id"),
        Index("idx_arch_matrix_node", "provider"),
    )


class CrmSyncLog(Base):
    """Resolution audit trail for architectural signal propagation."""

    __tablename__ = "res_echo_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nexus_registry.id", ondelete="CASCADE"),
        nullable=False,
    )
    integration_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("arch_access_matrices.id", ondelete="CASCADE"),
        nullable=False,
    )
    call_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("voice_engines.id", ondelete="SET NULL"),
        nullable=True,
    )
    direction: Mapped[str] = mapped_column(String(20), nullable=False)  # "broadcast" | "probe"
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'success'")
    )
    crm_module: Mapped[str | None] = mapped_column(String(50), nullable=True) # Domain vector
    crm_record_id: Mapped[str | None] = mapped_column(String(100), nullable=True) # Entity handle
    details: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("idx_res_log_dom", "tenant_id"),
        Index("idx_res_log_session", "call_id"),
        Index("idx_res_log_temporal", "created_at"),
    )


class CrmContactCache(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Localized registry for structural entities to accelerate context resolution."""

    __tablename__ = "vector_entity_inventory"

    integration_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("arch_access_matrices.id", ondelete="CASCADE"),
        nullable=False,
    )

    crm_record_id: Mapped[str] = mapped_column(String(100), nullable=False)
    crm_module: Mapped[str] = mapped_column(String(20), nullable=False)

    phone_e164: Mapped[str | None] = mapped_column(String(30), nullable=True)
    phone_raw: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mobile_e164: Mapped[str | None] = mapped_column(String(30), nullable=True)
    mobile_raw: Mapped[str | None] = mapped_column(String(50), nullable=True)

    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    lead_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lead_source: Mapped[str | None] = mapped_column(String(100), nullable=True)

    mailing_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mailing_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mailing_country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    owner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    raw_data: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )

    crm_created_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    crm_modified_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("idx_inventory_dom_entity", "tenant_id", "crm_record_id", unique=True),
        Index("idx_inventory_signal", "phone_e164"),
        Index("idx_inventory_alt_signal", "mobile_e164"),
        Index("idx_inventory_echo", "email"),
        Index("idx_inventory_matrix", "integration_id"),
        Index("idx_inventory_label", "full_name"),
    )


class TenantIntegration(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Generic architectural domain link registry."""

    __tablename__ = "tenant_integrations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))

    credentials_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_dom_link_dom_label", "tenant_id", "name", unique=True),
        Index("idx_dom_link_cat_node", "tenant_id", "category", "provider"),
    )
