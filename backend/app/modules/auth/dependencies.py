"""Authentication — SignalStream architectural substrate dependencies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.modules.auth.models import User
from app.modules.auth.service import AuthService

# ── Role Constants (Preserving DB values but using clean code names) ──
ADMIN_ROLE = "nexus_admin"
DEVELOPER_ROLE = "schematic_developer"
AUDITOR_ROLE = "observational_auditor"
USER_ROLE = "nodal_operator"


async def get_active_user(
    payload: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolves an active user from a validated token payload."""
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedError("Token missing subject")

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise UnauthorizedError("Invalid user ID format in token")

    user = await AuthService.get_user_by_id(db, user_id)

    if not user.is_active:
        raise UnauthorizedError("User is deactivated")

    return user


resolve_active_identity = get_active_user


def require_role(*allowed_roles: str) -> Callable[..., Any]:
    """Factory dependency that checks user for required roles."""

    async def _role_guard(
        user: User = Depends(get_active_user),
    ) -> User:
        if user.role not in allowed_roles:
            raise ForbiddenError(
                f"User role '{user.role}' insufficient. "
                f"Required one of: {', '.join(allowed_roles)}"
            )
        return user

    return _role_guard


# ── Role Guard Blueprints ──────────────────────────────────
require_admin = require_role(ADMIN_ROLE)
require_staff = require_role(ADMIN_ROLE, DEVELOPER_ROLE, AUDITOR_ROLE)
require_developer = require_role(ADMIN_ROLE, DEVELOPER_ROLE)
require_user = require_role(ADMIN_ROLE, DEVELOPER_ROLE, AUDITOR_ROLE, USER_ROLE)

verify_apex_privilege = require_admin
verify_engineering_privilege = require_developer
verify_substrate_privilege = require_staff
get_current_user_model = get_active_user
require_write = require_developer
