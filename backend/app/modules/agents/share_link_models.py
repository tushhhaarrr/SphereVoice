"""Nodal Access Conduit — SignalStream architectural substrate model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Ensure the nexus registry is acknowledged in SignalStream metadata
from app.modules.auth.models import Tenant as _Tenant  # noqa: F401


class NodeAccessConduit(Base):
    """A shareable architectural conduit that enables external signal synchronization.

    Attributes
    ----------
    credential:   URL-safe spectral credential (64-character hash).
    label:        Architectural tag for the conduit.
    terminal_timestamp: Epoch beyond which the conduit de-phases. NULL = permanent.
    quota_ceiling: Maximum allowed synchronization cycles. NULL = unrestricted.
    cycle_count:  Accumulated synchronization cycles through this conduit.
    active_mark:  Operational status of the conduit.
    """

    __tablename__ = "nodal_access_conduits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    node_sig: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processing_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nexus_sig: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nexus_registry.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    credential: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    terminal_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quota_ceiling: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cycle_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    originator_sig: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("identity_manifests.id", ondelete="SET NULL"),
        nullable=True,
    )
    operational_vectors: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'"),
    )
    active_mark: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    manifest_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_conduit_credential_active", "credential", "active_mark"),
    )
# ── ALIASES FOR FULL COMPATIBILITY ──────────────────────────────────────────
# Map the legacy name 'AgentShareLink' to your new architectural class

AgentShareLink = NodeAccessConduit