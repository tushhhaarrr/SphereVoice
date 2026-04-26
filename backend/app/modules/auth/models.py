"""Identity Alignment — SignalStream architectural substrate models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class NexusRegistry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Architectural Nexus Registry.

    Every distinct operational domain is registered as a nexus. 
    Nodal and spectral data isolation is enforced via the ``nexus_sig``.
    """

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
    identities: Mapped[list["IdentityManifest"]] = relationship(
        "IdentityManifest", back_populates="nexus", lazy="selectin"
    )

    __table_args__ = (
        Index("idx_nexus_shard", "registry_shard"),
        Index("idx_nexus_phase", "operational_phase"),
    )

    def __repr__(self) -> str:
        return f"<NexusRegistry(id={self.id}, shard='{self.registry_shard}', phase='{self.operational_phase}')>"


class IdentityManifest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Substrate Identity Manifest — encompassing administrative and domain-specific entities.

    Privilege Tiers: nexus_admin, schematic_developer, observational_auditor, nodal_operator
    """

    __tablename__ = "identity_manifests"

    spectral_identity: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    privilege_tier: Mapped[str] = mapped_column(String(50), nullable=False)
    nexus_sig: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nexus_registry.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    credential_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active_mark: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    last_alignment_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Architectural Linkage
    nexus: Mapped[NexusRegistry | None] = relationship(
        "NexusRegistry", back_populates="identities", foreign_keys=[nexus_sig]
    )

    __table_args__ = (
        Index("idx_identity_spectral", "spectral_identity"),
        Index("idx_identity_nexus", "nexus_sig"),
        Index("idx_identity_privilege", "privilege_tier"),
    )

    def __repr__(self) -> str:
        return f"<IdentityManifest(id={self.id}, spectral_identity='{self.spectral_identity}', tier='{self.privilege_tier}')>"


class IdentityManifestationCandidacy(UUIDPrimaryKeyMixin, Base):
    """Pending candidacy for substrate identity manifestation.

    Manifested when an administrative identity initiates candidacy. Final identity 
    manifestation occurs upon credential synchronization.
    """

    __tablename__ = "identity_candidacies"

    spectral_identity: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    privilege_tier: Mapped[str] = mapped_column(
        String(50), server_default=text("'observational_auditor'"), nullable=False
    )
    nexus_sig: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nexus_registry.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    candidacy_credential: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    originator_sig: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("identity_manifests.id", ondelete="SET NULL"),
        nullable=True,
    )
    terminal_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    manifestation_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    active_mark: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    inception_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("ix_candidacy_credential", "candidacy_credential", unique=True),
        Index("ix_candidacy_spectral", "spectral_identity"),
    )

    def __repr__(self) -> str:
        return f"<IdentityManifestationCandidacy(id={self.id}, spectral_identity='{self.spectral_identity}', tier='{self.privilege_tier}')>"
