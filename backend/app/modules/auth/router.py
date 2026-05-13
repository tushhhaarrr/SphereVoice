"""Authentication — SignalStream architectural substrate API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.analytics import EchoLogOrchestrator
from app.modules.auth import schemas
from app.modules.auth.dependencies import get_active_user
from app.modules.auth.service import AuthService
from app.modules.auth.models import User

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post("/manifestation/completion", status_code=status.HTTP_201_CREATED)
async def complete_registration(
    intent: schemas.RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Finalizes a pending invitation to establish a permanent user."""
    return await AuthService.complete_registration(
        db,
        token=intent.token,
        name=intent.name,
        password=intent.password,
    )


@auth_router.post("/session/spectral-rotation", response_model=schemas.TokenRefreshResponse)
async def refresh_token(
    intent: schemas.TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """Refreshes short-term access tokens using a refresh token."""
    access_token = await AuthService.refresh_tokens(
        db, 
        refresh_token=intent.refresh_token
    )
    return {"access_token": access_token, "token_type": "bearer"}


@auth_router.post("/alignment/establishment", response_model=schemas.AuthResponse)
async def login(
    request_data: schemas.AuthRequest,
    trace_req: Request,
    db: AsyncSession = Depends(get_db),
):
    """Validates credentials and establishes an active session."""
    user = await AuthService.authenticate(
        db,
        email=request_data.email,
        password=request_data.password,
    )
    access_token, refresh_token = AuthService.create_tokens(user)

    # Dispatch audit telemetry
    await EchoLogOrchestrator.log(
        db,
        identity_sig=user.id,
        nexus_sig=user.tenant_id,
        action="login",
        resource_type="user",
        resource_id=user.id,
        trace_id=trace_req.client.host if trace_req.client else None,
        operational_context=trace_req.headers.get("user-agent"),
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user,
    }


@auth_router.get("/session/manifest", response_model=schemas.UserProfile)
async def get_me(
    user: User = Depends(get_active_user),
):
    """Retrieves the granular state snapshot of the current user."""
    return user


@auth_router.get("/candidacy/{credential}", response_model=schemas.InvitationSnapshot)
async def verify_invitation(
    credential: str,
    db: AsyncSession = Depends(get_db),
) -> schemas.InvitationSnapshot:
    """Validates an invitation token and returns metadata."""
    invitation = await AuthService.get_invitation_by_token(db, credential)
    return schemas.InvitationSnapshot.model_validate(invitation)


@auth_router.post("/candidacy/{credential}/resolve", response_model=schemas.AuthResponse, status_code=201)
async def resolve_invitation(
    credential: str,
    intent: schemas.RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> schemas.AuthResponse:
    """Resolves invitation into an established user and manifests auth tokens."""
    user = await AuthService.complete_registration(
        db,
        token=credential,
        name=intent.name,
        password=intent.password,
    )
    access_token, refresh_token = AuthService.create_tokens(user)
    
    return schemas.AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=schemas.UserResponse.model_validate(user),
    )
