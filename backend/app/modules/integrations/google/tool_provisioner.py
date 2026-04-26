"""Auto-provision default TenantTool records when a Google integration connects.

Called from the OAuth callback after a successful ``handle_callback()``.  The
helper is idempotent — if tools already exist for the integration they are
skipped.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tool_registry.models import TenantTool

logger = structlog.get_logger(__name__)

# ── Calendar tool templates ──────────────────────────────────────────────

_CALENDAR_TOOLS: list[dict] = [
    {
        "name": "book_appointment",
        "display_name": "Book Appointment",
        "description": (
            "Create a new calendar event / appointment. "
            "Use this when the caller wants to schedule a meeting or appointment."
        ),
        "category": "calendar",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create_event"],
                    "description": "The action to perform.",
                },
                "summary": {
                    "type": "string",
                    "description": "Title of the event (e.g. 'Meeting with John').",
                },
                "start_time": {
                    "type": "string",
                    "description": "Start time in ISO 8601 format (e.g. '2026-03-22T10:00:00').",
                },
                "end_time": {
                    "type": "string",
                    "description": "End time in ISO 8601 format (e.g. '2026-03-22T11:00:00').",
                },
                "description": {
                    "type": "string",
                    "description": "Optional description or notes for the event.",
                },
                "attendee_email": {
                    "type": "string",
                    "description": "Optional email address of the attendee.",
                },
            },
            "required": ["action", "summary", "start_time", "end_time"],
        },
        "execution_config": {},
    },
    {
        "name": "check_availability",
        "display_name": "Check Availability",
        "description": (
            "Check calendar availability for a given time range. "
            "Use this when the caller asks 'are you available on…' or 'when is the next free slot'."
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
        "execution_config": {},
    },
    {
        "name": "list_upcoming_events",
        "display_name": "List Upcoming Events",
        "description": (
            "List upcoming calendar events. "
            "Use this when the caller asks about their schedule or upcoming appointments."
        ),
        "category": "calendar",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list_events"],
                    "description": "The action to perform.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of events to return (default 5).",
                },
            },
            "required": ["action"],
        },
        "execution_config": {},
    },
]

# ── Sheets tool templates ────────────────────────────────────────────────

_SHEETS_TOOLS: list[dict] = [
    {
        "name": "save_to_sheet",
        "display_name": "Save to Spreadsheet",
        "description": (
            "Append a row of data to a Google Sheet. "
            "Use this to save caller information, form responses, or call notes."
        ),
        "category": "spreadsheet",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["append"],
                    "description": "The action to perform.",
                },
                "data": {
                    "type": "object",
                    "description": "Key-value pairs to save. Keys should match sheet column headers.",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["action", "data"],
        },
        "execution_config": {"row_data_field": "data"},
    },
    {
        "name": "read_from_sheet",
        "display_name": "Read from Spreadsheet",
        "description": (
            "Read rows from a Google Sheet. "
            "Use this to look up information like pricing, inventory, or contact details."
        ),
        "category": "spreadsheet",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read"],
                    "description": "The action to perform.",
                },
                "range": {
                    "type": "string",
                    "description": "Optional A1 range (e.g. 'Sheet1!A:D'). Returns all data if omitted.",
                },
                "max_rows": {
                    "type": "integer",
                    "description": "Maximum rows to return (default 50, max 200).",
                },
            },
            "required": ["action"],
        },
        "execution_config": {},
    },
]


async def provision_default_tools(
    db: AsyncSession,
    integration_id: uuid.UUID,
    tenant_id: uuid.UUID,
    provider: str,
) -> list[TenantTool]:
    """Create default tools for a newly connected integration.

    Idempotent: skips tools whose ``name`` already exists for this integration.
    """
    if provider == "google_calendar":
        templates = _CALENDAR_TOOLS
    elif provider == "google_sheets":
        templates = _SHEETS_TOOLS
    else:
        return []

    # Check existing tool names for this integration to avoid duplicates
    existing = await db.execute(
        select(TenantTool.name).where(
            TenantTool.tenant_id == tenant_id,
            TenantTool.integration_id == integration_id,
        )
    )
    existing_names = {row[0] for row in existing.all()}

    created: list[TenantTool] = []
    for tmpl in templates:
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
            "default_tools_provisioned",
            provider=provider,
            tenant_id=str(tenant_id),
            tool_count=len(created),
            tool_names=[t.name for t in created],
        )

    return created
