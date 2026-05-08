"""FastAPI dependencies shared across all modules.

Provides:
- ``get_db``: Async database session (re-exported from database.py)
- ``get_current_user``: Extract and validate JWT from request
- ``get_current_tenant_id``: Extract tenant_id from current user context
- ``set_tenant_context``: Set RLS context (tenant_id + role) on DB session
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db as _get_db
from app.core.security import decode_token

# Whitelist for role values to prevent SQL injection in SET LOCAL
_VALID_ROLES = {"admin", "developer", "read_only", "client_user"}
# UUID v4 pattern for tenant_id validation
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Re-export for convenience
get_db = _get_db

# Bearer token scheme — auto_error=False so we return 401 (not 403)
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict[str, Any]:
    """Decode JWT Bearer token and return the payload.

    Raises 401 if token is missing, expired, or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate token type — reject refresh tokens
    if payload.get("type") == "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh tokens cannot be used for API access",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_current_tenant_id(
    user: dict[str, Any] = Depends(get_current_user),
) -> str | None:
    """Extract tenant_id from the JWT payload.

    Returns None for admin/employee users (who see all tenants).
    """
    return user.get("tenant_id")


async def get_current_role(
    user: dict[str, Any] = Depends(get_current_user),
) -> str:
    """Extract role from the JWT payload."""
    return user.get("role", "")


async def get_current_user_id(
    user: dict[str, Any] = Depends(get_current_user),
) -> str:
    """Extract the authenticated user ID from the JWT payload."""
    user_id = user.get("sub")
    if not isinstance(user_id, str) or not _UUID_RE.match(user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
        )
    return user_id


async def set_tenant_context(
    db: AsyncSession = Depends(get_db),  # type: ignore[assignment]
    tenant_id: str | None = Depends(get_current_tenant_id),
    role: str = Depends(get_current_role),
    user_id: str = Depends(get_current_user_id),
) -> AsyncSession:
    """Set the RLS tenant context on the database session.

    Executes SET LOCAL for ``app.current_tenant_id``,
    ``app.current_user_id``, and ``app.user_role`` so that PostgreSQL
    RLS policies can filter queries automatically.

    Also sets ROLE to the configured DB_APP_ROLE so RLS is enforced
    (superuser bypasses RLS). If DB_APP_ROLE is empty or the role
    doesn't exist, this step is skipped gracefully.
    """
    # Switch to application role so RLS is enforced (if configured)
    from app.core.config import get_settings as _cfg
    _app_role = _cfg().DB_APP_ROLE
    if _app_role:
        try:
            await db.execute(text(f"SET LOCAL ROLE {_app_role}"))
        except Exception:
            # Role doesn't exist in this Postgres instance — skip RLS enforcement
            pass

    if tenant_id:
        # Validate UUID format before interpolation (asyncpg doesn't support
        # parameterized SET LOCAL — the driver converts :param to $1 which
        # PostgreSQL rejects for SET commands).
        if not _UUID_RE.match(tenant_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid tenant_id in token",
            )
        await db.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'"))
    else:
        # Admin/employee — set nil UUID so RLS UUID casts stay valid;
        # audit triggers normalize this sentinel back to NULL.
        await db.execute(
            text("SET LOCAL app.current_tenant_id = '00000000-0000-0000-0000-000000000000'")
        )

    # Validate role against whitelist before interpolation
    if role not in _VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid role in token",
        )
    await db.execute(text(f"SET LOCAL app.current_user_id = '{user_id}'"))
    await db.execute(text(f"SET LOCAL app.user_role = '{role}'"))

    return db
