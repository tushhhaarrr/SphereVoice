"""Google integrations — API routes for Calendar & Sheets.

Endpoints:
  Calendar:
    POST   /google/calendar/initiate       — Get Google OAuth URL (calendar scopes)
    GET    /google/calendar/callback        — OAuth callback (no auth header)
    POST   /google/calendar/{id}/sync       — Verify / refresh connection
    DELETE /google/calendar/{id}            — Disconnect
    GET    /google/calendar/{id}/calendars  — List user's calendars
    GET    /google/calendar/{id}/events     — List upcoming events
    POST   /google/calendar/{id}/events     — Create an event
    PATCH  /google/calendar/{id}/events/{eid} — Update an event
    DELETE /google/calendar/{id}/events/{eid} — Delete an event
    POST   /google/calendar/{id}/availability — Check free/busy

  Sheets:
    POST   /google/sheets/initiate         — Get Google OAuth URL (sheets scopes)
    GET    /google/sheets/callback          — OAuth callback (no auth header)
    POST   /google/sheets/{id}/sync         — Verify / refresh connection
    DELETE /google/sheets/{id}              — Disconnect
    GET    /google/sheets/{id}/spreadsheets — List spreadsheets
    GET    /google/sheets/{id}/spreadsheets/{sid} — Get spreadsheet details
    GET    /google/sheets/{id}/spreadsheets/{sid}/rows — Read rows
    POST   /google/sheets/{id}/spreadsheets/{sid}/rows — Append rows
    PUT    /google/sheets/{id}/spreadsheets/{sid}/rows — Update rows
"""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_db, set_tenant_context
from app.core.exceptions import ValidationError as SphereVoiceValidationError
from app.modules.auth import User, get_current_user_model, require_write
from app.modules.integrations.google._http import GoogleAPIError
from app.modules.integrations.google.oauth import GoogleOAuthService, _verify_oauth_state
from app.modules.integrations.google.schemas import (
    AppendRowsRequest,
    AppendRowsResponse,
    AvailabilityResponse,
    CalendarEntry,
    CalendarEvent,
    CalendarEventListResponse,
    CalendarListResponse,
    CheckAvailabilityRequest,
    CreateCalendarEventRequest,
    GoogleInitiateResponse,
    GoogleIntegrationListResponse,
    GoogleIntegrationResponse,
    GoogleSyncResponse,
    ReadRowsResponse,
    SheetTab,
    SpreadsheetDetailResponse,
    SpreadsheetEntry,
    SpreadsheetListResponse,
    UpdateCalendarEventRequest,
    UpdateRowsRequest,
)

router = APIRouter(prefix="/integrations/google", tags=["Google Integrations"])
settings = get_settings()
logger = structlog.get_logger(__name__)


def _effective_tenant_id(explicit: UUID | None, user: User) -> UUID:
    tid = explicit or user.tenant_id
    if tid is None:
        raise SphereVoiceValidationError("tenant_id is required — pass it as a query parameter")
    return tid


# ═══════════════════════════════════════════════════════════════
#  Google Calendar
# ═══════════════════════════════════════════════════════════════


@router.get("/calendar", response_model=GoogleIntegrationListResponse)
async def list_calendar_integrations(
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> GoogleIntegrationListResponse:
    """List Google Calendar integrations for the tenant."""
    from sqlalchemy import select
    from app.modules.integrations.models import TenantIntegration

    tid = _effective_tenant_id(tenant_id, user)
    result = await db.execute(
        select(TenantIntegration).where(
            TenantIntegration.tenant_id == tid,
            TenantIntegration.provider == "google_calendar",
        )
    )
    rows = list(result.scalars().all())
    return GoogleIntegrationListResponse(
        integrations=[GoogleIntegrationResponse.from_integration(r) for r in rows],
        total=len(rows),
    )


@router.post("/calendar/initiate", response_model=GoogleInitiateResponse)
async def initiate_calendar_oauth(
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> GoogleInitiateResponse:
    """Return the Google OAuth 2.0 authorization URL for Calendar."""
    tid = _effective_tenant_id(tenant_id, user)
    auth_url = GoogleOAuthService.build_auth_url(tid, user.id, "google_calendar")
    return GoogleInitiateResponse(auth_url=auth_url)


@router.get("/calendar/callback")
async def calendar_oauth_callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle Google OAuth redirect for Calendar."""
    frontend_url = settings.FRONTEND_URL

    if error or not code or not state:
        return RedirectResponse(
            url=f"{frontend_url}/integrations?google_error={error or 'cancelled'}",
            status_code=302,
        )

    try:
        integration = await GoogleOAuthService.handle_callback(db=db, code=code, state=state)
        tenant_id = integration.tenant_id
        # Auto-create default calendar tools for this integration
        from app.modules.integrations.google.tool_provisioner import provision_default_tools
        await provision_default_tools(db, integration.id, tenant_id, "google_calendar")
        await db.commit()
        return RedirectResponse(
            url=f"{frontend_url}/workspace/{tenant_id}/integrations?google_calendar_connected=true",
            status_code=302,
        )
    except Exception as exc:
        logger.error("google_calendar_callback_error", error=str(exc))
        try:
            tenant_id, _, _ = _verify_oauth_state(state)
            return RedirectResponse(
                url=f"{frontend_url}/workspace/{tenant_id}/integrations?google_error=callback_failed",
                status_code=302,
            )
        except Exception:
            return RedirectResponse(
                url=f"{frontend_url}/integrations?google_error=callback_failed",
                status_code=302,
            )


@router.post("/calendar/{integration_id}/sync", response_model=GoogleSyncResponse)
async def sync_calendar_integration(
    integration_id: UUID,
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> GoogleSyncResponse:
    """Verify / refresh the Google Calendar connection."""
    tid = _effective_tenant_id(tenant_id, user)
    integration = await GoogleOAuthService.sync_integration(db, integration_id, tid)
    email = (integration.config or {}).get("account_email")
    return GoogleSyncResponse(
        status=integration.status,
        message="Connection verified" if integration.status == "connected" else "Connection error",
        account_email=email,
    )


@router.delete("/calendar/{integration_id}", status_code=204)
async def disconnect_calendar(
    integration_id: UUID,
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> Response:
    """Revoke Google tokens and remove the Calendar integration."""
    tid = _effective_tenant_id(tenant_id, user)
    await GoogleOAuthService.disconnect_integration(db, integration_id, tid)
    return Response(status_code=204)


# ── Calendar data endpoints ──────────────────────────────────


async def _get_calendar_client(
    db: AsyncSession, integration_id: UUID, tenant_id: UUID,
):
    """Helper: resolve integration → client."""
    from sqlalchemy import select
    from app.modules.integrations.models import TenantIntegration
    from app.modules.integrations.google.calendar_client import GoogleCalendarClient

    result = await db.execute(
        select(TenantIntegration).where(
            TenantIntegration.id == integration_id,
            TenantIntegration.tenant_id == tenant_id,
            TenantIntegration.provider == "google_calendar",
        )
    )
    integration = result.scalar_one_or_none()
    if integration is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("GoogleCalendarIntegration", str(integration_id))
    return GoogleCalendarClient(db, integration)


@router.get("/calendar/{integration_id}/calendars", response_model=CalendarListResponse)
async def list_calendars(
    integration_id: UUID,
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> CalendarListResponse:
    """List calendars visible to the connected Google account."""
    tid = _effective_tenant_id(tenant_id, user)
    client = await _get_calendar_client(db, integration_id, tid)
    items = await client.list_calendars()
    return CalendarListResponse(
        calendars=[
            CalendarEntry(
                id=c.get("id", ""),
                summary=c.get("summary"),
                description=c.get("description"),
                primary=c.get("primary", False),
            )
            for c in items
        ]
    )


@router.get("/calendar/{integration_id}/events", response_model=CalendarEventListResponse)
async def list_calendar_events(
    integration_id: UUID,
    calendar_id: str = Query(default="primary"),
    max_results: int = Query(default=25, ge=1, le=250),
    time_min: str | None = Query(default=None),
    time_max: str | None = Query(default=None),
    query: str | None = Query(default=None, max_length=200),
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> CalendarEventListResponse:
    """List upcoming events from a Google Calendar."""
    tid = _effective_tenant_id(tenant_id, user)
    client = await _get_calendar_client(db, integration_id, tid)
    items = await client.list_events(
        calendar_id=calendar_id,
        max_results=max_results,
        time_min=time_min,
        time_max=time_max,
        query=query,
    )
    events = [
        CalendarEvent(
            id=e.get("id"),
            summary=e.get("summary"),
            description=e.get("description"),
            location=e.get("location"),
            start=e.get("start"),
            end=e.get("end"),
            attendees=e.get("attendees"),
            html_link=e.get("htmlLink"),
            status=e.get("status"),
            created=e.get("created"),
            updated=e.get("updated"),
        )
        for e in items
    ]
    return CalendarEventListResponse(events=events, total=len(events))


@router.post("/calendar/{integration_id}/events", response_model=CalendarEvent)
async def create_calendar_event(
    integration_id: UUID,
    body: CreateCalendarEventRequest,
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> CalendarEvent:
    """Create a new event on Google Calendar."""
    tid = _effective_tenant_id(tenant_id, user)
    client = await _get_calendar_client(db, integration_id, tid)
    result = await client.create_event(
        summary=body.summary,
        start=body.start,
        end=body.end,
        calendar_id=body.calendar_id,
        description=body.description,
        location=body.location,
        attendees=body.attendees,
        timezone=body.timezone,
    )
    return CalendarEvent(
        id=result.get("id"),
        summary=result.get("summary"),
        description=result.get("description"),
        location=result.get("location"),
        start=result.get("start"),
        end=result.get("end"),
        attendees=result.get("attendees"),
        html_link=result.get("htmlLink"),
        status=result.get("status"),
        created=result.get("created"),
        updated=result.get("updated"),
    )


@router.patch("/calendar/{integration_id}/events/{event_id}", response_model=CalendarEvent)
async def update_calendar_event(
    integration_id: UUID,
    event_id: str,
    body: UpdateCalendarEventRequest,
    calendar_id: str = Query(default="primary"),
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> CalendarEvent:
    """Update an existing Google Calendar event."""
    tid = _effective_tenant_id(tenant_id, user)
    client = await _get_calendar_client(db, integration_id, tid)
    result = await client.update_event(
        event_id=event_id,
        calendar_id=calendar_id,
        summary=body.summary,
        start=body.start,
        end=body.end,
        description=body.description,
        location=body.location,
        attendees=body.attendees,
        timezone=body.timezone,
    )
    return CalendarEvent(
        id=result.get("id"),
        summary=result.get("summary"),
        description=result.get("description"),
        location=result.get("location"),
        start=result.get("start"),
        end=result.get("end"),
        attendees=result.get("attendees"),
        html_link=result.get("htmlLink"),
        status=result.get("status"),
        created=result.get("created"),
        updated=result.get("updated"),
    )


@router.delete("/calendar/{integration_id}/events/{event_id}", status_code=204)
async def delete_calendar_event(
    integration_id: UUID,
    event_id: str,
    calendar_id: str = Query(default="primary"),
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> Response:
    """Delete a Google Calendar event."""
    tid = _effective_tenant_id(tenant_id, user)
    client = await _get_calendar_client(db, integration_id, tid)
    await client.delete_event(event_id, calendar_id)
    return Response(status_code=204)


@router.post("/calendar/{integration_id}/availability", response_model=AvailabilityResponse)
async def check_availability(
    integration_id: UUID,
    body: CheckAvailabilityRequest,
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> AvailabilityResponse:
    """Check free/busy for calendars in a time window."""
    tid = _effective_tenant_id(tenant_id, user)
    client = await _get_calendar_client(db, integration_id, tid)
    result = await client.check_availability(
        time_min=body.time_min,
        time_max=body.time_max,
        calendar_ids=body.calendar_ids,
    )
    return AvailabilityResponse(calendars=result)


# ═══════════════════════════════════════════════════════════════
#  Google Sheets
# ═══════════════════════════════════════════════════════════════


@router.get("/sheets", response_model=GoogleIntegrationListResponse)
async def list_sheets_integrations(
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> GoogleIntegrationListResponse:
    """List Google Sheets integrations for the tenant."""
    from sqlalchemy import select
    from app.modules.integrations.models import TenantIntegration

    tid = _effective_tenant_id(tenant_id, user)
    result = await db.execute(
        select(TenantIntegration).where(
            TenantIntegration.tenant_id == tid,
            TenantIntegration.provider == "google_sheets",
        )
    )
    rows = list(result.scalars().all())
    return GoogleIntegrationListResponse(
        integrations=[GoogleIntegrationResponse.from_integration(r) for r in rows],
        total=len(rows),
    )


@router.post("/sheets/initiate", response_model=GoogleInitiateResponse)
async def initiate_sheets_oauth(
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> GoogleInitiateResponse:
    """Return the Google OAuth 2.0 authorization URL for Sheets."""
    tid = _effective_tenant_id(tenant_id, user)
    auth_url = GoogleOAuthService.build_auth_url(tid, user.id, "google_sheets")
    return GoogleInitiateResponse(auth_url=auth_url)


@router.get("/sheets/callback")
async def sheets_oauth_callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle Google OAuth redirect for Sheets."""
    frontend_url = settings.FRONTEND_URL

    if error or not code or not state:
        return RedirectResponse(
            url=f"{frontend_url}/integrations?google_error={error or 'cancelled'}",
            status_code=302,
        )

    try:
        integration = await GoogleOAuthService.handle_callback(db=db, code=code, state=state)
        tenant_id = integration.tenant_id
        # Auto-create default sheets tools for this integration
        from app.modules.integrations.google.tool_provisioner import provision_default_tools
        await provision_default_tools(db, integration.id, tenant_id, "google_sheets")
        await db.commit()
        return RedirectResponse(
            url=f"{frontend_url}/workspace/{tenant_id}/integrations?google_sheets_connected=true",
            status_code=302,
        )
    except Exception as exc:
        logger.error("google_sheets_callback_error", error=str(exc))
        try:
            tenant_id, _, _ = _verify_oauth_state(state)
            return RedirectResponse(
                url=f"{frontend_url}/workspace/{tenant_id}/integrations?google_error=callback_failed",
                status_code=302,
            )
        except Exception:
            return RedirectResponse(
                url=f"{frontend_url}/integrations?google_error=callback_failed",
                status_code=302,
            )


@router.post("/sheets/{integration_id}/sync", response_model=GoogleSyncResponse)
async def sync_sheets_integration(
    integration_id: UUID,
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> GoogleSyncResponse:
    """Verify / refresh the Google Sheets connection."""
    tid = _effective_tenant_id(tenant_id, user)
    integration = await GoogleOAuthService.sync_integration(db, integration_id, tid)
    email = (integration.config or {}).get("account_email")
    return GoogleSyncResponse(
        status=integration.status,
        message="Connection verified" if integration.status == "connected" else "Connection error",
        account_email=email,
    )


@router.delete("/sheets/{integration_id}", status_code=204)
async def disconnect_sheets(
    integration_id: UUID,
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> Response:
    """Revoke Google tokens and remove the Sheets integration."""
    tid = _effective_tenant_id(tenant_id, user)
    await GoogleOAuthService.disconnect_integration(db, integration_id, tid)
    return Response(status_code=204)


# ── Sheets data endpoints ───────────────────────────────────


async def _get_sheets_client(
    db: AsyncSession, integration_id: UUID, tenant_id: UUID,
):
    """Helper: resolve integration → client."""
    from sqlalchemy import select
    from app.modules.integrations.models import TenantIntegration
    from app.modules.integrations.google.sheets_client import GoogleSheetsClient

    result = await db.execute(
        select(TenantIntegration).where(
            TenantIntegration.id == integration_id,
            TenantIntegration.tenant_id == tenant_id,
            TenantIntegration.provider == "google_sheets",
        )
    )
    integration = result.scalar_one_or_none()
    if integration is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("GoogleSheetsIntegration", str(integration_id))
    return GoogleSheetsClient(db, integration)


@router.get("/sheets/{integration_id}/spreadsheets", response_model=SpreadsheetListResponse)
async def list_spreadsheets(
    integration_id: UUID,
    max_results: int = Query(default=50, ge=1, le=100),
    query: str | None = Query(default=None, max_length=200),
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> SpreadsheetListResponse:
    """List Google Sheets spreadsheets visible to the connected account."""
    tid = _effective_tenant_id(tenant_id, user)
    client = await _get_sheets_client(db, integration_id, tid)
    files = await client.list_spreadsheets(max_results=max_results, query=query)
    return SpreadsheetListResponse(
        spreadsheets=[
            SpreadsheetEntry(
                id=f.get("id", ""),
                name=f.get("name", ""),
                modified_time=f.get("modifiedTime"),
                web_view_link=f.get("webViewLink"),
            )
            for f in files
        ]
    )


@router.get(
    "/sheets/{integration_id}/spreadsheets/{spreadsheet_id}",
    response_model=SpreadsheetDetailResponse,
)
async def get_spreadsheet_detail(
    integration_id: UUID,
    spreadsheet_id: str,
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> SpreadsheetDetailResponse:
    """Get metadata (title, tabs) for a specific spreadsheet."""
    tid = _effective_tenant_id(tenant_id, user)
    client = await _get_sheets_client(db, integration_id, tid)
    data = await client.get_spreadsheet(spreadsheet_id)
    sheets = [
        SheetTab(
            sheet_id=s["properties"]["sheetId"],
            title=s["properties"]["title"],
            index=s["properties"]["index"],
        )
        for s in data.get("sheets", [])
    ]
    return SpreadsheetDetailResponse(
        spreadsheet_id=data.get("spreadsheetId", spreadsheet_id),
        title=data.get("properties", {}).get("title", ""),
        sheets=sheets,
    )


@router.get(
    "/sheets/{integration_id}/spreadsheets/{spreadsheet_id}/rows",
    response_model=ReadRowsResponse,
)
async def read_spreadsheet_rows(
    integration_id: UUID,
    spreadsheet_id: str,
    range: str = Query(..., description="A1 notation range, e.g. Sheet1!A1:Z100"),
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> ReadRowsResponse:
    """Read rows from a spreadsheet range."""
    tid = _effective_tenant_id(tenant_id, user)
    client = await _get_sheets_client(db, integration_id, tid)
    values = await client.read_rows(spreadsheet_id, range)
    return ReadRowsResponse(values=values, row_count=len(values))


@router.post(
    "/sheets/{integration_id}/spreadsheets/{spreadsheet_id}/rows",
    response_model=AppendRowsResponse,
)
async def append_spreadsheet_rows(
    integration_id: UUID,
    spreadsheet_id: str,
    body: AppendRowsRequest,
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> AppendRowsResponse:
    """Append rows to the end of a sheet tab."""
    tid = _effective_tenant_id(tenant_id, user)
    client = await _get_sheets_client(db, integration_id, tid)
    result = await client.append_rows(spreadsheet_id, body.sheet_name, body.rows)
    updates = result.get("updates", {})
    return AppendRowsResponse(
        updated_range=updates.get("updatedRange"),
        updated_rows=updates.get("updatedRows", len(body.rows)),
    )


@router.put(
    "/sheets/{integration_id}/spreadsheets/{spreadsheet_id}/rows",
    response_model=dict,
)
async def update_spreadsheet_rows(
    integration_id: UUID,
    spreadsheet_id: str,
    body: UpdateRowsRequest,
    tenant_id: UUID | None = Query(default=None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> dict:
    """Overwrite a specific range with new values."""
    tid = _effective_tenant_id(tenant_id, user)
    client = await _get_sheets_client(db, integration_id, tid)
    result = await client.update_rows(spreadsheet_id, body.range, body.rows)
    return result
