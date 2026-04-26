"""Auth API endpoint tests.

Tests:
- POST /api/v1/auth/login (success, invalid password, inactive user)
- POST /api/v1/auth/refresh (success, expired token, bad token)
- GET  /api/v1/auth/me (authenticated, unauthenticated)
- RBAC guards (admin-only, write-only, read_only)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import TEST_PASSWORD


@pytest.mark.asyncio
class TestLogin:
    """POST /api/v1/auth/login."""

    async def test_login_success(
        self, client: AsyncClient, admin_user: object
    ) -> None:
        """Valid credentials return access + refresh tokens."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@Sphere.com", "password": TEST_PASSWORD},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "admin@Sphere.com"
        assert data["user"]["role"] == "admin"

    async def test_login_wrong_password(
        self, client: AsyncClient, admin_user: object
    ) -> None:
        """Wrong password returns 401."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@Sphere.com", "password": "wrong"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_email(self, client: AsyncClient) -> None:
        """Non-existent email returns 401."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@Sphere.com", "password": "any"},
        )
        assert resp.status_code == 401

    async def test_login_inactive_user(
        self, client: AsyncClient, db_session: object, admin_user: object
    ) -> None:
        """Inactive user cannot log in."""
        from app.modules.auth.models import User
        from sqlalchemy import update

        await db_session.execute(  # type: ignore[union-attr]
            update(User).where(User.email == "admin@Sphere.com").values(is_active=False)
        )
        await db_session.flush()  # type: ignore[union-attr]

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@Sphere.com", "password": TEST_PASSWORD},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestRefresh:
    """POST /api/v1/auth/refresh."""

    async def test_refresh_success(
        self, client: AsyncClient, admin_user: object
    ) -> None:
        """Login then refresh returns a new access token."""
        # Login first
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@Sphere.com", "password": TEST_PASSWORD},
        )
        refresh_token = login_resp.json()["refresh_token"]

        # Refresh
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_refresh_with_access_token_fails(
        self, client: AsyncClient, admin_user: object
    ) -> None:
        """Using an access token as a refresh token should fail."""
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@Sphere.com", "password": TEST_PASSWORD},
        )
        access_token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        assert resp.status_code == 401

    async def test_refresh_with_garbage_token_fails(
        self, client: AsyncClient
    ) -> None:
        """Garbage token returns 401."""
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "not-a-valid-jwt"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestMe:
    """GET /api/v1/auth/me."""

    async def test_me_authenticated(
        self, client: AsyncClient, admin_user: object, admin_headers: dict[str, str]
    ) -> None:
        """Authenticated user can fetch their profile."""
        resp = await client.get("/api/v1/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "admin@Sphere.com"
        assert data["role"] == "admin"

    async def test_me_unauthenticated(self, client: AsyncClient) -> None:
        """No token returns 401."""
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_me_bad_token(self, client: AsyncClient) -> None:
        """Invalid token returns 401."""
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestRBAC:
    """Role-based access control tests."""

    async def test_client_user_cannot_create_provider(
        self, client: AsyncClient, client_user: object, client_headers: dict[str, str]
    ) -> None:
        """client_user role is forbidden from write endpoints."""
        resp = await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "deepgram",
                "provider_category": "stt",
                "api_key": "test-key",
            },
            headers=client_headers,
        )
        assert resp.status_code == 403

    async def test_read_only_cannot_create_agent(
        self, client: AsyncClient, read_only_user: object, read_only_headers: dict[str, str]
    ) -> None:
        """read_only role is forbidden from write endpoints."""
        resp = await client.post(
            "/api/v1/agents",
            json={
                "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "name": "TestAgent",
                "type": "single_prompt",
            },
            headers=read_only_headers,
        )
        assert resp.status_code == 403
