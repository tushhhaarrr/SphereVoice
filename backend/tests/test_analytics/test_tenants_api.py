"""Tenant management API tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.modules.agents.models import Agent
from app.modules.auth.models import Tenant, User
from app.modules.calls.models import Call
from app.modules.phone_numbers.models import PhoneNumber
from tests.conftest import TENANT_1_ID, TENANT_2_ID


@pytest.mark.asyncio
class TestTenantManagement:
    """Admin tenant CRUD and summary endpoints."""

    async def test_admin_can_create_tenant(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/api/v1/analytics/tenants",
            json={
                "name": "Northwind Health",
                "status": "active",
                "metadata": {"plan": "enterprise"},
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Northwind Health"
        assert data["slug"] == "northwind-health"
        assert data["status"] == "active"
        assert data["metadata"]["plan"] == "enterprise"
        assert data["summary"]["user_count"] == 0

    async def test_list_tenants_returns_summary_counts(
        self,
        client: AsyncClient,
        db_session: object,
        admin_headers: dict[str, str],
        admin_user: object,
        test_tenant: Tenant,
    ) -> None:
        tenant_2 = Tenant(id=TENANT_2_ID, name="Other Corp", slug="other-corp")
        db_session.add(tenant_2)  # type: ignore[union-attr]

        client_user = User(
            email="ops@testcorp.com",
            name="Ops User",
            role="client_user",
            tenant_id=TENANT_1_ID,
            password_hash="hash",
            is_active=True,
        )
        db_session.add(client_user)  # type: ignore[union-attr]

        agent = Agent(
            tenant_id=TENANT_1_ID,
            name="Tenant 1 Agent",
            type="single_prompt",
        )
        db_session.add(agent)  # type: ignore[union-attr]
        await db_session.flush()  # type: ignore[union-attr]

        phone_number = PhoneNumber(
            tenant_id=TENANT_1_ID,
            phone_number="+15555550123",
            provider_name="twilio",
        )
        db_session.add(phone_number)  # type: ignore[union-attr]
        await db_session.flush()  # type: ignore[union-attr]

        call = Call(
            tenant_id=TENANT_1_ID,
            agent_id=agent.id,
            phone_number_id=phone_number.id,
            from_number="+15555550000",
            to_number="+15555550123",
            direction="inbound",
            started_at=datetime.now(UTC),
            status="completed",
            total_cost=Decimal("0.25"),
        )
        db_session.add(call)  # type: ignore[union-attr]
        await db_session.commit()  # type: ignore[union-attr]

        resp = await client.get("/api/v1/analytics/tenants", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        tenant = next(item for item in data["tenants"] if item["id"] == str(TENANT_1_ID))
        assert tenant["summary"] == {
            "user_count": 1,
            "agent_count": 1,
            "call_count": 1,
            "phone_number_count": 1,
        }

    async def test_get_tenant_returns_detail(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        test_tenant: Tenant,
    ) -> None:
        resp = await client.get(
            f"/api/v1/analytics/tenants/{TENANT_1_ID}", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(TENANT_1_ID)
        assert data["name"] == "Test Corp"

    async def test_admin_can_update_tenant(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        test_tenant: Tenant,
    ) -> None:
        resp = await client.put(
            f"/api/v1/analytics/tenants/{TENANT_1_ID}",
            json={
                "name": "Updated Test Corp",
                "slug": "updated-test-corp",
                "status": "suspended",
                "metadata": {"plan": "startup"},
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Test Corp"
        assert data["slug"] == "updated-test-corp"
        assert data["status"] == "suspended"
        assert data["metadata"]["plan"] == "startup"

    async def test_duplicate_slug_returns_conflict(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        test_tenant: Tenant,
        test_tenant_2: Tenant,
    ) -> None:
        resp = await client.put(
            f"/api/v1/analytics/tenants/{TENANT_2_ID}",
            json={"slug": "test-corp"},
            headers=admin_headers,
        )
        assert resp.status_code == 409

    async def test_non_admin_cannot_manage_tenants(
        self,
        client: AsyncClient,
        developer_headers: dict[str, str],
    ) -> None:
        resp = await client.get("/api/v1/analytics/tenants", headers=developer_headers)
        assert resp.status_code == 403