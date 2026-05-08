"""Google OAuth 2.0 — shared token management for Calendar & Sheets.

Uses the existing TenantIntegration model to store encrypted credentials.
Both Google Calendar and Google Sheets integrations share a common OAuth
flow; the only difference is the requested scopes and redirect URI.

Token lifecycle:
1. ``build_auth_url()`` — redirect user to Google consent screen.
2. ``handle_callback()`` — exchange code for tokens, upsert TenantIntegration.
3. ``get_valid_access_token()`` — return a non-expired token (auto-refresh).
4. ``revoke_and_delete()`` — revoke token at Google, delete row.
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

# ── Google endpoints ─────────────────────────────────────────

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Scopes per integration type
_SCOPES: dict[str, str] = {
    "google_calendar": (
        "https://www.googleapis.com/auth/calendar "
        "https://www.googleapis.com/auth/userinfo.email"
    ),
    "google_sheets": (
        "https://www.googleapis.com/auth/spreadsheets "
        "https://www.googleapis.com/auth/drive.readonly "
        "https://www.googleapis.com/auth/userinfo.email"
    ),
}

_REDIRECT_URIS: dict[str, str] = {
    "google_calendar": settings.GOOGLE_CALENDAR_REDIRECT_URI,
    "google_sheets": settings.GOOGLE_SHEETS_REDIRECT_URI,
}

_CATEGORIES: dict[str, str] = {
    "google_calendar": "calendar",
    "google_sheets": "spreadsheet",
}


# ── OAuth state helpers (same tamper-evident pattern as Zoho) ─

def _generate_oauth_state(
    tenant_id: UUID, user_id: UUID, provider: str,
) -> str:
    """Tamper-evident state: base64(payload).hmac16."""
    nonce = secrets.token_hex(8)
    payload = f"{tenant_id}:{user_id}:{provider}:{nonce}"
    encoded = base64.urlsafe_b64encode(payload.encode()).decode()
    sig = hmac.new(
        settings.JWT_SECRET_KEY.encode(), payload.encode(), hashlib.sha256,
    ).hexdigest()[:16]
    return f"{encoded}.{sig}"


def _verify_oauth_state(state: str) -> tuple[UUID, UUID, str]:
    """Return (tenant_id, user_id, provider) or raise ValidationError."""
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
        return UUID(parts[0]), UUID(parts[1]), parts[2]
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"Malformed OAuth state: {exc}") from exc


# ── Service ──────────────────────────────────────────────────


class GoogleOAuthService:
    """Shared Google OAuth operations for all Google integrations."""

    @staticmethod
    def build_auth_url(
        tenant_id: UUID,
        user_id: UUID,
        provider: str,
    ) -> str:
        """Return the Google OAuth 2.0 consent URL."""
        if not settings.GOOGLE_CLIENT_ID:
            raise ValidationError("Google integration is not configured on this platform")
        if provider not in _SCOPES:
            raise ValidationError(f"Unknown Google provider: {provider}")

        state = _generate_oauth_state(tenant_id, user_id, provider)
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": _REDIRECT_URIS[provider],
            "response_type": "code",
            "scope": _SCOPES[provider],
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"

    @staticmethod
    async def handle_callback(
        db: AsyncSession,
        code: str,
        state: str,
    ) -> TenantIntegration:
        """Exchange authorisation code for tokens, upsert TenantIntegration."""
        tenant_id, _user_id, provider = _verify_oauth_state(state)

        if provider not in _SCOPES:
            raise ValidationError(f"Unknown Google provider in state: {provider}")

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
                _GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": _REDIRECT_URIS[provider],
                    "grant_type": "authorization_code",
                },
            )
        if resp.status_code != 200:
            logger.error("google_token_exchange_failed", status=resp.status_code, body=resp.text[:300])
            raise ValidationError("Google token exchange failed — check client credentials")

        token_data = resp.json()
        access_token: str | None = token_data.get("access_token")
        refresh_token: str | None = token_data.get("refresh_token")
        expires_in: int = int(token_data.get("expires_in", 3600))

        if not access_token:
            raise ValidationError("No access_token in Google response")

        # Fetch user email (non-fatal)
        account_email: str | None = None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                info_resp = await client.get(
                    _GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            if info_resp.status_code == 200:
                account_email = info_resp.json().get("email")
        except Exception:
            logger.warning("google_userinfo_fetch_failed", tenant_id=str(tenant_id))

        token_expires_at = (datetime.now(UTC) + timedelta(seconds=expires_in)).isoformat()
        now = datetime.now(UTC)

        credentials = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expires_at": token_expires_at,
        }

        # Upsert: one row per (tenant_id, provider) via the name field
        integration_name = f"{provider}"  # e.g. "google_calendar"
        existing = await db.execute(
            select(TenantIntegration).where(
                TenantIntegration.tenant_id == tenant_id,
                TenantIntegration.provider == provider,
            )
        )
        integration = existing.scalar_one_or_none()

        if integration is None:
            integration = TenantIntegration(
                tenant_id=tenant_id,
                name=integration_name,
                category=_CATEGORIES[provider],
                provider=provider,
            )
            db.add(integration)

        integration.status = "connected"
        integration.credentials_encrypted = encrypt(json.dumps(credentials))
        integration.config = {
            **(integration.config or {}),
            "account_email": account_email,
        }
        integration.last_synced_at = now
        integration.updated_at = now

        await db.commit()
        await db.refresh(integration)
        logger.info(
            "google_integration_connected",
            provider=provider,
            tenant_id=str(tenant_id),
            email=account_email,
        )
        return integration

    @staticmethod
    async def get_valid_access_token(
        db: AsyncSession,
        integration: TenantIntegration,
    ) -> str:
        """Return a valid access token, refreshing if expired."""
        if not integration.credentials_encrypted:
            raise ValidationError("No credentials stored — please reconnect")

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

        # Refresh
        if not refresh_token:
            raise ValidationError("No refresh token — please reconnect Google")

        # Retry token refresh up to 2 times (critical path during live calls)
        import asyncio as _asyncio

        resp = None
        for _attempt in range(3):
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    _GOOGLE_TOKEN_URL,
                    data={
                        "client_id": settings.GOOGLE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_CLIENT_SECRET,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
            if resp.status_code == 200:
                break
            if resp.status_code >= 500:
                logger.warning(
                    "google_token_refresh_retrying",
                    status=resp.status_code,
                    attempt=_attempt + 1,
                )
                await _asyncio.sleep(1.0 * (_attempt + 1))
                continue
            # 4xx errors are not retryable
            break

        if resp is None or resp.status_code != 200:
            integration.status = "error"
            await db.commit()
            raise ValidationError("Token refresh failed — please reconnect Google")

        token_data = resp.json()
        new_access = token_data.get("access_token")
        if not new_access:
            raise ValidationError("No access_token in refresh response")

        new_expires = (
            datetime.now(UTC) + timedelta(seconds=int(token_data.get("expires_in", 3600)))
        ).isoformat()

        creds["access_token"] = new_access
        creds["token_expires_at"] = new_expires
        # Google may issue a new refresh token
        if token_data.get("refresh_token"):
            creds["refresh_token"] = token_data["refresh_token"]

        integration.credentials_encrypted = encrypt(json.dumps(creds))
        integration.status = "connected"
        await db.commit()

        logger.debug("google_token_refreshed", integration_id=str(integration.id))
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
            raise NotFoundError("TenantIntegration", str(integration_id))

        try:
            access_token = await GoogleOAuthService.get_valid_access_token(db, integration)
        except ValidationError:
            raise

        # Optionally refresh email
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                info_resp = await client.get(
                    _GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            if info_resp.status_code == 200:
                email = info_resp.json().get("email")
                if email:
                    config = dict(integration.config or {})
                    config["account_email"] = email
                    integration.config = config
        except Exception:
            pass

        integration.last_synced_at = datetime.now(UTC)
        integration.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(integration)
        return integration

    @staticmethod
    async def disconnect_integration(
        db: AsyncSession,
        integration_id: UUID,
        tenant_id: UUID,
    ) -> None:
        """Revoke Google token and delete the integration."""
        result = await db.execute(
            select(TenantIntegration).where(
                TenantIntegration.id == integration_id,
                TenantIntegration.tenant_id == tenant_id,
            )
        )
        integration = result.scalar_one_or_none()
        if integration is None:
            raise NotFoundError("TenantIntegration", str(integration_id))

        # Best-effort token revocation
        if integration.credentials_encrypted:
            try:
                creds = json.loads(decrypt(integration.credentials_encrypted))
                token = creds.get("access_token") or creds.get("refresh_token")
                if token:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        await client.post(_GOOGLE_REVOKE_URL, params={"token": token})
            except Exception:
                logger.warning("google_revoke_failed", integration_id=str(integration_id))

        await db.delete(integration)
        await db.commit()
        logger.info(
            "google_integration_disconnected",
            integration_id=str(integration_id),
            tenant_id=str(tenant_id),
        )
