"""DNC (Do Not Call) module — API router."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import set_tenant_context
from app.modules.auth.dependencies import get_current_user_model, require_write
from app.modules.auth.models import User
from app.modules.dnc.schemas import (
    DncCheckRequest,
    DncCheckResponse,
    DncEntryCreate,
    DncEntryListResponse,
    DncEntryResponse,
)
from app.modules.dnc.service import DncService

router = APIRouter(prefix="/dnc", tags=["DNC"])
logger = structlog.get_logger(__name__)


def _tid(explicit: uuid.UUID | None, user: User) -> uuid.UUID:
    tid = explicit or user.tenant_id
    if tid is None:
        from app.core.exceptions import ValidationError

        raise ValidationError("tenant_id is required — pass it as a query parameter")
    return tid


@router.get("", response_model=DncEntryListResponse)
async def list_dnc_entries(
    tenant_id: uuid.UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> DncEntryListResponse:
    """List all DNC entries for the current tenant."""
    tid = _tid(tenant_id, user)
    rows, total = await DncService.list_entries(db, tid, skip=skip, limit=limit)
    return DncEntryListResponse(
        entries=[DncEntryResponse.model_validate(r) for r in rows],
        total=total,
    )


@router.post("", response_model=DncEntryResponse, status_code=201)
async def add_dnc_entry(
    body: DncEntryCreate,
    tenant_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> DncEntryResponse:
    """Add a phone number to the DNC list."""
    tid = _tid(tenant_id, user)
    entry = await DncService.add_entry(db, tid, body, added_by=user.id)
    return DncEntryResponse.model_validate(entry)


@router.post("/check", response_model=DncCheckResponse)
async def check_dnc(
    body: DncCheckRequest,
    tenant_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> DncCheckResponse:
    """Check if a phone number is currently on the DNC list."""
    tid = _tid(tenant_id, user)
    return await DncService.check_number(db, tid, body.phone_number)


@router.get("/{entry_id}", response_model=DncEntryResponse)
async def get_dnc_entry(
    entry_id: uuid.UUID,
    tenant_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> DncEntryResponse:
    """Get a single DNC entry by ID."""
    tid = _tid(tenant_id, user)
    entry = await DncService.get_entry(db, entry_id, tid)
    return DncEntryResponse.model_validate(entry)


@router.delete("/{entry_id}", status_code=204)
async def remove_dnc_entry(
    entry_id: uuid.UUID,
    tenant_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> Response:
    """Remove a phone number from the DNC list."""
    tid = _tid(tenant_id, user)
    await DncService.remove_entry(db, entry_id, tid)
    return Response(status_code=204)
