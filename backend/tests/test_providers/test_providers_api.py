"""Provider API endpoint tests.

Tests:
- GET  /api/v1/providers (list, filter by category)
- POST /api/v1/providers (create — encryption verified)
- GET  /api/v1/providers/{id} (detail)
- PUT  /api/v1/providers/{id} (update)
- DELETE /api/v1/providers/{id} (delete)
- POST /api/v1/providers/{id}/test (connection test)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import TENANT_1_ID


@pytest.mark.asyncio
class TestProviderCRUD:
    """Provider CRUD operations."""

    async def test_create_provider(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """Admin can create a tenant-scoped provider key."""
        resp = await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "deepgram",
                "provider_category": "stt",
                "api_key": "dg-test-api-key-12345",
                "is_default": False,
                "tenant_id": str(TENANT_1_ID),
                "config": {"model": "nova-3"},
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["provider_name"] == "deepgram"
        assert data["provider_category"] == "stt"
        assert data["is_default"] is False
        assert data["tenant_id"] == str(TENANT_1_ID)
        # API key should NEVER be returned in response
        assert "api_key" not in data
        assert "api_key_encrypted" not in data

    async def test_create_provider_normalizes_family_name_by_category(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """Canonical family names like groq should normalize to category-specific ids."""
        resp = await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "groq",
                "provider_category": "stt",
                "api_key": "groq-test-key",
                "tenant_id": str(TENANT_1_ID),
            },
            headers=admin_headers,
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["provider_name"] == "groq_whisper"
        assert data["provider_family"] == "groq"
        assert data["provider_variant"] == "groq_whisper"

    async def test_admin_create_shared_default_provider(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """Admin can create a shared default provider."""
        resp = await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "openai",
                "provider_category": "llm",
                "api_key": "shared-key",
                "is_default": True,
            },
            headers=admin_headers,
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["is_default"] is True
        assert data["tenant_id"] is None

    async def test_admin_create_non_default_provider_requires_tenant_scope(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """Admin must choose a tenant when creating a non-default provider."""
        resp = await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "deepgram",
                "provider_category": "stt",
                "api_key": "dg-test-api-key-12345",
                "is_default": False,
            },
            headers=admin_headers,
        )

        assert resp.status_code == 403
        assert "choose a tenant" in resp.json()["detail"]["error"]["message"].lower()

    async def test_list_providers(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """List providers returns paginated results."""
        # Create one first
        await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "deepgram",
                "provider_category": "stt",
                "api_key": "dg-key-123",
                "is_default": True,
            },
            headers=admin_headers,
        )

        resp = await client.get("/api/v1/providers", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        assert isinstance(data["providers"], list)

    async def test_list_providers_filter_category(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """Filter providers by category."""
        # Create STT and LLM providers
        await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "deepgram",
                "provider_category": "stt",
                "api_key": "k1",
                "tenant_id": str(TENANT_1_ID),
            },
            headers=admin_headers,
        )
        await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "openai",
                "provider_category": "llm",
                "api_key": "k2",
                "is_default": True,
            },
            headers=admin_headers,
        )

        # Filter by STT
        resp = await client.get(
            "/api/v1/providers?category=stt", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        for p in data["providers"]:
            assert p["provider_category"] == "stt"

    async def test_list_providers_filter_tenant_scope_for_admin(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """Admin can list shared + tenant providers for a specific tenant workspace."""
        await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "openai",
                "provider_category": "llm",
                "api_key": "shared-key",
                "is_default": True,
            },
            headers=admin_headers,
        )
        await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "deepgram",
                "provider_category": "stt",
                "api_key": "tenant-key",
                "tenant_id": str(TENANT_1_ID),
            },
            headers=admin_headers,
        )

        resp = await client.get(
            f"/api/v1/providers?tenant_id={TENANT_1_ID}",
            headers=admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert {provider["tenant_id"] for provider in data["providers"]} == {
            str(TENANT_1_ID),
            None,
        }

    async def test_list_providers_filter_tenant_scope_includes_shared_non_default(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        db_session: object,
        test_tenant: object,
    ) -> None:
        """Tenant-scoped provider lists should include shared non-default providers."""
        from app.modules.providers.service import ProviderService

        await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "inworld",
                "provider_category": "tts",
                "api_key": "shared-default-key",
                "is_default": True,
            },
            headers=admin_headers,
        )
        await ProviderService.create_provider(
            db_session,
            provider_name="sarvam",
            provider_category="tts",
            api_key="shared-non-default-key",
            is_default=False,
            tenant_id=None,
        )
        await db_session.commit()  # type: ignore[union-attr]
        await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "smallest",
                "provider_category": "tts",
                "api_key": "tenant-key",
                "tenant_id": str(TENANT_1_ID),
            },
            headers=admin_headers,
        )

        resp = await client.get(
            f"/api/v1/providers?tenant_id={TENANT_1_ID}&category=tts",
            headers=admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert {provider["provider_name"] for provider in data["providers"]} == {
            "inworld",
            "sarvam",
            "smallest",
        }

    async def test_get_provider_detail(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """Get a single provider by ID."""
        create_resp = await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "openai",
                "provider_category": "llm",
                "api_key": "sk-123",
                "is_default": True,
            },
            headers=admin_headers,
        )
        provider_id = create_resp.json()["id"]

        resp = await client.get(
            f"/api/v1/providers/{provider_id}", headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == provider_id

    async def test_update_provider(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """Update a provider's config."""
        create_resp = await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "deepgram",
                "provider_category": "stt",
                "api_key": "old-key",
                "tenant_id": str(TENANT_1_ID),
            },
            headers=admin_headers,
        )
        provider_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/providers/{provider_id}",
            json={"config": {"model": "nova-3-turbo"}},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["config"]["model"] == "nova-3-turbo"

    async def test_update_provider_normalizes_family_name_for_new_category(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """Updating with a canonical family name should store the category variant."""
        create_resp = await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "groq",
                "provider_category": "llm",
                "api_key": "groq-key",
                "tenant_id": str(TENANT_1_ID),
            },
            headers=admin_headers,
        )
        provider_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/providers/{provider_id}",
            json={"provider_name": "groq", "provider_category": "tts"},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["provider_name"] == "groq_tts"
        assert data["provider_family"] == "groq"
        assert data["provider_category"] == "tts"

    async def test_delete_provider(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """Delete a provider returns 204."""
        create_resp = await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "cartesia",
                "provider_category": "tts",
                "api_key": "cart-key",
                "tenant_id": str(TENANT_1_ID),
            },
            headers=admin_headers,
        )
        provider_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/providers/{provider_id}", headers=admin_headers
        )
        assert resp.status_code == 204

        # Verify gone
        resp = await client.get(
            f"/api/v1/providers/{provider_id}", headers=admin_headers
        )
        assert resp.status_code == 404

    async def test_provider_not_found(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
    ) -> None:
        """Non-existent provider returns 404."""
        resp = await client.get(
            "/api/v1/providers/00000000-0000-0000-0000-000000000000",
            headers=admin_headers,
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestProviderEncryption:
    """Verify API keys are encrypted at rest."""

    async def test_api_key_encrypted_in_db(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        db_session: object,
        test_tenant: object,
    ) -> None:
        """After creating a provider, the DB column contains
        encrypted data, not the plaintext key."""
        from sqlalchemy import select
        from app.modules.providers.models import ProviderKey

        raw_key = "super-secret-api-key-xyz"
        create_resp = await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "deepgram",
                "provider_category": "stt",
                "api_key": raw_key,
                "tenant_id": str(TENANT_1_ID),
            },
            headers=admin_headers,
        )
        provider_id = create_resp.json()["id"]

        # Query DB directly
        result = await db_session.execute(  # type: ignore[union-attr]
            select(ProviderKey).where(ProviderKey.id == provider_id)
        )
        pk = result.scalar_one_or_none()
        assert pk is not None
        # The encrypted value should NOT equal the plaintext
        assert pk.api_key_encrypted != raw_key
        # And should be non-empty
        assert len(pk.api_key_encrypted) > 0
