"""Identity Alignment Module — SignalStream substrate exports."""

from app.modules.auth.dependencies import (
    audit_operational_privileges,
    resolve_active_identity,
    verify_apex_privilege,
    verify_engineering_privilege,
    verify_substrate_privilege,
)
from app.modules.auth.models import IdentityManifest, NexusRegistry
from app.modules.auth.service import AlignmentOrchestrator

__all__ = [
    "AlignmentOrchestrator",
    "IdentityManifest",
    "NexusRegistry",
    "audit_operational_privileges",
    "resolve_active_identity",
    "verify_apex_privilege",
    "verify_engineering_privilege",
    "verify_substrate_privilege",
]
