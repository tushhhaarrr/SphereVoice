"""Tool Registry module — Pydantic schemas."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# TenantTool schemas
# ---------------------------------------------------------------------------


class TenantToolCreate(BaseModel):
    """Request body for creating a new tenant tool."""

    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    category: str = Field(..., pattern="^(messaging|email|calendar|spreadsheet|crm|custom)$")
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    execution_type: str = Field(default="integration", pattern="^(integration|webhook)$")
    execution_config: dict[str, Any] = Field(default_factory=dict)
    integration_id: uuid.UUID | None = None
    is_active: bool = True


class TenantToolUpdate(BaseModel):
    """Request body for updating a tenant tool. All fields optional."""

    display_name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, min_length=1)
    category: str | None = Field(None, pattern="^(messaging|email|calendar|spreadsheet|crm|custom)$")
    parameters_schema: dict[str, Any] | None = None
    execution_type: str | None = Field(None, pattern="^(integration|webhook)$")
    execution_config: dict[str, Any] | None = None
    integration_id: uuid.UUID | None = None
    is_active: bool | None = None


class TenantToolResponse(BaseModel):
    """Response body for a tenant tool."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    integration_id: uuid.UUID | None
    name: str
    display_name: str
    description: str
    category: str
    parameters_schema: dict[str, Any]
    execution_type: str
    execution_config: dict[str, Any]
    is_active: bool


class TenantToolListResponse(BaseModel):
    """Paginated list of tenant tools."""

    items: list[TenantToolResponse]
    total: int
    skip: int
    limit: int


# ---------------------------------------------------------------------------
# AgentTool (bind/unbind) schemas
# ---------------------------------------------------------------------------


class AgentToolBind(BaseModel):
    """Request body to bind a tool to an agent."""

    tool_id: uuid.UUID
    config: dict[str, Any] = Field(default_factory=dict)


class AgentToolResponse(BaseModel):
    """Response body for a bound agent tool."""

    model_config = ConfigDict(from_attributes=True)

    agent_id: uuid.UUID
    tool_id: uuid.UUID
    config: dict[str, Any]
    tool: TenantToolResponse
