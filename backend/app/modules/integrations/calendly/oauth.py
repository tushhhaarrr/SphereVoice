"""Calendly OAuth 2.0 — token management for Calendly scheduling integration.

Uses the existing TenantIntegration model to store encrypted credentials.

Token lifecycle:
1. ``build_auth_url()`` — redirect user to Calendly consent screen.
2. ``handle_callback()`` — exchange code for tokens, upsert TenantIntegration.
3. ``get_valid_access_token()`` — return a non-expired token (auto-refresh with rotation).
4. ``disconnect_integration()`` — delete the integration row.

Calendly OAuth 2.1 uses **refresh token rotation** — every refresh returns
a new refresh_token and the old one is immediately invalidated.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.encryption import decrypt, encrypt
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.integrations.models import TenantIntegration

logger = structlog.get_logger(__name__)
settings = get_settings()

# ── Calendly endpoints ───────────────────────────────────────

_CALENDLY_AUTH_URL = "https://auth.calendly.com/oauth/authorize"
_CALENDLY_TOKEN_URL = "https://auth.calendly.com/oauth/token"
_CALENDLY_API_BASE = "https://api.calendly.com"
_CALENDLY_USERINFO_URL = f"{_CALENDLY_API_BASE}/users/me"

_SCOPES = ""  # Calendly OAuth doesn't use granular scopes


# ── OAuth state helpers (same tamper-evident pattern as Google) ─


def _generate_oauth_state(
    tenant_id: UUID, user_id: UUID,
) -> str:
    """Tamper-evident state: base64(payload).hmac16."""
    nonce = secrets.token_hex(8)
    payload = f"{tenant_id}:{user_id}:calendly:{nonce}"
    encoded = base64.urlsafe_b64encode(payload.encode()).decode()
    sig = hmac.new(
        settings.JWT_SECRET_KEY.encode(), payload.encode(), hashlib.sha256,
    ).hexdigest()[:16]
    return f"{encoded}.{sig}"


def _verify_oauth_state(state: str) -> tuple[UUID, UUID]:
    """Return (tenant_id, user_id) or raise ValidationError."""
    if not state or "." not in state:
        raise ValidationError("OAuth state parameter missing or malformed")
    try:
        encoded, sig = state.rsplit(".", 1)
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = base64.urlsafe_b64decode(padded.encode()).decode()
        expected = hmac.new(
            settings.JWT_SECRET_KEY.encode(), payload.encode(), hashlib.sha256,
        ).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected):
            raise ValidationError("Invalid OAuth state signature")
        parts = payload.split(":")
        if len(parts) < 3:
            raise ValidationError("OAuth state payload too short")
        return UUID(parts[0]), UUID(parts[1])
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"Malformed OAuth state: {exc}") from exc


# ── Service ──────────────────────────────────────────────────


class CalendlyOAuthService:
    """Calendly OAuth operations."""

    @staticmethod
    def build_auth_url(
        tenant_id: UUID,
        user_id: UUID,
    ) -> str:
        """Return the Calendly OAuth 2.0 consent URL."""
        if not settings.CALENDLY_CLIENT_ID:
            raise ValidationError("Calendly integration is not configured on this platform")

        state = _generate_oauth_state(tenant_id, user_id)
        params = {
            "client_id": settings.CALENDLY_CLIENT_ID,
            "redirect_uri": settings.CALENDLY_REDIRECT_URI,
            "response_type": "code",
            "state": state,
        }
        return f"{_CALENDLY_AUTH_URL}?{urlencode(params)}"

    @staticmethod
    async def handle_callback(
        db: AsyncSession,
        code: str,
        state: str,
    ) -> TenantIntegration:
        """Exchange authorisation code for tokens, upsert TenantIntegration."""
        tenant_id, _user_id = _verify_oauth_state(state)

        # Set RLS (callback has no JWT — security via HMAC state)
        _app_role = settings.DB_APP_ROLE
        if _app_role:
            try:
                await db.execute(text(f"SET LOCAL ROLE {_app_role}"))
            except Exception:
                pass
        await db.execute(
            text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'")  # noqa: S608
        )
        await db.execute(text("SET LOCAL app.user_role = 'admin'"))

        # Exchange code for tokens
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _CALENDLY_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.CALENDLY_CLIENT_ID,
                    "client_secret": settings.CALENDLY_CLIENT_SECRET,
                    "redirect_uri": settings.CALENDLY_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
        if resp.status_code != 200:
            logger.error("calendly_token_exchange_failed", status=resp.status_code, body=resp.text[:300])
            raise ValidationError("Calendly token exchange failed — check client credentials")

        token_data = resp.json()
        access_token: str | None = token_data.get("access_token")
        refresh_token: str | None = token_data.get("refresh_token")
        expires_in: int = int(token_data.get("expires_in", 7200))

        if not access_token:
            raise ValidationError("No access_token in Calendly response")

        # Fetch user info (owner URI + email)
        account_email: str | None = None
        owner_uri: str | None = None
        organization_uri: str | None = None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                info_resp = await client.get(
                    _CALENDLY_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            if info_resp.status_code == 200:
                resource = info_resp.json().get("resource", {})
                account_email = resource.get("email")
                owner_uri = resource.get("uri")
                organization_uri = resource.get("current_organization")
        except Exception:
            logger.warning("calendly_userinfo_fetch_failed", tenant_id=str(tenant_id))

        token_expires_at = (datetime.now(UTC) + timedelta(seconds=expires_in)).isoformat()
        now = datetime.now(UTC)

        credentials = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expires_at": token_expires_at,
        }

        # Upsert: one row per (tenant_id, provider=calendly)
        existing = await db.execute(
            select(TenantIntegration).where(
                TenantIntegration.tenant_id == tenant_id,
                TenantIntegration.provider == "calendly",
            )
        )
        integration = existing.scalar_one_or_none()

        if integration is None:
            integration = TenantIntegration(
                tenant_id=tenant_id,
                name="calendly",
                category="calendar",
                provider="calendly",
            )
            db.add(integration)

        integration.status = "connected"
        integration.credentials_encrypted = encrypt(json.dumps(credentials))
        integration.config = {
            **(integration.config or {}),
            "account_email": account_email,
            "owner_uri": owner_uri,
            "organization_uri": organization_uri,
        }
        integration.last_synced_at = now
        integration.updated_at = now

        await db.commit()
        await db.refresh(integration)
        logger.info(
            "calendly_integration_connected",
            tenant_id=str(tenant_id),
            email=account_email,
        )
        return integration

    @staticmethod
    async def get_valid_access_token(
        db: AsyncSession,
        integration: TenantIntegration,
    ) -> str:
        """Return a valid access token, refreshing if expired.

        Calendly uses refresh token rotation — the old refresh token is
        invalidated on each use, so we must always store the new one.
        """
        if not integration.credentials_encrypted:
            raise ValidationError("No credentials stored — please reconnect Calendly")

        creds = json.loads(decrypt(integration.credentials_encrypted))
        access_token: str = creds.get("access_token", "")
        refresh_token: str | None = creds.get("refresh_token")
        expires_at_str: str | None = creds.get("token_expires_at")

        # Check expiry (refresh 2 minutes early)
        needs_refresh = True
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at > datetime.now(UTC) + timedelta(minutes=2):
                    needs_refresh = False
            except (ValueError, TypeError):
                pass

        if not needs_refresh:
            return access_token

        # Refresh — Calendly requires client_id but NOT client_secret for refresh
        if not refresh_token:
            raise ValidationError("No refresh token — please reconnect Calendly")

        import asyncio as _asyncio

        resp = None
        for _attempt in range(3):
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    _CALENDLY_TOKEN_URL,
                    data={
                        "client_id": settings.CALENDLY_CLIENT_ID,
                        "client_secret": settings.CALENDLY_CLIENT_SECRET,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
            if resp.status_code == 200:
                break
            if resp.status_code >= 500:
                logger.warning(
                    "calendly_token_refresh_retrying",
                    status=resp.status_code,
                    attempt=_attempt + 1,
                )
                await _asyncio.sleep(1.0 * (_attempt + 1))
                continue
            break

        if resp is None or resp.status_code != 200:
            integration.status = "error"
            await db.commit()
            raise ValidationError("Token refresh failed — please reconnect Calendly")

        token_data = resp.json()
        new_access = token_data.get("access_token")
        if not new_access:
            raise ValidationError("No access_token in refresh response")

        new_expires = (
            datetime.now(UTC) + timedelta(seconds=int(token_data.get("expires_in", 7200)))
        ).isoformat()

        creds["access_token"] = new_access
        creds["token_expires_at"] = new_expires
        # Calendly rotation: ALWAYS store the new refresh token
        new_refresh = token_data.get("refresh_token")
        if new_refresh:
            creds["refresh_token"] = new_refresh

        integration.credentials_encrypted = encrypt(json.dumps(creds))
        integration.status = "connected"
        await db.commit()

        logger.debug("calendly_token_refreshed", integration_id=str(integration.id))
        return new_access

    @staticmethod
    async def sync_integration(
        db: AsyncSession,
        integration_id: UUID,
        tenant_id: UUID,
    ) -> TenantIntegration:
        """Verify the connection is live by refreshing the token & fetching user info."""
        result = await db.execute(
            select(TenantIntegration).where(
                TenantIntegration.id == integration_id,
                TenantIntegration.tenant_id == tenant_id,
            )
        )
        integration = result.scalar_one_or_none()
        if integration is None:
            raise NotFoundError("Calendly integration not found")

        try:
            token = await CalendlyOAuthService.get_valid_access_token(db, integration)
            # Fetch user info to verify and update
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    _CALENDLY_USERINFO_URL,
                    headers={"Authorization": f"Bearer {token}"},
                )
            if resp.status_code == 200:
                resource = resp.json().get("resource", {})
                integration.config = {
                    **(integration.config or {}),
                    "account_email": resource.get("email"),
                    "owner_uri": resource.get("uri"),
                    "organization_uri": resource.get("current_organization"),
                }
            integration.status = "connected"
            integration.last_synced_at = datetime.now(UTC)
            await db.commit()
            await db.refresh(integration)
        except Exception as exc:
            logger.warning("calendly_sync_error", error=str(exc))
            integration.status = "error"
            await db.commit()
            await db.refresh(integration)

        return integration

    @staticmethod
    async def disconnect_integration(
        db: AsyncSession,
        integration_id: UUID,
        tenant_id: UUID,
    ) -> None:
        """Delete the Calendly integration."""
        result = await db.execute(
            select(TenantIntegration).where(
                TenantIntegration.id == integration_id,
                TenantIntegration.tenant_id == tenant_id,
            )
        )
        integration = result.scalar_one_or_none()
        if integration is None:
            raise NotFoundError("Calendly integration not found")

        await db.delete(integration)
        await db.commit()
        logger.info(
            "calendly_integration_disconnected",
            integration_id=str(integration_id),
            tenant_id=str(tenant_id),
        )
