"""Calendly API client — interacts with the Calendly REST API v2.

Supports:
- Fetching the current user profile
- Listing event types (scheduling pages)
- Checking available times for an event type
- Listing scheduled events (past & upcoming)
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.calendly.oauth import CalendlyOAuthService
from app.modules.integrations.models import TenantIntegration

logger = structlog.get_logger(__name__)

_API_BASE = "https://api.calendly.com"


class CalendlyClient:
    """Thin async wrapper around the Calendly REST API v2."""

    def __init__(self, db: AsyncSession, integration: TenantIntegration) -> None:
        self._db = db
        self._integration = integration

    async def _get_headers(self) -> dict[str, str]:
        token = await CalendlyOAuthService.get_valid_access_token(self._db, self._integration)
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _owner_uri(self) -> str | None:
        return (self._integration.config or {}).get("owner_uri")

    # ── User info ────────────────────────────────────────────

    async def get_current_user(self) -> dict[str, Any]:
        """GET /users/me"""
        headers = await self._get_headers()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{_API_BASE}/users/me", headers=headers)
            resp.raise_for_status()
            return resp.json().get("resource", {})

    # ── Event types ──────────────────────────────────────────

    async def list_event_types(self, active: bool = True) -> list[dict[str, Any]]:
        """GET /event_types — list the user's scheduling pages."""
        owner_uri = self._owner_uri()
        if not owner_uri:
            raise ValueError("Calendly owner URI not found — please reconnect")

        headers = await self._get_headers()
        params: dict[str, Any] = {"user": owner_uri}
        if active:
            params["active"] = "true"

        all_items: list[dict[str, Any]] = []
        next_page: str | None = None

        async with httpx.AsyncClient(timeout=15.0) as client:
            while True:
                if next_page:
                    resp = await client.get(next_page, headers=headers)
                else:
                    resp = await client.get(
                        f"{_API_BASE}/event_types", params=params, headers=headers,
                    )
                resp.raise_for_status()
                data = resp.json()
                all_items.extend(data.get("collection", []))
                next_page = data.get("pagination", {}).get("next_page")
                if not next_page:
                    break

        return all_items

    # ── Available times ──────────────────────────────────────

    async def get_available_times(
        self,
        event_type_uri: str,
        start_time: str,
        end_time: str,
    ) -> list[dict[str, Any]]:
        """GET /event_type_available_times — available slots (max 7-day window)."""
        headers = await self._get_headers()
        params = {
            "event_type": event_type_uri,
            "start_time": start_time,
            "end_time": end_time,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{_API_BASE}/event_type_available_times",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json().get("collection", [])

    # ── Scheduled events ─────────────────────────────────────

    async def list_scheduled_events(
        self,
        status: str = "active",
        max_results: int = 25,
        min_start_time: str | None = None,
        max_start_time: str | None = None,
    ) -> list[dict[str, Any]]:
        """GET /scheduled_events — list upcoming/past meetings."""
        owner_uri = self._owner_uri()
        if not owner_uri:
            raise ValueError("Calendly owner URI not found — please reconnect")

        headers = await self._get_headers()
        params: dict[str, Any] = {
            "user": owner_uri,
            "status": status,
            "count": min(max_results, 100),
            "sort": "start_time:asc",
        }
        if min_start_time:
            params["min_start_time"] = min_start_time
        if max_start_time:
            params["max_start_time"] = max_start_time

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{_API_BASE}/scheduled_events",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json().get("collection", [])
