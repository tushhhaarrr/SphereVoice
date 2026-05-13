"""Campaigns Campaigns — API router."""

from __future__ import annotations

import csv
import io
import json
import uuid
from typing import Any
import structlog
from fastapi import APIRouter, Depends, Query, Response, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import set_tenant_context
from app.modules.auth import get_active_user as get_current_user_model, require_staff as require_write
from app.modules.auth import User
from app.modules.campaigns.schemas import (
    CampaignsManifest as CampaignResponse,
    PropagationTargetManifest as CampaignContactResponse,
    PropagationCampaignListWrapper as CampaignsListWrapper,
    PropagationTargetListWrapper as CampaignContactsListWrapper,
)
from app.modules.campaigns.service import CampaignsOrchestrator as CampaignService

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])
logger = structlog.get_logger(__name__)


@router.get("", response_model=CampaignsListWrapper)
async def list_campaigns(
    tenant_id: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    status: str | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> CampaignsListWrapper:
    if not tenant_id or tenant_id in ("undefined", "null", "") or str(tenant_id).startswith("11111111-"):
        tid = user.tenant_id
    else:
        try:
            tid = uuid.UUID(tenant_id)
        except ValueError:
            tid = user.tenant_id
    try:
        rows, total = await CampaignService.aggregate_propagation_campaigns(db, tid, skip=skip, limit=limit, status=status)
    except Exception:
        rows, total = [], 0
    return CampaignsListWrapper(campaigns=rows, total=total)


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    body: Any, tenant_id: str | None = Query(default=None),
    user: User = Depends(require_write), db: AsyncSession = Depends(set_tenant_context),
) -> CampaignResponse:
    if not tenant_id or tenant_id in ("undefined", "null", "") or str(tenant_id).startswith("11111111-"):
        tid = user.tenant_id
    else:
        try:
            tid = uuid.UUID(tenant_id)
        except ValueError:
            tid = user.tenant_id
    campaign = await CampaignService.provision_propagation_campaign(db, tenant_id=tid, data=body, created_by=user.id)
    return CampaignResponse.model_validate(campaign)


@router.post("/{campaign_id}/start", response_model=CampaignResponse)
async def start_campaign(
    campaign_id: uuid.UUID, tenant_id: str | None = Query(default=None),
    user: User = Depends(require_write), db: AsyncSession = Depends(set_tenant_context),
) -> CampaignResponse:
    if not tenant_id or tenant_id in ("undefined", "null", "") or str(tenant_id).startswith("11111111-"):
        tid = user.tenant_id
    else:
        try:
            tid = uuid.UUID(tenant_id)
        except ValueError:
            tid = user.tenant_id
    campaign = await CampaignService.activate_propagation_cycle(db, campaign_id, tid)
    from app.workers.celery_app import celery_app
    celery_app.send_task("app.modules.campaigns.workers.orchestrate_propagation_cycle", args=[str(campaign_id)])
    return CampaignResponse.model_validate(campaign)
