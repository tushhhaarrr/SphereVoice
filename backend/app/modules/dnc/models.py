"""DNC (Do Not Call) module — SQLAlchemy model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class DncEntry(UUIDPrimaryKeyMixin, TenantMixin, Base):
    """A single Do-Not-Call suppression entry for a tenant.

    Every outbound dial must check against this table before connecting.
    Entries may optionally expire (expires_at IS NULL means permanent).
    Unique constraint on (tenant_id, phone_number) prevents duplicates.
    """

    __tablename__ = "dnc_entries"

    phone_number: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'manual'"))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("identity_manifests.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "phone_number", name="uq_dnc_entries_tenant_phone"),
        Index("idx_dnc_entries_tenant_phone", "tenant_id", "phone_number"),
        Index("idx_dnc_entries_expires_at", "expires_at"),
    )
