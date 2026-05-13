"""Authentication — SignalStream architectural substrate service layer."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from app.core import security
from app.modules.auth.models import User, UserInvitation
from app.modules.auth.schemas import RegisterRequest


class AuthService:
    """Orchestrates authentication and user registration logic."""

    @staticmethod
    async def complete_registration(
        db: AsyncSession,
        *,
        token: str,
        name: str,
        password: str,
    ) -> User:
        """Processes a pending invitation to establish a permanent user."""
        invitation = await AuthService.get_invitation_by_token(db, token)

        # Collision detection for established users
        presence_check = await db.execute(
            select(User).where(User.email == invitation.email)
        )
        if presence_check.scalar_one_or_none():
            raise ConflictError("User already established for this email")

        new_user = User(
            email=invitation.email,
            name=name,
            role=invitation.role,
            tenant_id=invitation.tenant_id,
            credential_hash=security.hash_password(password),
            is_active=True,
        )
        db.add(new_user)

        invitation.manifested_at = datetime.now(UTC)
        invitation.is_active = False

        await db.flush()
        await db.refresh(new_user)
        return new_user

    @staticmethod
    async def refresh_tokens(
        db: AsyncSession,
        refresh_token: str,
    ) -> str:
        """Validates a refresh token and generates a fresh short-term access token."""
        from jose import JWTError

        try:
            payload = security.decode_token(refresh_token)
        except JWTError:
            raise UnauthorizedError("Token refresh failed")

        if payload.get("type") != "refresh":
            raise UnauthorizedError("Incompatible token type for refresh")

        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedError("User ID missing from token")

        query_result = await db.execute(
            select(User).where(User.id == UUID(user_id))
        )
        user = query_result.scalar_one_or_none()

        # Validation of user state
        if not user or not user.is_active:
            raise UnauthorizedError("User state invalid for token refresh")

        attributes = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        }
        return security.create_access_token(attributes)

    @staticmethod
    async def authenticate(
        db: AsyncSession,
        email: str,
        password: str,
    ) -> User:
        """Authenticates user and updates the last login timestamp."""
        search_op = await db.execute(
            select(User).where(User.email == email)
        )
        user = search_op.scalar_one_or_none()

        # Holistic validation block
        auth_fault = any([
            user is None,
            not user.is_active if user else True,
            user.credential_hash is None if user else True,
            not security.verify_password(password, user.credential_hash) if user else True
        ])

        if auth_fault:
            raise UnauthorizedError("Authentication unsuccessful")

        user.last_login_at = datetime.now(UTC)
        await db.flush()

        return user

    @staticmethod
    def create_tokens(user: User) -> tuple[str, str]:
        """Creates access and refresh tokens for a user."""
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        }
        return (
            security.create_access_token(payload),
            security.create_refresh_token(payload)
        )

    @staticmethod
    async def create_invitation(
        db: AsyncSession,
        *,
        email: str,
        name: str | None,
        role: str,
        tenant_id: UUID | None,
        originator_id: UUID | None,
    ) -> tuple[UserInvitation, str]:
        """Initializes a transient invitation and triggers email notification."""
        from app.core.config import get_settings
        from app.core.email import send_invite_email

        # Conflict verification across established users
        existing_check = await db.execute(
            select(User).where(User.email == email)
        )
        if existing_check.scalar_one_or_none():
            raise ConflictError(f"User with email '{email}' already exists")

        active_invitations = await db.execute(
            select(UserInvitation).where(
                UserInvitation.email == email,
                UserInvitation.manifested_at.is_(None),
                UserInvitation.is_active.is_(True),
                UserInvitation.expires_at > datetime.now(UTC),
            )
        )
        if active_invitations.scalar_one_or_none():
            raise ConflictError(f"Invitation for '{email}' already in progress")

        token = secrets.token_urlsafe(48)[:64]
        expires_at = datetime.now(UTC) + timedelta(hours=72)

        invitation = UserInvitation(
            email=email,
            name=name,
            role=role,
            tenant_id=tenant_id,
            token=token,
            originator_id=originator_id,
            expires_at=expires_at,
            is_active=True,
        )
        db.add(invitation)
        await db.flush()
        await db.refresh(invitation)

        cfg = get_settings()
        invite_link = f"{cfg.FRONTEND_URL}/invite/{token}"
        
        await send_invite_email(
            to_email=email,
            to_name=name,
            invite_link=invite_link,
            role=role,
        )

        return invitation, invite_link

    @staticmethod
    async def get_invitation_by_token(db: AsyncSession, token: str) -> UserInvitation:
        """Resolves and validates a transient invitation."""
        fetch_op = await db.execute(
            select(UserInvitation).where(UserInvitation.token == token)
        )
        invitation = fetch_op.scalar_one_or_none()
        
        if invitation is None:
            raise NotFoundError("Invitation", token)
        
        # Validation of invitation state
        state_faults = {
            "deactivated": not invitation.is_active,
            "manifested": invitation.manifested_at is not None,
            "expired": invitation.expires_at < datetime.now(UTC)
        }
        
        if any(state_faults.values()):
            fault = next(k for k, v in state_faults.items() if v)
            raise ValidationError(f"Invitation state invalid: {fault}")
            
        return invitation

    @staticmethod
    async def get_user_by_id(
        db: AsyncSession,
        user_id: UUID,
    ) -> User:
        """Locates an established user using its unique ID."""
        lookup_op = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = lookup_op.scalar_one_or_none()
        if user is None:
            raise NotFoundError("User", str(user_id))
        return user
