"""Authentication Module — SignalStream substrate exports."""

from app.modules.auth.dependencies import (
    get_active_user,
    require_role,
    require_admin,
    require_developer,
    require_staff,
    require_user,
)
from app.modules.auth.models import User, Tenant, UserInvitation
from app.modules.auth.service import AuthService

resolve_active_identity = get_active_user
verify_engineering_privilege = require_developer
verify_substrate_privilege = require_staff
get_current_user_model = get_active_user
require_write = require_developer

__all__ = [
    "AuthService",
    "User",
    "Tenant",
    "UserInvitation",
    "get_active_user",
    "resolve_active_identity",
    "verify_engineering_privilege",
    "verify_substrate_privilege",
    "get_current_user_model",
    "require_write",
    "require_role",
    "require_admin",
    "require_developer",
    "require_staff",
    "require_user",
]
