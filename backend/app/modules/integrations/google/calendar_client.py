"""Google Calendar API client — async wrapper with retry & connection pooling.

All calls go through the Google Calendar v3 REST API.
Token management is delegated to GoogleOAuthService.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.google._http import google_request
from app.modules.integrations.google.oauth import GoogleOAuthService
from app.modules.integrations.models import TenantIntegration

logger = structlog.get_logger(__name__)

_CALENDAR_API = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarClient:
    """Async Google Calendar v3 client with automatic token refresh.

    Features:
    - Connection-pooled HTTP (shared across calls)
    - Exponential-backoff retry for 429 / 5xx
    - Structured ``GoogleAPIError`` for all failures
    - Pagination for list endpoints

    Usage::

        client = GoogleCalendarClient(db, integration)
        events = await client.list_events(max_results=10)
        event  = await client.create_event(summary="Demo", ...)
    """

    def __init__(self, db: AsyncSession, integration: TenantIntegration) -> None:
        self._db = db
        self._integration = integration

    async def _get_headers(self) -> dict[str, str]:
        token = await GoogleOAuthService.get_valid_access_token(self._db, self._integration)
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # ── Calendars ────────────────────────────────────────────

    async def list_calendars(self) -> list[dict[str, Any]]:
        """Return all calendars visible to the connected Google account."""
        headers = await self._get_headers()
        resp = await google_request(
            "GET",
            f"{_CALENDAR_API}/users/me/calendarList",
            headers=headers,
        )
        return resp.json().get("items", [])

    # ── Events ───────────────────────────────────────────────

    async def list_events(
        self,
        calendar_id: str = "primary",
        *,
        max_results: int = 25,
        time_min: str | None = None,
        time_max: str | None = None,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        """List upcoming events from a calendar.

        Automatically paginates when ``max_results`` exceeds a single page (250 items).
        """
        if time_min is None:
            time_min = datetime.now(UTC).isoformat()

        headers = await self._get_headers()
        all_events: list[dict[str, Any]] = []
        page_token: str | None = None

        while len(all_events) < max_results:
            page_size = min(max_results - len(all_events), 250)
            params: dict[str, Any] = {
                "maxResults": page_size,
                "timeMin": time_min,
                "singleEvents": "true",
                "orderBy": "startTime",
            }
            if time_max:
                params["timeMax"] = time_max
            if query:
                params["q"] = query
            if page_token:
                params["pageToken"] = page_token

            resp = await google_request(
                "GET",
                f"{_CALENDAR_API}/calendars/{calendar_id}/events",
                headers=headers,
                params=params,
            )
            data = resp.json()
            all_events.extend(data.get("items", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return all_events[:max_results]

    async def get_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """Fetch a single event by ID."""
        headers = await self._get_headers()
        resp = await google_request(
            "GET",
            f"{_CALENDAR_API}/calendars/{calendar_id}/events/{event_id}",
            headers=headers,
        )
        return resp.json()

    async def create_event(
        self,
        summary: str,
        start: str,
        end: str,
        *,
        calendar_id: str = "primary",
        description: str | None = None,
        location: str | None = None,
        attendees: list[str] | None = None,
        timezone: str = "UTC",
    ) -> dict[str, Any]:
        """Create an event on the connected Google Calendar."""
        body: dict[str, Any] = {
            "summary": summary,
            "start": {"dateTime": start, "timeZone": timezone},
            "end": {"dateTime": end, "timeZone": timezone},
        }
        if description:
            body["description"] = description
        if location:
            body["location"] = location
        if attendees:
            body["attendees"] = [{"email": e} for e in attendees]

        headers = await self._get_headers()
        resp = await google_request(
            "POST",
            f"{_CALENDAR_API}/calendars/{calendar_id}/events",
            headers=headers,
            json_body=body,
        )
        event = resp.json()
        logger.info(
            "google_calendar_event_created",
            event_id=event.get("id"),
            summary=summary,
            integration_id=str(self._integration.id),
        )
        return event

    async def update_event(
        self,
        event_id: str,
        *,
        calendar_id: str = "primary",
        summary: str | None = None,
        start: str | None = None,
        end: str | None = None,
        description: str | None = None,
        location: str | None = None,
        attendees: list[str] | None = None,
        timezone: str = "UTC",
    ) -> dict[str, Any]:
        """Patch an existing event."""
        body: dict[str, Any] = {}
        if summary is not None:
            body["summary"] = summary
        if start is not None:
            body["start"] = {"dateTime": start, "timeZone": timezone}
        if end is not None:
            body["end"] = {"dateTime": end, "timeZone": timezone}
        if description is not None:
            body["description"] = description
        if location is not None:
            body["location"] = location
        if attendees is not None:
            body["attendees"] = [{"email": e} for e in attendees]

        headers = await self._get_headers()
        resp = await google_request(
            "PATCH",
            f"{_CALENDAR_API}/calendars/{calendar_id}/events/{event_id}",
            headers=headers,
            json_body=body,
        )
        return resp.json()

    async def delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> None:
        """Delete (cancel) an event on the calendar."""
        headers = await self._get_headers()
        try:
            await google_request(
                "DELETE",
                f"{_CALENDAR_API}/calendars/{calendar_id}/events/{event_id}",
                headers=headers,
            )
        except Exception as exc:
            # 410 (already deleted) is acceptable
            if hasattr(exc, "status_code") and exc.status_code == 410:
                return
            raise

    async def check_availability(
        self,
        time_min: str,
        time_max: str,
        calendar_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Check free/busy for given calendars in a time window.

        Returns the ``calendars`` dict from the freeBusy response, keyed by
        calendar ID.  Each value contains a ``busy`` list of time blocks.
        """
        if calendar_ids is None:
            calendar_ids = ["primary"]
        body = {
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": cid} for cid in calendar_ids],
        }
        headers = await self._get_headers()
        resp = await google_request(
            "POST",
            f"{_CALENDAR_API}/freeBusy",
            headers=headers,
            json_body=body,
        )
        return resp.json().get("calendars", {})
