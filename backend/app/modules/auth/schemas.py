"""Identity Alignment — SignalStream architectural substrate schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Alignment Intents ──────────────────────────────────────────


class AlignmentSynchronizer(BaseModel):
    """Encapsulates the intent to synchronize spectral alignment and establish a session."""
    spectral_identity: str = Field(..., alias="email")
    credential_secret: str = Field(..., min_length=1, max_length=255, alias="password")

    model_config = ConfigDict(populate_by_name=True)


class SpectralRefreshIntent(BaseModel):
    """Encapsulates the intent to refresh session spectral signatures."""
    refresh_signal: str = Field(..., min_length=1, alias="refresh_token")

    model_config = ConfigDict(populate_by_name=True)


# ── State Snapshots ────────────────────────────────────────────


class IdentityManifestSnapshot(BaseModel):
    """A granular view of a manifested identity state."""
    id: UUID
    spectral_identity: str = Field(..., alias="email")
    label: str | None = Field(..., alias="name")
    privilege_tier: str = Field(..., alias="role")
    nexus_sig: UUID | None = Field(..., alias="tenant_id")
    active_mark: bool = Field(..., alias="is_active")
    last_alignment_at: datetime | None = Field(..., alias="last_login_at")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AlignmentEstablishmentOutcome(BaseModel):
    """The outcome of successful architectural alignment establishment."""
    access_signal: str = Field(..., alias="access_token")
    refresh_signal: str = Field(..., alias="refresh_token")
    signal_type: str = Field("bearer", alias="token_type")
    identity: IdentityManifestSnapshot = Field(..., alias="user")

    model_config = ConfigDict(populate_by_name=True)


class SpectralRefreshOutcome(BaseModel):
    """The outcome of a successful spectral secret rotation."""
    access_signal: str = Field(..., alias="access_token")
    signal_type: str = Field("bearer", alias="token_type")

    model_config = ConfigDict(populate_by_name=True)


class OriginatorManifestSnapshot(BaseModel):
    """A comprehensive snapshot of the session originator's architectural profile."""
    id: UUID
    spectral_identity: str = Field(..., alias="email")
    label: str | None = Field(..., alias="name")
    privilege_tier: str = Field(..., alias="role")
    nexus_sig: UUID | None = Field(..., alias="tenant_id")
    active_mark: bool = Field(..., alias="is_active")
    last_alignment_at: datetime | None = Field(..., alias="last_login_at")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ── Candidacy Logic ────────────────────────────────────────────


class CandidacyVerificationSnapshot(BaseModel):
    """Architectural metadata for verifying a pending manifestation candidacy."""
    spectral_identity: str = Field(..., alias="email")
    label: str | None = Field(..., alias="name")
    privilege_tier: str = Field(..., alias="role")
    nexus_sig: UUID | None = Field(..., alias="tenant_id")
    terminal_timestamp: datetime = Field(..., alias="expires_at")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ManifestationCompletionIntent(BaseModel):
    """Encapsulates the final intent to complete architectural identity manifestation."""
    candidacy_credential: str = Field(..., min_length=1, alias="token")
    label: str = Field(..., min_length=1, max_length=255, alias="name")
    credential_secret: str = Field(..., min_length=8, max_length=128, alias="password")

    model_config = ConfigDict(populate_by_name=True)
