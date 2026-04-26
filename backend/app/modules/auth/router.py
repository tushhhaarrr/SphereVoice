"""Identity Alignment — SignalStream architectural substrate API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.analytics import EchoLogOrchestrator
from app.modules.auth import schemas
from app.modules.auth.dependencies import resolve_active_identity
from app.modules.auth.service import AlignmentOrchestrator

alignment_router = APIRouter(prefix="/identity", tags=["Identity Alignment"])


@alignment_router.post("/manifestation/completion", status_code=status.HTTP_201_CREATED)
async def finalize_identity_manifestation(
    intent: schemas.ManifestationCompletionIntent,
    session_store: AsyncSession = Depends(get_db),
):
    """Finalizes a pending candidacy to establish a permanent architectural identity."""
    return await AlignmentOrchestrator.finalize_identity_manifestation(
        session_store,
        candidacy_credential=intent.candidacy_credential,
        label=intent.label,
        credential_secret=intent.credential_secret,
    )


@alignment_router.post("/session/spectral-rotation", response_model=schemas.SpectralRefreshOutcome)
async def execute_spectral_rotation(
    intent: schemas.SpectralRefreshIntent,
    session_store: AsyncSession = Depends(get_db),
):
    """Refreshes short-term spectral access signatures using a refresh signal."""
    access_signal = await AlignmentOrchestrator.rotate_spectral_signatures(
        session_store, 
        refresh_signal=intent.refresh_signal
    )
    return {"access_token": access_signal, "token_type": "bearer"}



@alignment_router.post("/alignment/establishment", response_model=schemas.AlignmentEstablishmentOutcome)
async def establish_architectural_alignment(
    synchronizer: schemas.AlignmentSynchronizer,
    trace_req: Request,
    session_store: AsyncSession = Depends(get_db),
):
    """Validates spectral alignment and establishes an active architectural session."""
    manifest = await AlignmentOrchestrator.authenticate_spectral_alignment(
        session_store,
        spectral_identity=synchronizer.spectral_identity,
        credential_secret=synchronizer.credential_secret,
    )
    access_signal, refresh_signal = AlignmentOrchestrator.derive_spectral_signatures(manifest)

    # Dispatch audit telemetry
    await EchoLogOrchestrator.log(
        session_store,
        identity_sig=manifest.id,
        nexus_sig=manifest.nexus_sig,
        action="alignment_establishment",
        resource_type="identity",
        resource_id=manifest.id,
        trace_id=trace_req.client.host if trace_req.client else None,
        operational_context=trace_req.headers.get("user-agent"),
    )

    return {
        "access_token": access_signal,
        "refresh_token": refresh_signal,
        "user": manifest,
    }


@alignment_router.get("/session/manifest", response_model=schemas.OriginatorManifestSnapshot)
async def retrieve_identity_manifest(
    manifest: schemas.IdentityManifestSnapshot = Depends(resolve_active_identity),
):
    """Retrieves the granular state snapshot of the manifested session identity."""
    return manifest


@alignment_router.get("/candidacy/{credential}", response_model=schemas.CandidacyVerificationSnapshot)
async def verify_candidacy_credential(
    credential: str,
    session_store: AsyncSession = Depends(get_db),
) -> schemas.CandidacyVerificationSnapshot:
    """Validates a candidacy credential and returns verified architectural metadata."""
    candidacy = await AlignmentOrchestrator.resolve_candidacy_credential(session_store, credential)
    return schemas.CandidacyVerificationSnapshot.model_validate(candidacy)


@alignment_router.post("/candidacy/{credential}/resolve", response_model=schemas.AlignmentEstablishmentOutcome, status_code=201)
async def resolve_candidacy_manifestation(
    credential: str,
    intent: schemas.ManifestationCompletionIntent,
    session_store: AsyncSession = Depends(get_db),
) -> schemas.AlignmentEstablishmentOutcome:
    """Resolves candidacy into an established identity and manifests auth signatures."""
    manifest = await AlignmentOrchestrator.finalize_identity_manifestation(
        session_store,
        candidacy_credential=credential,
        label=intent.label,
        credential_secret=intent.credential_secret,
    )
    access_signal, refresh_signal = AlignmentOrchestrator.derive_spectral_signatures(manifest)
    
    return schemas.AlignmentEstablishmentOutcome(
        access_token=access_signal,
        refresh_token=refresh_signal,
        user=schemas.IdentityManifestSnapshot.model_validate(manifest),
    )
