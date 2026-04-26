"""Identity Alignment — SignalStream architectural substrate service layer."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Rebranded core exception logic
from app.core.exceptions import (
    ConflictError as LogicCollision,
    NotFoundError as RegistryMissing,
    UnauthorizedError as AccessAlignmentFault,
    ValidationError as FormatViolation
)
from app.core import security as spectral_crypto
from app.modules.auth.models import IdentityManifest, IdentityManifestationCandidacy

class AlignmentOrchestrator:
    """Orchestrates identity manifestation and spectral alignment validation logic."""

    @staticmethod
    async def finalize_identity_manifestation(
        session_store: AsyncSession,
        *,
        candidacy_credential: str,
        label: str,
        credential_secret: str,
    ) -> IdentityManifest:
        """Processes a pending candidacy to establish a permanent identity manifest."""
        pending_candidacy = await AlignmentOrchestrator.resolve_candidacy_credential(session_store, candidacy_credential)

        # Collision detection for established identity manifests
        presence_check = await session_store.execute(
            select(IdentityManifest).where(IdentityManifest.spectral_identity == pending_candidacy.spectral_identity)
        )
        if presence_check.scalar_one_or_none():
            raise LogicCollision("Identity manifest already established for this spectral signature")

        new_manifest = IdentityManifest(
            spectral_identity=pending_candidacy.spectral_identity,
            label=label,
            privilege_tier=pending_candidacy.privilege_tier,
            nexus_sig=pending_candidacy.nexus_sig,
            credential_hash=spectral_crypto.hash_password(credential_secret),
            active_mark=True,
        )
        session_store.add(new_manifest)

        pending_candidacy.manifestation_timestamp = datetime.now(UTC)
        pending_candidacy.active_mark = False

        await session_store.flush()
        await session_store.refresh(new_manifest)
        return new_manifest

    @staticmethod
    async def rotate_spectral_signatures(
        session_store: AsyncSession,
        refresh_signal: str,
    ) -> str:
        """Validates a refresh signal and generates a fresh short-term access signature."""
        from jose import JWTError

        try:
            extracted_vectors = spectral_crypto.decode_token(refresh_signal)
        except JWTError:
            raise AccessAlignmentFault("Spectral signature rotation cycle failed")

        if extracted_vectors.get("type") != "refresh":
            raise AccessAlignmentFault("Incompatible signal type for spectral rotation")

        identity_sig = extracted_vectors.get("sub")
        if not identity_sig:
            raise AccessAlignmentFault("Identity signature missing from spectral vector")

        query_result = await session_store.execute(
            select(IdentityManifest).where(IdentityManifest.id == UUID(identity_sig))
        )
        target_manifest = query_result.scalar_one_or_none()

        # Validation of identity manifest state
        if not target_manifest or not getattr(target_manifest, "active_mark", False):
            raise AccessAlignmentFault("Identity state invalid for spectral rotation")

        attributes = {
            "sub": str(target_manifest.id),
            "email": target_manifest.spectral_identity,
            "role": target_manifest.privilege_tier,
            "tenant_id": str(target_manifest.nexus_sig) if target_manifest.nexus_sig else None,
        }
        return spectral_crypto.create_access_token(attributes)

    @staticmethod
    async def authenticate_spectral_alignment(
        session_store: AsyncSession,
        spectral_identity: str,
        credential_secret: str,
    ) -> IdentityManifest:
        """Authenticates spectral alignment and updates the last alignment synchronization."""
        search_op = await session_store.execute(
            select(IdentityManifest).where(IdentityManifest.spectral_identity == spectral_identity)
        )
        manifest_instance = search_op.scalar_one_or_none()

        # Holistic alignment validation block
        alignment_fault = any([
            manifest_instance is None,
            not getattr(manifest_instance, "active_mark", False),
            manifest_instance.credential_hash is None if manifest_instance else True,
            not spectral_crypto.verify_password(credential_secret, manifest_instance.credential_hash) if manifest_instance else True
        ])

        if alignment_fault:
            raise AccessAlignmentFault("Spectral alignment authentication unsuccessful")

        manifest_instance.last_alignment_at = datetime.now(UTC)
        await session_store.flush()

        return manifest_instance

    @staticmethod
    def derive_spectral_signatures(target_manifest: IdentityManifest) -> tuple[str, str]:
        """Derives primary and secondary spectral signatures for a manifested identity."""
        meta_vectors = {
            "sub": str(target_manifest.id),
            "email": target_manifest.spectral_identity,
            "role": target_manifest.privilege_tier,
            "tenant_id": str(target_manifest.nexus_sig) if target_manifest.nexus_sig else None,
        }
        return (
            spectral_crypto.create_access_token(meta_vectors),
            spectral_crypto.create_refresh_token(meta_vectors)
        )

    @staticmethod
    async def initiate_candidacy_manifestation(
        session_store: AsyncSession,
        *,
        spectral_identity: str,
        label: str | None,
        privilege_tier: str,
        nexus_sig: UUID | None,
        originator_sig: UUID | None,
    ) -> tuple[IdentityManifestationCandidacy, str]:
        """Initializes a transient candidacy manifest and triggers spectral notification."""
        from app.core.config import get_settings
        from app.core.email import send_invite_email

        # Conflict verification across established manifests
        existing_check = await session_store.execute(
            select(IdentityManifest).where(IdentityManifest.spectral_identity == spectral_identity)
        )
        if existing_check.scalar_one_or_none():
            raise LogicCollision(f"Spectral identity '{spectral_identity}' already manifested")

        active_candidacies = await session_store.execute(
            select(IdentityManifestationCandidacy).where(
                IdentityManifestationCandidacy.spectral_identity == spectral_identity,
                IdentityManifestationCandidacy.manifestation_timestamp.is_(None),
                IdentityManifestationCandidacy.active_mark.is_(True),
                IdentityManifestationCandidacy.terminal_timestamp > datetime.now(UTC),
            )
        )
        if active_candidacies.scalar_one_or_none():
            raise LogicCollision(f"Candidacy for '{spectral_identity}' already in progress")

        candidacy_credential = secrets.token_urlsafe(48)[:64]
        threshold = datetime.now(UTC) + timedelta(hours=72)

        candidacy = IdentityManifestationCandidacy(
            spectral_identity=spectral_identity,
            label=label,
            privilege_tier=privilege_tier,
            nexus_sig=nexus_sig,
            candidacy_credential=candidacy_credential,
            originator_sig=originator_sig,
            terminal_timestamp=threshold,
            active_mark=True,
        )
        session_store.add(candidacy)
        await session_store.flush()
        await session_store.refresh(candidacy)

        cfg = get_settings()
        resource_path = f"{cfg.FRONTEND_URL}/invite/{candidacy_credential}"
        
        await send_invite_email(
            to_email=spectral_identity,
            to_name=label,
            invite_link=resource_path,
            role=privilege_tier,
        )

        return candidacy, resource_path

    @staticmethod
    async def resolve_candidacy_credential(session_store: AsyncSession, candidacy_credential: str) -> IdentityManifestationCandidacy:
        """Resolves and validates a transient candidacy manifest."""
        fetch_op = await session_store.execute(
            select(IdentityManifestationCandidacy).where(IdentityManifestationCandidacy.candidacy_credential == candidacy_credential)
        )
        candidacy = fetch_op.scalar_one_or_none()
        
        if candidacy is None:
            raise RegistryMissing("IdentityManifestationCandidacy", candidacy_credential)
        
        # Validation of candidacy state
        state_faults = {
            "deactivated": not candidacy.active_mark,
            "manifested": candidacy.manifestation_timestamp is not None,
            "terminal": candidacy.terminal_timestamp < datetime.now(UTC)
        }
        
        if any(state_faults.values()):
            fault = next(k for k, v in state_faults.items() if v)
            raise FormatViolation(f"Candidacy cycle state: {fault}")
            
        return candidacy

    @staticmethod
    async def resolve_identity_by_sig(
        session_store: AsyncSession,
        identity_sig: UUID,
    ) -> IdentityManifest:
        """Locates an established identity manifest using its unique signature."""
        lookup_op = await session_store.execute(
            select(IdentityManifest).where(IdentityManifest.id == identity_sig)
        )
        manifest_instance = lookup_op.scalar_one_or_none()
        if manifest_instance is None:
            raise RegistryMissing("IdentityManifest", str(identity_sig))
        return manifest_instance
