"""Tool Registry module — API router."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import set_tenant_context
from app.modules.auth.dependencies import get_current_user_model, require_write
from app.modules.auth.models import User
from app.modules.tool_registry.schemas import (
    AgentToolBind,
    AgentToolResponse,
    TenantToolCreate,
    TenantToolListResponse,
    TenantToolResponse,
    TenantToolUpdate,
)
from app.modules.tool_registry.service import ToolService

router = APIRouter(prefix="/tools", tags=["Tool Registry"])
logger = structlog.get_logger(__name__)


def _tid(explicit: uuid.UUID | None, user: User) -> uuid.UUID:
    tid = explicit or user.tenant_id
    if tid is None:
        from app.core.exceptions import ValidationError

        raise ValidationError("tenant_id is required — pass it as a query parameter")
    return tid


# ============================================================================
# Tenant Tool CRUD
# ============================================================================


@router.get("", response_model=TenantToolListResponse)
async def list_tools(
    tenant_id: uuid.UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    category: str | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> TenantToolListResponse:
    """List all tenant tools for the current tenant."""
    tid = _tid(tenant_id, user)
    rows, total = await ToolService.list_tools(db, tid, skip=skip, limit=limit, category=category)
    return TenantToolListResponse(
        items=[TenantToolResponse.model_validate(r) for r in rows],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=TenantToolResponse, status_code=201)
async def create_tool(
    body: TenantToolCreate,
    tenant_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> TenantToolResponse:
    """Create a new tenant tool."""
    tid = _tid(tenant_id, user)
    tool = await ToolService.create_tool(db, tid, body)
    return TenantToolResponse.model_validate(tool)


@router.get("/{tool_id}", response_model=TenantToolResponse)
async def get_tool(
    tool_id: uuid.UUID,
    tenant_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> TenantToolResponse:
    """Get a single tenant tool by ID."""
    tid = _tid(tenant_id, user)
    tool = await ToolService.get_tool(db, tool_id, tid)
    return TenantToolResponse.model_validate(tool)


@router.patch("/{tool_id}", response_model=TenantToolResponse)
async def update_tool(
    tool_id: uuid.UUID,
    body: TenantToolUpdate,
    tenant_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> TenantToolResponse:
    """Partially update a tenant tool."""
    tid = _tid(tenant_id, user)
    tool = await ToolService.update_tool(db, tool_id, tid, body)
    return TenantToolResponse.model_validate(tool)


@router.delete("/{tool_id}", status_code=204)
async def delete_tool(
    tool_id: uuid.UUID,
    tenant_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> Response:
    """Delete a tenant tool."""
    tid = _tid(tenant_id, user)
    await ToolService.delete_tool(db, tool_id, tid)
    return Response(status_code=204)


# ============================================================================
# Agent ↔ Tool bindings
# ============================================================================


@router.post("/agents/{agent_id}/bind", response_model=AgentToolResponse, status_code=201)
async def bind_tool_to_agent(
    agent_id: uuid.UUID,
    body: AgentToolBind,
    tenant_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> AgentToolResponse:
    """Bind a tenant tool to an agent."""
    tid = _tid(tenant_id, user)
    binding = await ToolService.bind_agent_tool(db, agent_id, tid, body)
    return AgentToolResponse.model_validate(binding)


@router.delete("/agents/{agent_id}/tools/{tool_id}", status_code=204)
async def unbind_tool_from_agent(
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    tenant_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> Response:
    """Unbind a tenant tool from an agent."""
    tid = _tid(tenant_id, user)
    await ToolService.unbind_agent_tool(db, agent_id, tool_id, tid)
    return Response(status_code=204)


@router.get("/agents/{agent_id}", response_model=list[AgentToolResponse])
async def list_agent_tools(
    agent_id: uuid.UUID,
    tenant_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> list[AgentToolResponse]:
    """List all tools bound to an agent."""
    tid = _tid(tenant_id, user)
    bindings = await ToolService.list_agent_tools(db, agent_id, tid)
    return [AgentToolResponse.model_validate(b) for b in bindings]
