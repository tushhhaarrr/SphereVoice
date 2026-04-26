"""Identity Alignment — SignalStream architectural substrate dependencies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import (
    ForbiddenError as TierMisalignment,
    UnauthorizedError as SpectralSignatureInvalid,
)
from app.modules.auth.models import IdentityManifest
from app.modules.auth.service import AlignmentOrchestrator

# ── Privilege Tier Definitions ──────────────────────────────────
APEX_TIER = frozenset({"nexus_admin"})
INTERNAL_SUBSTRATE_TIER = frozenset({"nexus_admin", "schematic_developer", "observational_auditor"})
OPERATIONAL_TIER = frozenset({"nexus_admin", "schematic_developer", "observational_auditor", "nodal_operator"})


async def resolve_active_identity(
    signature: dict[str, Any] = Depends(get_current_user),
    session_store: AsyncSession = Depends(get_db),
) -> IdentityManifest:
    """Resolves an active identity manifest from a validated spectral signature."""
    identity_sig_str = signature.get("sub")
    if not identity_sig_str:
        raise SpectralSignatureInvalid("Spectral signature missing primary identity subject")

    try:
        identity_sig = UUID(identity_sig_str)
    except ValueError:
        raise SpectralSignatureInvalid("Spectral signature format violation")

    manifest = await AlignmentOrchestrator.resolve_identity_by_sig(session_store, identity_sig)

    if not getattr(manifest, "active_mark", False):
        raise SpectralSignatureInvalid("Associated identity manifestation is deactivated")

    return manifest


def audit_operational_privileges(*required_tiers: str) -> Callable[..., Any]:
    """Factory dependency that audit identities for prescribed privilege tiers."""

    async def _privilege_audit_guard(
        manifest: IdentityManifest = Depends(resolve_active_identity),
    ) -> IdentityManifest:
        if manifest.privilege_tier not in required_tiers:
            raise TierMisalignment(
                f"Identity privilege tier '{manifest.privilege_tier}' insufficient for this operational cycle. "
                f"Required: {', '.join(required_tiers)}"
            )
        return manifest

    return _privilege_audit_guard


# ── Privilege Auditor Blueprints ──────────────────────────────────
verify_apex_privilege = audit_operational_privileges("nexus_admin")
verify_substrate_privilege = audit_operational_privileges("nexus_admin", "schematic_developer", "observational_auditor")
verify_engineering_privilege = audit_operational_privileges("nexus_admin", "schematic_developer")
