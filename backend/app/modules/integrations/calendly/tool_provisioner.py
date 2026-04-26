"""Auto-provision default TenantTool records when Calendly connects.

Called from the OAuth callback after a successful ``handle_callback()``.
Idempotent — skips tools whose name already exists for this integration.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tool_registry.models import TenantTool

logger = structlog.get_logger(__name__)

# ── Calendly tool templates ──────────────────────────────────

_CALENDLY_TOOLS: list[dict] = [
    {
        "name": "check_calendly_availability",
        "display_name": "Check Calendly Availability",
        "description": (
            "Check available time slots on Calendly for a given date range. "
            "Use this when the caller asks 'are you available on…' or "
            "'when is the next free slot'."
        ),
        "category": "calendar",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["check_availability"],
                    "description": "The action to perform.",
                },
                "start_time": {
                    "type": "string",
                    "description": "Start of the window to check (ISO 8601).",
                },
                "end_time": {
                    "type": "string",
                    "description": "End of the window to check (ISO 8601).",
                },
            },
            "required": ["action", "start_time", "end_time"],
        },
        "execution_config": {"calendly_action": "check_availability"},
    },
    {
        "name": "list_calendly_event_types",
        "display_name": "List Calendly Event Types",
        "description": (
            "List available Calendly event types (scheduling pages). "
            "Use this to find the right event type before checking availability "
            "or sharing a booking link."
        ),
        "category": "calendar",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list_event_types"],
                    "description": "The action to perform.",
                },
            },
            "required": ["action"],
        },
        "execution_config": {"calendly_action": "list_event_types"},
    },
    {
        "name": "get_calendly_scheduling_link",
        "display_name": "Get Calendly Scheduling Link",
        "description": (
            "Get the Calendly scheduling link (booking URL) so the caller can "
            "book an appointment. Use this when the caller wants to schedule a meeting."
        ),
        "category": "calendar",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get_scheduling_link"],
                    "description": "The action to perform.",
                },
                "event_type_name": {
                    "type": "string",
                    "description": "Optional name of the event type to get the link for. If not provided, returns the first active event type.",
                },
            },
            "required": ["action"],
        },
        "execution_config": {"calendly_action": "get_scheduling_link"},
    },
    {
        "name": "list_calendly_scheduled_events",
        "display_name": "List Calendly Scheduled Events",
        "description": (
            "List upcoming scheduled Calendly events/meetings. "
            "Use this when the caller asks about their upcoming appointments."
        ),
        "category": "calendar",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list_scheduled_events"],
                    "description": "The action to perform.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of events to return (default 5).",
                },
            },
            "required": ["action"],
        },
        "execution_config": {"calendly_action": "list_scheduled_events"},
    },
]


async def provision_calendly_tools(
    db: AsyncSession,
    integration_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[TenantTool]:
    """Create default tools for a newly connected Calendly integration.

    Idempotent: skips tools whose ``name`` already exists for this integration.
    """
    # Check existing tool names for this integration
    existing = await db.execute(
        select(TenantTool.name).where(
            TenantTool.tenant_id == tenant_id,
            TenantTool.integration_id == integration_id,
        )
    )
    existing_names = {row[0] for row in existing.all()}

    created: list[TenantTool] = []
    for tmpl in _CALENDLY_TOOLS:
        if tmpl["name"] in existing_names:
            continue
        tool = TenantTool(
            tenant_id=tenant_id,
            integration_id=integration_id,
            name=tmpl["name"],
            display_name=tmpl["display_name"],
            description=tmpl["description"],
            category=tmpl["category"],
            parameters_schema=tmpl["parameters_schema"],
            execution_type="integration",
            execution_config=tmpl["execution_config"],
            is_active=True,
        )
        db.add(tool)
        created.append(tool)

    if created:
        await db.flush()
        logger.info(
            "calendly_tools_provisioned",
            tenant_id=str(tenant_id),
            tool_count=len(created),
            tool_names=[t.name for t in created],
        )

    return created
