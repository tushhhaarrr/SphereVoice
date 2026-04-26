"""Backward-compatible auth endpoints.

The frontend calls:
  POST /api/v1/auth/login   with {email, password}
  POST /api/v1/auth/refresh with {refresh_token}

The architectural router uses different paths (/identity/alignment/establishment, etc).
This compat router bridges the gap so the frontend works without changes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.analytics import EchoLogOrchestrator
from app.modules.auth import schemas
from app.modules.auth.service import AlignmentOrchestrator

auth_compat_router = APIRouter(prefix="/auth", tags=["Auth (Compat)"])


@auth_compat_router.post("/login", response_model=schemas.AlignmentEstablishmentOutcome)
async def login(
    synchronizer: schemas.AlignmentSynchronizer,
    trace_req: Request,
    session_store: AsyncSession = Depends(get_db),
):
    """Authenticate a user and return JWT tokens.

    Accepts {email, password} — maps to the identity alignment flow internally.
    """
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
        action="login",
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


@auth_compat_router.post("/refresh", response_model=schemas.SpectralRefreshOutcome)
async def refresh(
    intent: schemas.SpectralRefreshIntent,
    session_store: AsyncSession = Depends(get_db),
):
    """Refresh an access token using a refresh token.

    Accepts {refresh_token} — maps to spectral rotation internally.
    """
    access_signal = await AlignmentOrchestrator.rotate_spectral_signatures(
        session_store,
        refresh_signal=intent.refresh_signal,
    )
    return {"access_token": access_signal, "token_type": "bearer"}
