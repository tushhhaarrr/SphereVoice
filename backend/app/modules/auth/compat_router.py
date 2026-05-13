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
from app.modules.auth.service import AuthService

auth_compat_router = APIRouter(prefix="/auth/compat", tags=["Auth (Compat)"])


@auth_compat_router.post("/login", response_model=schemas.AuthResponse)
async def login(
    synchronizer: schemas.AuthRequest,
    trace_req: Request,
    session_store: AsyncSession = Depends(get_db),
):
    """Authenticate a user and return JWT tokens.

    Accepts {email, password} — maps to the identity alignment flow internally.
    """
    manifest = await AuthService.authenticate(
        session_store,
        email=synchronizer.email,
        password=synchronizer.password,
    )
    access_signal, refresh_signal = AuthService.create_tokens(manifest)

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


@auth_compat_router.post("/refresh", response_model=schemas.TokenRefreshResponse)
async def refresh(
    intent: schemas.TokenRefreshRequest,
    session_store: AsyncSession = Depends(get_db),
):
    """Refresh an access token using a refresh token.

    Accepts {refresh_token} — maps to spectral rotation internally.
    """
    access_signal = await AuthService.refresh_tokens(
        session_store,
        refresh_token=intent.refresh_token,
    )
    return {"access_token": access_signal, "token_type": "bearer"}
