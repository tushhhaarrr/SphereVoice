"""Tests for shared authentication and RLS dependencies."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.core.dependencies import get_current_user_id, set_tenant_context


@pytest.mark.asyncio
class TestTenantContext:
    """Verify request-scoped RLS context setup."""

    async def test_set_tenant_context_sets_user_id_for_rls(self) -> None:
        """The dependency should set tenant, user, and role context values."""
        db = AsyncMock()
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        result = await set_tenant_context(
            db=db,
            tenant_id=tenant_id,
            role="client_user",
            user_id=user_id,
        )

        assert result is db
        executed_sql = [str(call.args[0]) for call in db.execute.await_args_list]
        assert any("SET LOCAL ROLE SphereVoice_app" in sql for sql in executed_sql)
        assert any(tenant_id in sql for sql in executed_sql)
        assert any("app.current_user_id" in sql and user_id in sql for sql in executed_sql)
        assert any("SET LOCAL app.user_role = 'client_user'" in sql for sql in executed_sql)

    async def test_get_current_user_id_rejects_invalid_subject(self) -> None:
        """Invalid user IDs should fail before the DB context is mutated."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(user={"sub": "not-a-uuid"})

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid user ID in token"

    async def test_set_tenant_context_uses_nil_uuid_for_admin_users(self) -> None:
        """Admin requests should use the sentinel tenant UUID for RLS-safe casts."""
        db = AsyncMock()
        user_id = str(uuid.uuid4())

        await set_tenant_context(
            db=db,
            tenant_id=None,
            role="admin",
            user_id=user_id,
        )

        executed_sql = [str(call.args[0]) for call in db.execute.await_args_list]
        assert any("00000000-0000-0000-0000-000000000000" in sql for sql in executed_sql)
        assert any("app.current_user_id" in sql and user_id in sql for sql in executed_sql)
        assert any("SET LOCAL app.user_role = 'admin'" in sql for sql in executed_sql)