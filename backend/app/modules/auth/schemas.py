"""Authentication — SignalStream architectural substrate schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Authentication Requests ──────────────────────────────────────────


class AuthRequest(BaseModel):
    """Encapsulates the intent to authenticate and establish a session."""
    email: str
    password: str = Field(..., min_length=1, max_length=255)


class TokenRefreshRequest(BaseModel):
    """Encapsulates the intent to refresh session tokens."""
    refresh_token: str = Field(..., min_length=1)


# ── State Snapshots / Responses ──────────────────────────────────────────


class UserResponse(BaseModel):
    """A clean view of a user state."""
    id: UUID
    email: str
    name: str | None = None
    role: str
    tenant_id: UUID | None = None
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    """The outcome of successful authentication."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenRefreshResponse(BaseModel):
    """The outcome of a successful token refresh."""
    access_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    """A comprehensive snapshot of the user's profile."""
    id: UUID
    email: str
    name: str | None = None
    role: str
    tenant_id: UUID | None = None
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Invitation Logic ────────────────────────────────────────────


class InvitationSnapshot(BaseModel):
    """Metadata for verifying a pending invitation."""
    email: str
    name: str | None = None
    role: str
    tenant_id: UUID | None = None
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    """Encapsulates the final intent to complete registration from an invitation."""
    token: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
