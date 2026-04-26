"""Tool Registry module — service layer."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.modules.tool_registry.models import AgentTool, TenantTool
from app.modules.tool_registry.schemas import (
    AgentToolBind,
    TenantToolCreate,
    TenantToolUpdate,
)

logger = structlog.get_logger(__name__)


class ToolService:
    """Service layer for TenantTool and AgentTool CRUD."""

    # ========================================================================
    # TenantTool CRUD
    # ========================================================================

    @staticmethod
    async def list_tools(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        category: str | None = None,
    ) -> tuple[list[TenantTool], int]:
        """List all tools for the given tenant, optionally filtered by category."""
        count_q = (
            select(func.count()).select_from(TenantTool).where(TenantTool.tenant_id == tenant_id)
        )
        rows_q = (
            select(TenantTool)
            .where(TenantTool.tenant_id == tenant_id)
            .order_by(TenantTool.created_at.desc())
        )
        if category is not None:
            count_q = count_q.where(TenantTool.category == category)
            rows_q = rows_q.where(TenantTool.category == category)
        total = (await db.execute(count_q)).scalar_one()
        rows = (await db.execute(rows_q.offset(skip).limit(limit))).scalars().all()
        return list(rows), total

    @staticmethod
    async def get_tool(
        db: AsyncSession,
        tool_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> TenantTool:
        """Get a single tenant tool by ID."""
        q = select(TenantTool).where(
            TenantTool.id == tool_id,
            TenantTool.tenant_id == tenant_id,
        )
        row = (await db.execute(q)).scalar_one_or_none()
        if row is None:
            raise NotFoundError("TenantTool", str(tool_id))
        return row

    @staticmethod
    async def create_tool(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        data: TenantToolCreate,
    ) -> TenantTool:
        """Create a new tenant tool."""
        tool = TenantTool(
            tenant_id=tenant_id,
            integration_id=data.integration_id,
            name=data.name,
            display_name=data.display_name,
            description=data.description,
            category=data.category,
            parameters_schema=data.parameters_schema,
            execution_type=data.execution_type,
            execution_config=data.execution_config,
            is_active=data.is_active,
        )
        db.add(tool)
        await db.flush()
        await db.refresh(tool)
        logger.info("tool_created", tool_id=str(tool.id), tenant_id=str(tenant_id))
        return tool

    @staticmethod
    async def update_tool(
        db: AsyncSession,
        tool_id: uuid.UUID,
        tenant_id: uuid.UUID,
        data: TenantToolUpdate,
    ) -> TenantTool:
        """Partially update a tenant tool."""
        tool = await ToolService.get_tool(db, tool_id, tenant_id)
        updates = data.model_dump(exclude_none=True)
        for field, value in updates.items():
            setattr(tool, field, value)
        await db.flush()
        await db.refresh(tool)
        logger.info("tool_updated", tool_id=str(tool_id), fields=list(updates.keys()))
        return tool

    @staticmethod
    async def delete_tool(
        db: AsyncSession,
        tool_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> None:
        """Delete a tenant tool."""
        tool = await ToolService.get_tool(db, tool_id, tenant_id)
        await db.delete(tool)
        await db.flush()
        logger.info("tool_deleted", tool_id=str(tool_id), tenant_id=str(tenant_id))

    # ========================================================================
    # AgentTool (bind / unbind)
    # ========================================================================

    @staticmethod
    async def bind_agent_tool(
        db: AsyncSession,
        agent_id: uuid.UUID,
        tenant_id: uuid.UUID,
        data: AgentToolBind,
    ) -> AgentTool:
        """Bind an existing tenant tool to an agent."""
        # Verify the tool belongs to this tenant
        await ToolService.get_tool(db, data.tool_id, tenant_id)

        # Upsert: delete existing binding if present, then insert
        existing_q = select(AgentTool).where(
            AgentTool.agent_id == agent_id,
            AgentTool.tool_id == data.tool_id,
        )
        existing = (await db.execute(existing_q)).scalar_one_or_none()
        if existing is not None:
            existing.config = data.config
            await db.flush()
            await db.refresh(existing, attribute_names=["tool"])
            return existing

        binding = AgentTool(
            agent_id=agent_id,
            tool_id=data.tool_id,
            config=data.config,
        )
        db.add(binding)
        await db.flush()
        await db.refresh(binding, attribute_names=["tool"])
        logger.info(
            "agent_tool_bound",
            agent_id=str(agent_id),
            tool_id=str(data.tool_id),
        )
        return binding

    @staticmethod
    async def unbind_agent_tool(
        db: AsyncSession,
        agent_id: uuid.UUID,
        tool_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> None:
        """Remove a tool binding from an agent."""
        # Verify tool belongs to this tenant first
        await ToolService.get_tool(db, tool_id, tenant_id)

        q = select(AgentTool).where(
            AgentTool.agent_id == agent_id,
            AgentTool.tool_id == tool_id,
        )
        binding = (await db.execute(q)).scalar_one_or_none()
        if binding is None:
            raise NotFoundError("AgentTool", f"{agent_id}/{tool_id}")
        await db.delete(binding)
        await db.flush()
        logger.info(
            "agent_tool_unbound",
            agent_id=str(agent_id),
            tool_id=str(tool_id),
        )

    @staticmethod
    async def get_agent_tools(
        db: AsyncSession,
        agent_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[TenantTool]:
        """Return all active tools bound to the given agent.

        Per-agent config from ``AgentTool.config`` is merged on top of each
        tool's ``execution_config`` so executors get the correct per-agent
        overrides (e.g. ``calendar_id``, ``spreadsheet_id``).
        """
        q = (
            select(AgentTool)
            .join(TenantTool, TenantTool.id == AgentTool.tool_id)
            .where(
                AgentTool.agent_id == agent_id,
                TenantTool.tenant_id == tenant_id,
                TenantTool.is_active == True,  # noqa: E712
            )
            .options(selectinload(AgentTool.tool))
        )
        bindings = (await db.execute(q)).scalars().all()

        tools: list[TenantTool] = []
        for binding in bindings:
            tool = binding.tool
            if binding.config:
                # Merge per-agent overrides on top of the base execution_config
                merged = {**(tool.execution_config or {}), **binding.config}
                tool.execution_config = merged
            tools.append(tool)
        return tools

    @staticmethod
    async def list_agent_tools(
        db: AsyncSession,
        agent_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[AgentTool]:
        """Return AgentTool bindings (with nested TenantTool) for the response schema."""
        q = (
            select(AgentTool)
            .join(TenantTool, TenantTool.id == AgentTool.tool_id)
            .where(
                AgentTool.agent_id == agent_id,
                TenantTool.tenant_id == tenant_id,
            )
            .options(selectinload(AgentTool.tool))
        )
        rows = (await db.execute(q)).scalars().all()
        return list(rows)
