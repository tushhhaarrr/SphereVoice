"""Calendly integration — API routes.

Endpoints:
  POST   /calendly/initiate              — Get Calendly OAuth URL
  GET    /calendly/callback              — OAuth callback (no auth header)
  GET    /calendly                       — List Calendly integrations for tenant
  POST   /calendly/{id}/sync             — Verify / refresh connection
  DELETE /calendly/{id}                  — Disconnect
  GET    /calendly/{id}/event-types      — List event types (scheduling pages)
  GET    /calendly/{id}/available-times  — Check availability for an event type
  GET    /calendly/{id}/scheduled-events — List upcoming scheduled events
"""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_db, set_tenant_context
from app.core.exceptions import ValidationError as SphereVoiceValidationError
from app.modules.auth import User, get_current_user_model, require_write
from app.modules.integrations.calendly.oauth import CalendlyOAuthService, _verify_oauth_state
from app.modules.integrations.calendly.schemas import (
    CalendlyAvailableTime,
    CalendlyAvailableTimesResponse,
    CalendlyEventType,
    CalendlyEventTypeListResponse,
    CalendlyInitiateResponse,
    CalendlyIntegrationListResponse,
    CalendlyIntegrationResponse,
    CalendlyScheduledEvent,
    CalendlyScheduledEventListResponse,
    CalendlySyncResponse,
)
from app.modules.integrations.models import TenantIntegration

router = APIRouter(prefix="/integrations/calendly", tags=["Calendly Integrations"])
settings = get_settings()
logger = structlog.get_logger(__name__)


def _effective_tenant_id(explicit: UUID | None, user: User) -> UUID:
    tid = explicit or user.tenant_id
    if tid is None:
        raise SphereVoiceValidationError("tenant_id is required — pass it as a query parameter")
    return tid


# ═══════════════════════════════════════════════════════════════
#  OAuth endpoints
# ═══════════════════════════════════════════════════════════════


@router.get("", response_model=CalendlyIntegrationListResponse)
async def list_calendly_integrations(
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> CalendlyIntegrationListResponse:
    """List Calendly integrations for the tenant."""
    tid = _effective_tenant_id(tenant_id, user)
    result = await db.execute(
        select(TenantIntegration).where(
            TenantIntegration.tenant_id == tid,
            TenantIntegration.provider == "calendly",
        )
    )
    rows = list(result.scalars().all())
    return CalendlyIntegrationListResponse(
        integrations=[CalendlyIntegrationResponse.from_integration(r) for r in rows],
        total=len(rows),
    )


@router.post("/initiate", response_model=CalendlyInitiateResponse)
async def initiate_calendly_oauth(
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> CalendlyInitiateResponse:
    """Return the Calendly OAuth 2.0 authorization URL."""
    tid = _effective_tenant_id(tenant_id, user)
    auth_url = CalendlyOAuthService.build_auth_url(tid, user.id)
    return CalendlyInitiateResponse(auth_url=auth_url)


@router.get("/callback")
async def calendly_oauth_callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle Calendly OAuth redirect."""
    frontend_url = settings.FRONTEND_URL

    if error or not code or not state:
        return RedirectResponse(
            url=f"{frontend_url}/integrations?calendly_error={error or 'cancelled'}",
            status_code=302,
        )

    try:
        integration = await CalendlyOAuthService.handle_callback(db=db, code=code, state=state)
        tenant_id = integration.tenant_id
        # Auto-create default Calendly tools
        from app.modules.integrations.calendly.tool_provisioner import provision_calendly_tools

        await provision_calendly_tools(db, integration.id, tenant_id)
        await db.commit()
        return RedirectResponse(
            url=f"{frontend_url}/workspace/{tenant_id}/integrations?calendly_connected=true",
            status_code=302,
        )
    except Exception as exc:
        logger.error("calendly_callback_error", error=str(exc))
        try:
            tenant_id, _ = _verify_oauth_state(state)
            return RedirectResponse(
                url=f"{frontend_url}/workspace/{tenant_id}/integrations?calendly_error=callback_failed",
                status_code=302,
            )
        except Exception:
            return RedirectResponse(
                url=f"{frontend_url}/integrations?calendly_error=callback_failed",
                status_code=302,
            )


@router.post("/{integration_id}/sync", response_model=CalendlySyncResponse)
async def sync_calendly_integration(
    integration_id: UUID,
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> CalendlySyncResponse:
    """Verify / refresh the Calendly connection."""
    tid = _effective_tenant_id(tenant_id, user)
    integration = await CalendlyOAuthService.sync_integration(db, integration_id, tid)
    email = (integration.config or {}).get("account_email")
    return CalendlySyncResponse(
        status=integration.status,
        message="Connection verified" if integration.status == "connected" else "Connection error",
        account_email=email,
    )


@router.delete("/{integration_id}", status_code=204)
async def disconnect_calendly(
    integration_id: UUID,
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> Response:
    """Disconnect the Calendly integration."""
    tid = _effective_tenant_id(tenant_id, user)
    await CalendlyOAuthService.disconnect_integration(db, integration_id, tid)
    return Response(status_code=204)


# ═══════════════════════════════════════════════════════════════
#  Data endpoints
# ═══════════════════════════════════════════════════════════════


async def _get_calendly_client(
    db: AsyncSession, integration_id: UUID, tenant_id: UUID,
):
    """Helper: resolve integration → CalendlyClient."""
    from app.modules.integrations.calendly.client import CalendlyClient

    result = await db.execute(
        select(TenantIntegration).where(
            TenantIntegration.id == integration_id,
            TenantIntegration.tenant_id == tenant_id,
            TenantIntegration.provider == "calendly",
        )
    )
    integration = result.scalar_one_or_none()
    if integration is None:
        raise SphereVoiceValidationError("Calendly integration not found")
    return CalendlyClient(db, integration)


@router.get("/{integration_id}/event-types", response_model=CalendlyEventTypeListResponse)
async def list_event_types(
    integration_id: UUID,
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> CalendlyEventTypeListResponse:
    """List Calendly event types (scheduling pages)."""
    tid = _effective_tenant_id(tenant_id, user)
    client = await _get_calendly_client(db, integration_id, tid)
    raw = await client.list_event_types()
    event_types = [
        CalendlyEventType(
            uri=et.get("uri", ""),
            name=et.get("name", ""),
            scheduling_url=et.get("scheduling_url"),
            active=et.get("active", True),
            duration_minutes=et.get("duration"),
            kind=et.get("kind"),
            pooling_type=et.get("pooling_type"),
        )
        for et in raw
    ]
    return CalendlyEventTypeListResponse(event_types=event_types, total=len(event_types))


@router.get("/{integration_id}/available-times", response_model=CalendlyAvailableTimesResponse)
async def get_available_times(
    integration_id: UUID,
    event_type: str = Query(..., description="Calendly event type URI"),
    start_time: str = Query(..., description="ISO 8601 start time"),
    end_time: str = Query(..., description="ISO 8601 end time"),
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> CalendlyAvailableTimesResponse:
    """Check available times for a Calendly event type (max 7-day window)."""
    tid = _effective_tenant_id(tenant_id, user)
    client = await _get_calendly_client(db, integration_id, tid)
    raw = await client.get_available_times(event_type, start_time, end_time)
    times = [
        CalendlyAvailableTime(
            status=t.get("status", "available"),
            start_time=t.get("start_time", ""),
            invitees_remaining=t.get("invitees_remaining"),
        )
        for t in raw
    ]
    return CalendlyAvailableTimesResponse(available_times=times, total=len(times))


@router.get("/{integration_id}/scheduled-events", response_model=CalendlyScheduledEventListResponse)
async def list_scheduled_events(
    integration_id: UUID,
    status: str = Query("active", description="Filter by status: active or canceled"),
    max_results: int = Query(25, ge=1, le=100),
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> CalendlyScheduledEventListResponse:
    """List scheduled Calendly events."""
    tid = _effective_tenant_id(tenant_id, user)
    client = await _get_calendly_client(db, integration_id, tid)
    raw = await client.list_scheduled_events(status=status, max_results=max_results)
    events = [
        CalendlyScheduledEvent(
            uri=e.get("uri", ""),
            name=e.get("name"),
            status=e.get("status", "active"),
            start_time=e.get("start_time", ""),
            end_time=e.get("end_time", ""),
            event_type=e.get("event_type"),
            location=e.get("location"),
        )
        for e in raw
    ]
    return CalendlyScheduledEventListResponse(events=events, total=len(events))
