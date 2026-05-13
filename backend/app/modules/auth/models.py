"""Authentication — SignalStream architectural substrate models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Workspace/Tenant Registry."""

    __tablename__ = "nexus_registry"

    label: Mapped[str] = mapped_column(String(255), nullable=False)
    registry_shard: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    operational_phase: Mapped[str] = mapped_column(
        String(20), server_default=text("'active'"), nullable=False
    )
    architectural_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )

    # Architectural Linkage
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="tenant", lazy="selectin"
    )

    __table_args__ = (
        Index("idx_nexus_shard", "registry_shard"),
        Index("idx_nexus_phase", "operational_phase"),
    )

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, shard='{self.registry_shard}', phase='{self.operational_phase}')>"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """User model mapped to identity_manifests table."""

    __tablename__ = "identity_manifests"

    email: Mapped[str] = mapped_column("spectral_identity", String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column("label", String(255), nullable=True)
    role: Mapped[str] = mapped_column("privilege_tier", String(50), nullable=False)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        "nexus_sig",
        UUID(as_uuid=True),
        ForeignKey("nexus_registry.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    credential_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        "active_mark", Boolean, server_default=text("true"), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        "last_alignment_at", DateTime(timezone=True), nullable=True
    )

    # Architectural Linkage
    tenant: Mapped[Tenant | None] = relationship(
        "Tenant", back_populates="users", foreign_keys=[tenant_id]
    )

    __table_args__ = (
        Index("idx_identity_spectral", "spectral_identity"),
        Index("idx_identity_nexus", "nexus_sig"),
        Index("idx_identity_privilege", "privilege_tier"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"


class UserInvitation(UUIDPrimaryKeyMixin, Base):
    """Pending candidacy for user registration."""

    __tablename__ = "identity_candidacies"

    email: Mapped[str] = mapped_column("spectral_identity", String(255), nullable=False)
    name: Mapped[str | None] = mapped_column("label", String(255), nullable=True)
    role: Mapped[str] = mapped_column(
        "privilege_tier", String(50), server_default=text("'observational_auditor'"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        "nexus_sig",
        UUID(as_uuid=True),
        ForeignKey("nexus_registry.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    token: Mapped[str] = mapped_column("candidacy_credential", String(64), unique=True, nullable=False)
    originator_id: Mapped[uuid.UUID | None] = mapped_column(
        "originator_sig",
        UUID(as_uuid=True),
        ForeignKey("identity_manifests.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        "terminal_timestamp", DateTime(timezone=True), nullable=False
    )
    manifested_at: Mapped[datetime | None] = mapped_column(
        "manifestation_timestamp", DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        "active_mark", Boolean, server_default=text("true"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        "inception_timestamp", DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("ix_candidacy_credential", "candidacy_credential", unique=True),
        Index("ix_candidacy_spectral", "spectral_identity"),
    )

    def __repr__(self) -> str:
        return f"<UserInvitation(id={self.id}, email='{self.email}', role='{self.role}')>"
