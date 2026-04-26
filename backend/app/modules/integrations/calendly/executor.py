"""Calendly executor — handles Calendly tool calls during live voice calls.

Dispatches based on ``execution_config.calendly_action``:
- ``check_availability`` — check available time slots
- ``list_event_types`` — list scheduling pages
- ``get_scheduling_link`` — get a booking URL
- ``list_scheduled_events`` — list upcoming meetings
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

if TYPE_CHECKING:
    from app.modules.tool_registry.models import TenantTool

logger = structlog.get_logger(__name__)


class CalendlyExecutor:
    """Execute Calendly tools during a live voice call."""

    async def execute(
        self,
        tool: "TenantTool",
        arguments: dict[str, Any],
        call_context: dict[str, Any],
    ) -> dict[str, Any]:
        config: dict[str, Any] = tool.execution_config or {}
        action = arguments.get("action", config.get("calendly_action", "check_availability"))

        if action == "check_availability":
            return await self._handle_check_availability(tool, arguments, call_context)
        if action == "list_event_types":
            return await self._handle_list_event_types(tool, arguments, call_context)
        if action == "get_scheduling_link":
            return await self._handle_get_scheduling_link(tool, arguments, call_context)
        if action == "list_scheduled_events":
            return await self._handle_list_scheduled_events(tool, arguments, call_context)

        return {"success": False, "error": f"Unknown Calendly action: {action}", "tool": tool.name}

    async def _get_client(self, tool: "TenantTool", call_context: dict[str, Any]):
        """Load the integration and return a CalendlyClient."""
        from app.core.database import async_session_factory
        from app.modules.integrations.calendly.client import CalendlyClient
        from app.modules.integrations.models import TenantIntegration

        tenant_id = call_context.get("tenant_id")
        async with async_session_factory() as db:
            query = select(TenantIntegration).where(
                TenantIntegration.id == tool.integration_id,
            )
            if tenant_id:
                query = query.where(TenantIntegration.tenant_id == tenant_id)
            result = await db.execute(query)
            integration = result.scalar_one_or_none()
            if integration is None:
                raise ValueError("Calendly integration not found — please reconnect")
            return CalendlyClient(db, integration), db

    async def _handle_check_availability(
        self, tool: "TenantTool", arguments: dict[str, Any], call_context: dict[str, Any],
    ) -> dict[str, Any]:
        start_time = arguments.get("start_time", "")
        end_time = arguments.get("end_time", "")

        if not start_time or not end_time:
            return {
                "success": False,
                "error": "Both start_time and end_time are required",
                "tool": tool.name,
            }

        if not tool.integration_id:
            return {
                "success": False,
                "error": "No Calendly integration linked",
                "tool": tool.name,
            }

        try:
            from app.core.database import async_session_factory
            from app.modules.integrations.calendly.client import CalendlyClient
            from app.modules.integrations.models import TenantIntegration

            tenant_id = call_context.get("tenant_id")
            async with async_session_factory() as db:
                query = select(TenantIntegration).where(
                    TenantIntegration.id == tool.integration_id,
                )
                if tenant_id:
                    query = query.where(TenantIntegration.tenant_id == tenant_id)
                result = await db.execute(query)
                integration = result.scalar_one_or_none()
                if integration is None:
                    return {
                        "success": False,
                        "error": "Calendly integration not found — please reconnect",
                        "tool": tool.name,
                    }

                client = CalendlyClient(db, integration)

                # Get event types to find the one to check availability for
                config = tool.execution_config or {}
                event_type_uri = config.get("event_type_uri")

                if not event_type_uri:
                    # Use the first active event type
                    event_types = await client.list_event_types(active=True)
                    if not event_types:
                        return {
                            "success": False,
                            "error": "No active event types found on Calendly",
                            "tool": tool.name,
                        }
                    event_type_uri = event_types[0].get("uri")

                available_times = await client.get_available_times(
                    event_type_uri=event_type_uri,
                    start_time=start_time,
                    end_time=end_time,
                )

                slots = [
                    {"start_time": t.get("start_time"), "status": t.get("status")}
                    for t in available_times
                    if t.get("status") == "available"
                ]

                return {
                    "success": True,
                    "tool": tool.name,
                    "available": len(slots) > 0,
                    "available_slots": slots[:10],
                    "total_slots": len(slots),
                    "time_range": {"start": start_time, "end": end_time},
                }
        except Exception as exc:
            logger.exception("calendly_check_availability_error", tool_name=tool.name, error=str(exc))
            return {"success": False, "error": f"Failed to check availability: {exc}", "tool": tool.name}

    async def _handle_list_event_types(
        self, tool: "TenantTool", arguments: dict[str, Any], call_context: dict[str, Any],
    ) -> dict[str, Any]:
        if not tool.integration_id:
            return {"success": False, "error": "No Calendly integration linked", "tool": tool.name}

        try:
            from app.core.database import async_session_factory
            from app.modules.integrations.calendly.client import CalendlyClient
            from app.modules.integrations.models import TenantIntegration

            tenant_id = call_context.get("tenant_id")
            async with async_session_factory() as db:
                query = select(TenantIntegration).where(
                    TenantIntegration.id == tool.integration_id,
                )
                if tenant_id:
                    query = query.where(TenantIntegration.tenant_id == tenant_id)
                result = await db.execute(query)
                integration = result.scalar_one_or_none()
                if integration is None:
                    return {"success": False, "error": "Calendly integration not found", "tool": tool.name}

                client = CalendlyClient(db, integration)
                event_types = await client.list_event_types(active=True)

                simple = [
                    {
                        "name": et.get("name"),
                        "duration_minutes": et.get("duration"),
                        "scheduling_url": et.get("scheduling_url"),
                        "kind": et.get("kind"),
                    }
                    for et in event_types
                ]

                return {
                    "success": True,
                    "tool": tool.name,
                    "event_types": simple,
                    "count": len(simple),
                }
        except Exception as exc:
            logger.exception("calendly_list_event_types_error", tool_name=tool.name, error=str(exc))
            return {"success": False, "error": f"Failed to list event types: {exc}", "tool": tool.name}

    async def _handle_get_scheduling_link(
        self, tool: "TenantTool", arguments: dict[str, Any], call_context: dict[str, Any],
    ) -> dict[str, Any]:
        if not tool.integration_id:
            return {"success": False, "error": "No Calendly integration linked", "tool": tool.name}

        try:
            from app.core.database import async_session_factory
            from app.modules.integrations.calendly.client import CalendlyClient
            from app.modules.integrations.models import TenantIntegration

            tenant_id = call_context.get("tenant_id")
            event_type_name = arguments.get("event_type_name")

            async with async_session_factory() as db:
                query = select(TenantIntegration).where(
                    TenantIntegration.id == tool.integration_id,
                )
                if tenant_id:
                    query = query.where(TenantIntegration.tenant_id == tenant_id)
                result = await db.execute(query)
                integration = result.scalar_one_or_none()
                if integration is None:
                    return {"success": False, "error": "Calendly integration not found", "tool": tool.name}

                client = CalendlyClient(db, integration)
                event_types = await client.list_event_types(active=True)

                if not event_types:
                    return {
                        "success": False,
                        "error": "No active event types found on Calendly",
                        "tool": tool.name,
                    }

                # Find by name if specified
                target = event_types[0]
                if event_type_name:
                    name_lower = event_type_name.lower()
                    for et in event_types:
                        if name_lower in (et.get("name", "")).lower():
                            target = et
                            break

                return {
                    "success": True,
                    "tool": tool.name,
                    "scheduling_url": target.get("scheduling_url"),
                    "event_type_name": target.get("name"),
                    "duration_minutes": target.get("duration"),
                }
        except Exception as exc:
            logger.exception("calendly_get_link_error", tool_name=tool.name, error=str(exc))
            return {"success": False, "error": f"Failed to get scheduling link: {exc}", "tool": tool.name}

    async def _handle_list_scheduled_events(
        self, tool: "TenantTool", arguments: dict[str, Any], call_context: dict[str, Any],
    ) -> dict[str, Any]:
        if not tool.integration_id:
            return {"success": False, "error": "No Calendly integration linked", "tool": tool.name}

        try:
            from app.core.database import async_session_factory
            from app.modules.integrations.calendly.client import CalendlyClient
            from app.modules.integrations.models import TenantIntegration

            tenant_id = call_context.get("tenant_id")
            max_results = int(arguments.get("max_results", 5))

            async with async_session_factory() as db:
                query = select(TenantIntegration).where(
                    TenantIntegration.id == tool.integration_id,
                )
                if tenant_id:
                    query = query.where(TenantIntegration.tenant_id == tenant_id)
                result = await db.execute(query)
                integration = result.scalar_one_or_none()
                if integration is None:
                    return {"success": False, "error": "Calendly integration not found", "tool": tool.name}

                client = CalendlyClient(db, integration)
                events = await client.list_scheduled_events(
                    status="active",
                    max_results=min(max_results, 25),
                    min_start_time=datetime.now(UTC).isoformat(),
                )

                simple = [
                    {
                        "name": e.get("name", "(No title)"),
                        "start_time": e.get("start_time"),
                        "end_time": e.get("end_time"),
                        "status": e.get("status"),
                    }
                    for e in events
                ]

                return {
                    "success": True,
                    "tool": tool.name,
                    "events": simple,
                    "count": len(simple),
                }
        except Exception as exc:
            logger.exception("calendly_list_events_error", tool_name=tool.name, error=str(exc))
            return {"success": False, "error": f"Failed to list events: {exc}", "tool": tool.name}
