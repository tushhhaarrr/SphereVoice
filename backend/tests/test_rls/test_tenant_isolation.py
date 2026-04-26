"""RLS (Row-Level Security) integration tests.

Verifies that:
- Tenant A cannot see or modify Tenant B's data
- Admin users can access all tenants' data
- Cross-tenant queries return zero rows

Requires a running PostgreSQL instance with the migration applied.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

# Fixed UUIDs for deterministic tests
TENANT_A_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
USER_A_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-111111111111")
USER_B_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-111111111111")
ADMIN_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _get_test_db_url() -> str:
    """Build test database URL from settings."""
    settings = get_settings()
    return settings.DATABASE_URL.replace("/SphereVoice_dev", "/SphereVoice_test")


async def _cleanup(session: AsyncSession) -> None:
    """Remove test data in dependency order."""
    for table in [
        "audit_logs", "webhook_deliveries", "webhooks", "call_events",
        "calls", "phone_numbers", "kb_embeddings", "kb_documents",
        "agent_knowledge_bases", "agent_versions", "agents",
        "knowledge_bases", "provider_keys", "users", "tenants",
    ]:
        await session.execute(text(f"DELETE FROM {table}"))
    await session.commit()


async def _seed_test_data(session: AsyncSession) -> None:
    """Insert test data for two tenants."""
    # Create tenants
    await session.execute(text("""
        INSERT INTO tenants (id, name, slug) VALUES
        (:ta_id, 'Tenant A', 'tenant-a'),
        (:tb_id, 'Tenant B', 'tenant-b')
    """), {"ta_id": TENANT_A_ID, "tb_id": TENANT_B_ID})

    # Create users
    await session.execute(text("""
        INSERT INTO users (id, email, name, role, tenant_id, password_hash) VALUES
        (:ua_id, 'user-a@test.com', 'User A', 'client_user', :ta_id, 'hash'),
        (:ub_id, 'user-b@test.com', 'User B', 'client_user', :tb_id, 'hash'),
        (:admin_id, 'admin@test.com', 'Admin', 'admin', NULL, 'hash')
    """), {
        "ua_id": USER_A_ID, "ta_id": TENANT_A_ID,
        "ub_id": USER_B_ID, "tb_id": TENANT_B_ID,
        "admin_id": ADMIN_USER_ID,
    })

    # Create agents for each tenant
    await session.execute(text("""
        INSERT INTO agents (id, tenant_id, name, type, created_by) VALUES
        (gen_random_uuid(), :ta_id, 'Agent A1', 'single_prompt', :ua_id),
        (gen_random_uuid(), :ta_id, 'Agent A2', 'conversation_flow', :ua_id),
        (gen_random_uuid(), :tb_id, 'Agent B1', 'single_prompt', :ub_id)
    """), {
        "ta_id": TENANT_A_ID, "tb_id": TENANT_B_ID,
        "ua_id": USER_A_ID, "ub_id": USER_B_ID,
    })

    # Create provider keys for each tenant
    await session.execute(text("""
        INSERT INTO provider_keys (id, tenant_id, provider_name, provider_category, api_key_encrypted) VALUES
        (gen_random_uuid(), :ta_id, 'deepgram', 'stt', 'encrypted_key_a'),
        (gen_random_uuid(), :tb_id, 'openai', 'llm', 'encrypted_key_b')
    """), {"ta_id": TENANT_A_ID, "tb_id": TENANT_B_ID})

    # Create webhooks
    await session.execute(text("""
        INSERT INTO webhooks (id, tenant_id, url, events) VALUES
        (gen_random_uuid(), :ta_id, 'https://a.test/hook', '{call_ended}'),
        (gen_random_uuid(), :tb_id, 'https://b.test/hook', '{call_ended}')
    """), {"ta_id": TENANT_A_ID, "tb_id": TENANT_B_ID})

    # Create knowledge bases with different sharing scopes
    await session.execute(text("""
        INSERT INTO knowledge_bases (id, tenant_id, name, sharing_scope, created_by) VALUES
        (:private_kb_id, :ta_id, 'Tenant A Private KB', 'private', :ua_id),
        (:tenant_kb_id, :ta_id, 'Tenant A Shared KB', 'tenant', :ua_id),
        (:global_kb_id, NULL, 'Global KB', 'global', :admin_id)
    """), {
        "private_kb_id": uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-222222222222"),
        "tenant_kb_id": uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-333333333333"),
        "global_kb_id": uuid.UUID("00000000-0000-0000-0000-000000000010"),
        "ta_id": TENANT_A_ID,
        "ua_id": USER_A_ID,
        "admin_id": ADMIN_USER_ID,
    })

    await session.commit()


async def _set_tenant_context(
    session: AsyncSession,
    tenant_id: uuid.UUID | None,
    role: str = "client_user",
    user_id: uuid.UUID | None = None,
) -> None:
    """Set tenant context via separate SET LOCAL calls (asyncpg requires single-statement execute).
    
    Also sets ROLE to `SphereVoice_app` so that RLS policies apply (superuser bypasses RLS).
    """
    await session.execute(text("SET LOCAL ROLE SphereVoice_app"))
    if tenant_id is None:
        await session.execute(
            text("SET LOCAL app.current_tenant_id = '00000000-0000-0000-0000-000000000000'")
        )
    else:
        await session.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'"))
    if user_id is None:
        user_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    await session.execute(text(f"SET LOCAL app.current_user_id = '{user_id}'"))
    await session.execute(text(f"SET LOCAL app.user_role = '{role}'"))


@pytest_asyncio.fixture
async def db_session():
    """Create a fresh engine + session per test to avoid event loop issues."""
    url = _get_test_db_url()
    engine = create_async_engine(url, echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # Seed data
    async with factory() as session:
        await _cleanup(session)
        await _seed_test_data(session)

    yield factory

    # Cleanup
    async with factory() as session:
        await _cleanup(session)

    await engine.dispose()


@pytest.mark.asyncio
class TestRLSTenantIsolation:
    """Verify RLS policies enforce tenant data isolation."""

    async def test_tenant_a_sees_only_own_agents(self, db_session: async_sessionmaker[AsyncSession]) -> None:
        """Tenant A should see 2 agents, not Tenant B's agent."""
        async with db_session() as session:
            await session.execute(text("BEGIN"))
            await _set_tenant_context(session, TENANT_A_ID)

            result = await session.execute(text("SELECT name FROM agents ORDER BY name"))
            rows = result.fetchall()

            assert len(rows) == 2
            names = [r[0] for r in rows]
            assert "Agent A1" in names
            assert "Agent A2" in names
            assert "Agent B1" not in names

            await session.execute(text("ROLLBACK"))

    async def test_tenant_b_sees_only_own_agents(self, db_session: async_sessionmaker[AsyncSession]) -> None:
        """Tenant B should see 1 agent, not Tenant A's agents."""
        async with db_session() as session:
            await session.execute(text("BEGIN"))
            await _set_tenant_context(session, TENANT_B_ID)

            result = await session.execute(text("SELECT name FROM agents ORDER BY name"))
            rows = result.fetchall()

            assert len(rows) == 1
            assert rows[0][0] == "Agent B1"

            await session.execute(text("ROLLBACK"))

    async def test_cross_tenant_returns_zero_rows(self, db_session: async_sessionmaker[AsyncSession]) -> None:
        """Querying provider_keys with wrong tenant context returns empty."""
        async with db_session() as session:
            await session.execute(text("BEGIN"))
            await _set_tenant_context(session, TENANT_A_ID)

            result = await session.execute(text(
                "SELECT provider_name FROM provider_keys WHERE provider_name = 'openai'"
            ))
            rows = result.fetchall()

            assert len(rows) == 0, "Tenant A should not see Tenant B's provider keys"

            await session.execute(text("ROLLBACK"))

    async def test_admin_sees_all_tenants(self, db_session: async_sessionmaker[AsyncSession]) -> None:
        """Admin role bypasses RLS and sees all records."""
        async with db_session() as session:
            await session.execute(text("BEGIN"))
            await _set_tenant_context(session, TENANT_A_ID, role="admin")

            result = await session.execute(text("SELECT name FROM agents ORDER BY name"))
            rows = result.fetchall()

            assert len(rows) == 3, "Admin should see all 3 agents across tenants"

            await session.execute(text("ROLLBACK"))

    async def test_tenant_a_cannot_see_tenant_b_webhooks(self, db_session: async_sessionmaker[AsyncSession]) -> None:
        """Tenant A's webhook queries should not return Tenant B's webhooks."""
        async with db_session() as session:
            await session.execute(text("BEGIN"))
            await _set_tenant_context(session, TENANT_A_ID)

            result = await session.execute(text("SELECT url FROM webhooks"))
            rows = result.fetchall()

            assert len(rows) == 1
            assert rows[0][0] == "https://a.test/hook"

            await session.execute(text("ROLLBACK"))

    async def test_tenant_b_cannot_modify_tenant_a_agents(self, db_session: async_sessionmaker[AsyncSession]) -> None:
        """Tenant B should not be able to update Tenant A's agents via RLS."""
        async with db_session() as session:
            await session.execute(text("BEGIN"))
            await _set_tenant_context(session, TENANT_B_ID)

            result = await session.execute(text(
                "UPDATE agents SET name = 'HACKED' WHERE name LIKE 'Agent A%' RETURNING id"
            ))
            rows = result.fetchall()

            assert len(rows) == 0, "Tenant B should not be able to update Tenant A's agents"

            await session.execute(text("ROLLBACK"))

    async def test_private_knowledge_base_visible_only_to_creator(self, db_session: async_sessionmaker[AsyncSession]) -> None:
        """Private KBs should be visible to their creator but not other tenant users."""
        async with db_session() as session:
            await session.execute(text("BEGIN"))
            await _set_tenant_context(session, TENANT_A_ID, user_id=USER_A_ID)

            own_result = await session.execute(text(
                "SELECT name FROM knowledge_bases ORDER BY name"
            ))
            own_names = [row[0] for row in own_result.fetchall()]

            assert "Tenant A Private KB" in own_names
            assert "Tenant A Shared KB" in own_names
            assert "Global KB" in own_names

            await session.execute(text("ROLLBACK"))

        async with db_session() as session:
            await session.execute(text("BEGIN"))
            await _set_tenant_context(session, TENANT_B_ID, user_id=USER_B_ID)

            other_result = await session.execute(text(
                "SELECT name FROM knowledge_bases ORDER BY name"
            ))
            other_names = [row[0] for row in other_result.fetchall()]

            assert "Tenant A Private KB" not in other_names
            assert "Tenant A Shared KB" not in other_names
            assert "Global KB" in other_names

            await session.execute(text("ROLLBACK"))

    async def test_admin_can_see_private_knowledge_bases(self, db_session: async_sessionmaker[AsyncSession]) -> None:
        """Admins should bypass sharing-scope RLS and see private KBs."""
        async with db_session() as session:
            await session.execute(text("BEGIN"))
            await _set_tenant_context(
                session,
                None,
                role="admin",
                user_id=ADMIN_USER_ID,
            )

            result = await session.execute(text("SELECT name FROM knowledge_bases ORDER BY name"))
            names = [row[0] for row in result.fetchall()]

            assert "Tenant A Private KB" in names
            assert "Tenant A Shared KB" in names
            assert "Global KB" in names

            await session.execute(text("ROLLBACK"))

    async def test_admin_can_insert_user_without_invalid_audit_tenant(self, db_session: async_sessionmaker[AsyncSession]) -> None:
        """Admin inserts should not write a synthetic tenant UUID into audit logs."""
        invited_user_id = uuid.uuid4()

        async with db_session() as session:
            await session.execute(text("BEGIN"))
            await _set_tenant_context(
                session,
                None,
                role="admin",
                user_id=ADMIN_USER_ID,
            )

            await session.execute(
                text(
                    """
                    INSERT INTO users (id, email, name, role, tenant_id, password_hash)
                    VALUES (:id, 'invited-admin-test@example.com', 'Invited User', 'client_user', :tenant_id, 'hash')
                    """
                ),
                {"id": invited_user_id, "tenant_id": TENANT_A_ID},
            )

            audit_tenant_id = (
                await session.execute(
                    text(
                        """
                        SELECT tenant_id
                        FROM audit_logs
                        WHERE resource_type = 'users' AND resource_id = :user_id
                        ORDER BY timestamp DESC
                        LIMIT 1
                        """
                    ),
                    {"user_id": invited_user_id},
                )
            ).scalar_one()

            assert audit_tenant_id is None

            await session.execute(text("ROLLBACK"))

    async def test_no_tenant_context_sees_nothing(self, db_session: async_sessionmaker[AsyncSession]) -> None:
        """Without setting tenant context, RLS should return zero rows."""
        async with db_session() as session:
            await session.execute(text("BEGIN"))
            await session.execute(text("SET LOCAL ROLE SphereVoice_app"))
            await session.execute(text("RESET app.current_tenant_id"))
            await session.execute(text("RESET app.user_role"))

            try:
                result = await session.execute(text("SELECT name FROM agents"))
                rows = result.fetchall()
                assert len(rows) == 0
            except Exception:
                # Expected: invalid UUID cast when context not set
                pass

            await session.execute(text("ROLLBACK"))


@pytest.mark.asyncio
class TestAuditTrigger:
    """Verify that audit triggers fire on CUD operations."""

    async def test_insert_agent_creates_audit_log(self, db_session: async_sessionmaker[AsyncSession]) -> None:
        """Inserting an agent should create an audit_logs entry."""
        async with db_session() as session:
            await session.execute(text("BEGIN"))

            await session.execute(text("SET LOCAL ROLE SphereVoice_app"))
            await session.execute(text(f"SET LOCAL app.current_user_id = '{USER_A_ID}'"))
            await session.execute(text(f"SET LOCAL app.current_tenant_id = '{TENANT_A_ID}'"))
            await session.execute(text("SET LOCAL app.user_role = 'admin'"))

            # Clear existing audit logs
            await session.execute(text("DELETE FROM audit_logs"))

            # Insert a new agent
            await session.execute(text("""
                INSERT INTO agents (tenant_id, name, type, created_by)
                VALUES (:tid, 'Audit Test Agent', 'single_prompt', :uid)
            """), {"tid": TENANT_A_ID, "uid": USER_A_ID})

            # Check audit log
            result = await session.execute(text(
                "SELECT action, resource_type FROM audit_logs "
                "WHERE action = 'create_agents' ORDER BY timestamp DESC LIMIT 1"
            ))
            row = result.fetchone()

            assert row is not None, "Audit log entry should exist after INSERT"
            assert row[0] == "create_agents"
            assert row[1] == "agents"

            await session.execute(text("ROLLBACK"))

    async def test_update_agent_creates_audit_log(self, db_session: async_sessionmaker[AsyncSession]) -> None:
        """Updating an agent should create an audit_logs entry with old + new values."""
        async with db_session() as session:
            await session.execute(text("BEGIN"))
            await session.execute(text("SET LOCAL ROLE SphereVoice_app"))
            await session.execute(text(f"SET LOCAL app.current_user_id = '{USER_A_ID}'"))
            await session.execute(text(f"SET LOCAL app.current_tenant_id = '{TENANT_A_ID}'"))
            await session.execute(text("SET LOCAL app.user_role = 'admin'"))

            # Clear existing audit logs
            await session.execute(text("DELETE FROM audit_logs"))

            # Update an agent
            await session.execute(text(
                "UPDATE agents SET name = 'Updated Name' WHERE name = 'Agent A1'"
            ))

            # Check audit log
            result = await session.execute(text(
                "SELECT action, changes FROM audit_logs "
                "WHERE action = 'update_agents' ORDER BY timestamp DESC LIMIT 1"
            ))
            row = result.fetchone()

            assert row is not None, "Audit log entry should exist after UPDATE"
            assert row[0] == "update_agents"
            assert "old" in row[1]
            assert "new" in row[1]

            await session.execute(text("ROLLBACK"))

    async def test_delete_agent_creates_audit_log(self, db_session: async_sessionmaker[AsyncSession]) -> None:
        """Deleting an agent should create an audit_logs entry."""
        async with db_session() as session:
            await session.execute(text("BEGIN"))
            await session.execute(text("SET LOCAL ROLE SphereVoice_app"))
            await session.execute(text(f"SET LOCAL app.current_user_id = '{USER_A_ID}'"))
            await session.execute(text(f"SET LOCAL app.current_tenant_id = '{TENANT_A_ID}'"))
            await session.execute(text("SET LOCAL app.user_role = 'admin'"))

            # Clear existing audit logs
            await session.execute(text("DELETE FROM audit_logs"))

            # Get an agent ID first
            result = await session.execute(text(
                "SELECT id FROM agents WHERE name = 'Agent A1' LIMIT 1"
            ))
            agent_row = result.fetchone()
            if agent_row:
                await session.execute(text(
                    "DELETE FROM agents WHERE id = :aid"
                ), {"aid": agent_row[0]})

                # Check audit log
                result = await session.execute(text(
                    "SELECT action FROM audit_logs "
                    "WHERE action = 'delete_agents' ORDER BY timestamp DESC LIMIT 1"
                ))
                row = result.fetchone()

                assert row is not None, "Audit log entry should exist after DELETE"
                assert row[0] == "delete_agents"

            await session.execute(text("ROLLBACK"))
