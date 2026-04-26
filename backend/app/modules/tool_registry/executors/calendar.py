"""Calendar executor — creates/checks events on Google Calendar during live calls."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

if TYPE_CHECKING:
    from app.modules.tool_registry.models import TenantTool

logger = structlog.get_logger(__name__)


class CalendarExecutor:
    """Execute calendar tools against Google Calendar during a live voice call.

    Supports multiple actions via the ``action`` field in arguments
    (or ``execution_config.default_action``):

    - ``create_event`` (default) — book an appointment
    - ``check_availability`` — check free/busy for a time range
    - ``list_events`` — list upcoming events

    Field names are configurable via ``execution_config``:
    - ``title_field`` → event title (default: ``"title"``)
    - ``start_field``  → ISO-8601 start datetime (default: ``"start_time"``)
    - ``end_field``    → ISO-8601 end datetime (default: ``"end_time"``)
    - ``duration_minutes_field`` → minutes if end absent (default: ``"duration_minutes"``)
    - ``attendees_field`` → list of emails (default: ``"attendees"``)
    - ``description_field`` → description (default: ``"description"``)
    - ``location_field`` → location (default: ``"location"``)

    The tool must be linked to a TenantIntegration with provider ``google_calendar``.
    """

    async def execute(
        self,
        tool: "TenantTool",
        arguments: dict[str, Any],
        call_context: dict[str, Any],
    ) -> dict[str, Any]:
        config: dict[str, Any] = tool.execution_config or {}
        action = arguments.get("action", config.get("default_action", "create_event"))

        if action == "check_availability":
            return await self._handle_check_availability(tool, arguments, call_context)
        if action == "list_events":
            return await self._handle_list_events(tool, arguments, call_context)
        return await self._handle_create_event(tool, arguments, call_context)

    # ── Create event ─────────────────────────────────────────

    async def _handle_create_event(
        self,
        tool: "TenantTool",
        arguments: dict[str, Any],
        call_context: dict[str, Any],
    ) -> dict[str, Any]:
        config: dict[str, Any] = tool.execution_config or {}
        title_field: str = config.get("title_field", "title")
        start_field: str = config.get("start_field", "start_time")
        end_field: str = config.get("end_field", "end_time")
        duration_field: str = config.get("duration_minutes_field", "duration_minutes")
        attendees_field: str = config.get("attendees_field", "attendees")
        description_field: str = config.get("description_field", "description")
        location_field: str = config.get("location_field", "location")

        title: str = arguments.get(title_field, "Meeting")
        start_time: str = arguments.get(start_field, "")
        end_time: str = arguments.get(end_field, "")
        attendees: list[str] = arguments.get(attendees_field, [])
        description: str | None = arguments.get(description_field)
        location: str | None = arguments.get(location_field)

        if not start_time:
            logger.warning(
                "calendar_missing_start",
                tool_name=tool.name,
                args=list(arguments.keys()),
            )
            return {
                "success": False,
                "error": "start_time is required to book an appointment",
                "tool": tool.name,
            }

        # Derive end from duration if not provided
        if not end_time:
            duration = int(arguments.get(duration_field, 30))
            try:
                start_dt = datetime.fromisoformat(start_time)
                end_dt = start_dt + timedelta(minutes=duration)
                end_time = end_dt.isoformat()
            except (ValueError, TypeError):
                end_time = ""

        # Real Google Calendar integration
        if tool.integration_id:
            try:
                return await self._create_google_event(
                    tool=tool,
                    title=title,
                    start_time=start_time,
                    end_time=end_time,
                    description=description,
                    location=location,
                    attendees=attendees,
                    call_context=call_context,
                )
            except Exception as exc:
                logger.exception(
                    "calendar_google_api_error",
                    tool_name=tool.name,
                    error=str(exc),
                )
                return {
                    "success": False,
                    "error": f"Failed to create calendar event: {exc}",
                    "tool": tool.name,
                }

        # No integration linked — return stub
        logger.info(
            "calendar_event_queued_no_integration",
            tool_name=tool.name,
            title=title,
            start_time=start_time,
            call_id=call_context.get("call_id"),
        )
        return {
            "success": True,
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "attendees": attendees,
            "tool": tool.name,
            "status": "queued",
        }

    # ── Check availability ───────────────────────────────────

    async def _handle_check_availability(
        self,
        tool: "TenantTool",
        arguments: dict[str, Any],
        call_context: dict[str, Any],
    ) -> dict[str, Any]:
        config: dict[str, Any] = tool.execution_config or {}
        start_field: str = config.get("start_field", "start_time")
        end_field: str = config.get("end_field", "end_time")

        time_min: str = arguments.get(start_field, "")
        time_max: str = arguments.get(end_field, "")

        if not time_min or not time_max:
            return {
                "success": False,
                "error": "Both start_time and end_time are required to check availability",
                "tool": tool.name,
            }

        if not tool.integration_id:
            return {
                "success": False,
                "error": "No calendar integration linked — cannot check availability",
                "tool": tool.name,
            }

        try:
            client, calendar_id = await self._get_client_and_calendar(tool, call_context)
            calendars = await client.check_availability(
                time_min=time_min,
                time_max=time_max,
                calendar_ids=[calendar_id],
            )

            # Parse busy blocks for the target calendar
            cal_data = calendars.get(calendar_id, {})
            busy_blocks = cal_data.get("busy", [])
            is_available = len(busy_blocks) == 0

            logger.info(
                "calendar_availability_checked",
                tool_name=tool.name,
                calendar_id=calendar_id,
                busy_count=len(busy_blocks),
                call_id=call_context.get("call_id"),
            )

            return {
                "success": True,
                "tool": tool.name,
                "available": is_available,
                "busy_blocks": busy_blocks,
                "time_range": {"start": time_min, "end": time_max},
            }
        except Exception as exc:
            logger.exception(
                "calendar_availability_error",
                tool_name=tool.name,
                error=str(exc),
            )
            return {
                "success": False,
                "error": f"Failed to check availability: {exc}",
                "tool": tool.name,
            }

    # ── List events ──────────────────────────────────────────

    async def _handle_list_events(
        self,
        tool: "TenantTool",
        arguments: dict[str, Any],
        call_context: dict[str, Any],
    ) -> dict[str, Any]:
        config: dict[str, Any] = tool.execution_config or {}
        start_field: str = config.get("start_field", "start_time")
        end_field: str = config.get("end_field", "end_time")

        time_min: str | None = arguments.get(start_field)
        time_max: str | None = arguments.get(end_field)
        max_results: int = int(arguments.get("max_results", 10))
        query: str | None = arguments.get("query")

        if not tool.integration_id:
            return {
                "success": False,
                "error": "No calendar integration linked — cannot list events",
                "tool": tool.name,
            }

        try:
            client, calendar_id = await self._get_client_and_calendar(tool, call_context)
            events = await client.list_events(
                calendar_id=calendar_id,
                max_results=min(max_results, 25),
                time_min=time_min,
                time_max=time_max,
                query=query,
            )

            # Return a simplified list for the LLM
            simple_events = [
                {
                    "id": e.get("id"),
                    "summary": e.get("summary", "(No title)"),
                    "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date")),
                    "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date")),
                    "status": e.get("status"),
                }
                for e in events
            ]

            return {
                "success": True,
                "tool": tool.name,
                "events": simple_events,
                "count": len(simple_events),
            }
        except Exception as exc:
            logger.exception(
                "calendar_list_events_error",
                tool_name=tool.name,
                error=str(exc),
            )
            return {
                "success": False,
                "error": f"Failed to list events: {exc}",
                "tool": tool.name,
            }

    # ── Helpers ───────────────────────────────────────────────

    async def _get_client_and_calendar(
        self,
        tool: "TenantTool",
        call_context: dict[str, Any],
    ) -> tuple[Any, str]:
        """Load the integration and return (GoogleCalendarClient, calendar_id)."""
        from app.core.database import async_session_factory
        from app.modules.integrations.google.calendar_client import GoogleCalendarClient
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
                raise ValueError("Calendar integration not found — please reconnect Google Calendar")

            client = GoogleCalendarClient(db, integration)
            calendar_id = (tool.execution_config or {}).get("calendar_id", "primary")
            # Detach from this session context — let caller use client
            # The client holds its own db ref for token refresh
            return client, calendar_id

    async def _create_google_event(
        self,
        tool: "TenantTool",
        title: str,
        start_time: str,
        end_time: str,
        description: str | None,
        location: str | None,
        attendees: list[str],
        call_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a real Google Calendar event using the linked integration."""
        from app.core.database import async_session_factory
        from app.modules.integrations.google.calendar_client import GoogleCalendarClient
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
                    "error": "Calendar integration not found — please reconnect Google Calendar",
                    "tool": tool.name,
                }

            client = GoogleCalendarClient(db, integration)
            calendar_id = (tool.execution_config or {}).get("calendar_id", "primary")

            event = await client.create_event(
                summary=title,
                start=start_time,
                end=end_time,
                calendar_id=calendar_id,
                description=description,
                location=location,
                attendees=attendees if attendees else None,
            )

        logger.info(
            "calendar_event_created_via_google",
            tool_name=tool.name,
            event_id=event.get("id"),
            call_id=call_context.get("call_id"),
        )

        return {
            "success": True,
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "attendees": attendees,
            "event_id": event.get("id"),
            "event_link": event.get("htmlLink"),
            "tool": tool.name,
            "status": "confirmed",
        }
