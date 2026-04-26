"""Agent API endpoint tests.

Tests:
- GET    /api/v1/agents (list, pagination)
- POST   /api/v1/agents (create)
- GET    /api/v1/agents/{id} (detail)
- PUT    /api/v1/agents/{id} (update)
- DELETE /api/v1/agents/{id} (delete)
- POST   /api/v1/agents/{id}/publish (versioning)
- GET    /api/v1/agents/{id}/versions (version history)
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.conftest import TENANT_1_ID, TENANT_2_ID


AGENT_PAYLOAD = {
    "tenant_id": str(TENANT_1_ID),
    "name": "Test Agent",
    "type": "single_prompt",
    "config": {"system_prompt": "You are a helpful agent."},
    "language": "en-US",
}


@pytest.mark.asyncio
class TestAgentCRUD:
    """Agent CRUD operations."""

    async def test_create_agent(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """Admin can create an agent."""
        resp = await client.post(
            "/api/v1/agents", json=AGENT_PAYLOAD, headers=admin_headers
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Agent"
        assert data["type"] == "single_prompt"
        assert data["status"] == "draft"
        assert data["version"] == 0
        assert data["tenant_id"] == str(TENANT_1_ID)

    async def test_list_agents(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """List agents returns paginated results."""
        # Create two agents
        await client.post(
            "/api/v1/agents", json=AGENT_PAYLOAD, headers=admin_headers
        )
        await client.post(
            "/api/v1/agents",
            json={**AGENT_PAYLOAD, "name": "Agent 2"},
            headers=admin_headers,
        )

        resp = await client.get("/api/v1/agents", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        assert data["page"] == 1
        assert isinstance(data["agents"], list)

    async def test_list_agents_for_tenant_workspace(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
        test_tenant_2: object,
    ) -> None:
        """Admin workspace filter only returns agents for the selected tenant."""
        await client.post(
            "/api/v1/agents",
            json=AGENT_PAYLOAD,
            headers=admin_headers,
        )
        await client.post(
            "/api/v1/agents",
            json={**AGENT_PAYLOAD, "tenant_id": str(TENANT_2_ID), "name": "Tenant 2 Agent"},
            headers=admin_headers,
        )

        resp = await client.get(
            f"/api/v1/agents?tenant_id={TENANT_1_ID}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        names = {agent["name"] for agent in data["agents"]}
        assert "Test Agent" in names
        assert "Tenant 2 Agent" not in names


    async def test_get_agent_detail(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """Get a single agent by ID."""
        create_resp = await client.post(
            "/api/v1/agents", json=AGENT_PAYLOAD, headers=admin_headers
        )
        agent_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/agents/{agent_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == agent_id

    async def test_update_agent(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """Update agent name and config."""
        create_resp = await client.post(
            "/api/v1/agents", json=AGENT_PAYLOAD, headers=admin_headers
        )
        agent_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/agents/{agent_id}",
            json={"name": "Renamed Agent", "llm_model": "gpt-4o"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Renamed Agent"
        assert data["llm_model"] == "gpt-4o"

    async def test_delete_agent(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """Delete agent returns 204."""
        create_resp = await client.post(
            "/api/v1/agents", json=AGENT_PAYLOAD, headers=admin_headers
        )
        agent_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/agents/{agent_id}", headers=admin_headers
        )
        assert resp.status_code == 204

        # Verify gone
        resp = await client.get(f"/api/v1/agents/{agent_id}", headers=admin_headers)
        assert resp.status_code == 404

    async def test_agent_not_found(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
    ) -> None:
        """Non-existent agent returns 404."""
        resp = await client.get(
            "/api/v1/agents/00000000-0000-0000-0000-000000000000",
            headers=admin_headers,
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestAgentVersioning:
    """Agent publish + version history."""

    async def test_publish_agent(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """Publishing an agent creates a version and bumps version counter."""
        create_resp = await client.post(
            "/api/v1/agents", json=AGENT_PAYLOAD, headers=admin_headers
        )
        agent_id = create_resp.json()["id"]
        assert create_resp.json()["version"] == 0

        # Publish
        resp = await client.post(
            f"/api/v1/agents/{agent_id}/publish", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 1
        assert data["status"] == "published"
        assert data["published_at"] is not None

    async def test_list_versions(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        test_tenant: object,
    ) -> None:
        """Get version history after publishing twice."""
        create_resp = await client.post(
            "/api/v1/agents", json=AGENT_PAYLOAD, headers=admin_headers
        )
        agent_id = create_resp.json()["id"]

        # Publish twice
        await client.post(f"/api/v1/agents/{agent_id}/publish", headers=admin_headers)
        await client.post(f"/api/v1/agents/{agent_id}/publish", headers=admin_headers)

        resp = await client.get(
            f"/api/v1/agents/{agent_id}/versions", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["versions"]) == 2
        # Newest first
        assert data["versions"][0]["version"] == 2
        assert data["versions"][1]["version"] == 1

    async def test_published_runtime_snapshot_ignores_newer_draft_changes(
        self,
        client: AsyncClient,
        admin_user: object,
        admin_headers: dict[str, str],
        db_session: object,
        test_tenant: object,
    ) -> None:
        """Runtime should use the latest published snapshot, not newer unsaved draft edits."""
        from app.modules.pipeline.orchestrator import CallOrchestrator

        stt_provider_resp = await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "deepgram",
                "provider_category": "stt",
                "api_key": "dg-runtime-key",
                "tenant_id": str(TENANT_1_ID),
            },
            headers=admin_headers,
        )
        llm_provider_resp = await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "openai",
                "provider_category": "llm",
                "api_key": "openai-runtime-key",
                "tenant_id": str(TENANT_1_ID),
            },
            headers=admin_headers,
        )
        tts_provider_resp = await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "cartesia",
                "provider_category": "tts",
                "api_key": "cartesia-runtime-key",
                "tenant_id": str(TENANT_1_ID),
            },
            headers=admin_headers,
        )

        published_stt_provider_id = stt_provider_resp.json()["id"]
        published_llm_provider_id = llm_provider_resp.json()["id"]
        published_tts_provider_id = tts_provider_resp.json()["id"]

        draft_stt_provider_resp = await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "assemblyai",
                "provider_category": "stt",
                "api_key": "assemblyai-runtime-key",
                "tenant_id": str(TENANT_1_ID),
            },
            headers=admin_headers,
        )
        draft_llm_provider_resp = await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "groq",
                "provider_category": "llm",
                "api_key": "groq-runtime-key",
                "tenant_id": str(TENANT_1_ID),
            },
            headers=admin_headers,
        )
        draft_tts_provider_resp = await client.post(
            "/api/v1/providers",
            json={
                "provider_name": "inworld",
                "provider_category": "tts",
                "api_key": "inworld-runtime-key",
                "tenant_id": str(TENANT_1_ID),
            },
            headers=admin_headers,
        )

        create_resp = await client.post(
            "/api/v1/agents",
            json={
                **AGENT_PAYLOAD,
                "name": "Published Agent",
                "config": {"prompt": "Published prompt"},
                "stt_provider_id": published_stt_provider_id,
                "llm_provider_id": published_llm_provider_id,
                "tts_provider_id": published_tts_provider_id,
            },
            headers=admin_headers,
        )
        agent_id = create_resp.json()["id"]

        publish_resp = await client.post(
            f"/api/v1/agents/{agent_id}/publish",
            headers=admin_headers,
        )
        assert publish_resp.status_code == 200

        draft_resp = await client.put(
            f"/api/v1/agents/{agent_id}",
            json={
                "name": "Draft Agent",
                "config": {"prompt": "Draft prompt"},
                "stt_provider_id": draft_stt_provider_resp.json()["id"],
                "llm_provider_id": draft_llm_provider_resp.json()["id"],
                "tts_provider_id": draft_tts_provider_resp.json()["id"],
            },
            headers=admin_headers,
        )
        assert draft_resp.status_code == 200

        runtime_agent = await CallOrchestrator(db_session)._get_agent(agent_id)
        assert runtime_agent is not None
        assert runtime_agent.name == "Published Agent"
        assert runtime_agent.config["prompt"] == "Published prompt"
        assert str(runtime_agent.stt_provider_id) == published_stt_provider_id
        assert str(runtime_agent.llm_provider_id) == published_llm_provider_id
        assert str(runtime_agent.tts_provider_id) == published_tts_provider_id
