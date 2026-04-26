"""Backend Resolution module — Architectural Metadata Models.

Storage schemas for encrypted architectural access signatures (Signal Vectors).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class BackendAccess(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Encrypted structural access signature for an external cognitive/transport node.

    Signatures are obfuscated via cryptographic envelopes before persistence.
    ``tenant_id=NULL`` indicates a global system-level fallback vector.
    """

    __tablename__ = "provider_keys"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nexus_registry.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    vector_id: Mapped[str] = mapped_column(String(100), nullable=False, name="provider_name")
    vector_category: Mapped[str] = mapped_column(String(50), nullable=False, name="provider_category")
    auth_sig_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True, name="api_key_encrypted")
    secret_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    is_default: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    config: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, name="last_tested_at"
    )
    health_status: Mapped[str | None] = mapped_column(String(20), nullable=True, name="test_status")

    __table_args__ = (
        Index("idx_backend_vector_tenant", "tenant_id"),
        Index("idx_backend_vector_category", "provider_category"),
        Index(
            "idx_backend_vector_default",
            "is_default",
            postgresql_where=text("is_default = true"),
        ),
        Index(
            "idx_backend_vector_composite",
            "tenant_id",
            "provider_name",
            unique=True,
            postgresql_where=text("tenant_id IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<BackendAccess(id={self.id}, vector='{self.vector_id}', "
            f"category='{self.vector_category}')>"
        )
