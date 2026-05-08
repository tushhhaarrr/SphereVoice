"""Ingress Conduit — architectural signal entry points."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class IngressConduit(UUIDPrimaryKeyMixin, TenantMixin, Base):
    """Architectural ingress conduit for asynchronous signal entry.

    Each conduit is mapped to a processing node and routed via a
    specified substrate provider.
    """

    __tablename__ = "ingress_conduits"

    ingress_vector: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False
    )
    country_code: Mapped[str | None] = mapped_column(String(5), nullable=True)
    substrate_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    substrate_metadata_sig: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Nodal Mapping
    node_sig: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processing_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Routing
    fallback_vector: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nexus_webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Substrate Capabilities
    capabilities: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )

    # Financial Benchmarks
    subscription_benchmark: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )

    # Default outbound vector (one per tenant)
    is_default_egress: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )

    conduit_status: Mapped[str] = mapped_column(
        String(20), server_default=text("'active'"), nullable=False
    )
    provisioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_conduits_tenant", "tenant_id"),
        Index("idx_conduits_node", "node_sig"),
        Index("idx_conduits_status", "conduit_status"),
    )

    def __repr__(self) -> str:
        return f"<IngressConduit(id={self.id}, vector='{self.ingress_vector}')>"
# ── ALIASES FOR FULL COMPATIBILITY ──────────────────────────────────────────
# Map the legacy name 'PhoneNumber' to your new architectural class
# Replace 'YourNewClass' with the actual class name found in this file (e.g., IngressConduit)

PhoneNumber = IngressConduit

# MISSING ALIASES CAUSING THE ERROR:

# MISSING ALIASES CAUSING THE ERROR: