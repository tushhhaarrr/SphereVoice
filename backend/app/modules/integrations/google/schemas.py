"""Google integrations — Pydantic schemas for Calendar & Sheets."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


# ── Shared ───────────────────────────────────────────────────


class GoogleInitiateResponse(BaseModel):
    auth_url: str


class GoogleSyncResponse(BaseModel):
    status: str
    message: str
    account_email: str | None = None


class GoogleIntegrationResponse(BaseModel):
    id: str
    tenant_id: str
    provider: str
    status: str
    account_email: str | None = None
    last_synced_at: str | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_integration(cls, obj: Any) -> "GoogleIntegrationResponse":
        config = getattr(obj, "config", {}) or {}
        return cls(
            id=str(obj.id),
            tenant_id=str(obj.tenant_id),
            provider=obj.provider,
            status=obj.status,
            account_email=config.get("account_email"),
            last_synced_at=obj.last_synced_at.isoformat() if obj.last_synced_at else None,
            created_at=obj.created_at.isoformat() if obj.created_at else "",
            updated_at=obj.updated_at.isoformat() if obj.updated_at else "",
        )


class GoogleIntegrationListResponse(BaseModel):
    integrations: list[GoogleIntegrationResponse]
    total: int


# ── Calendar ─────────────────────────────────────────────────


class CalendarEntry(BaseModel):
    id: str
    summary: str | None = None
    description: str | None = None
    primary: bool = False

    model_config = {"extra": "allow"}


class CalendarListResponse(BaseModel):
    calendars: list[CalendarEntry]


class CalendarEvent(BaseModel):
    id: str | None = None
    summary: str | None = None
    description: str | None = None
    location: str | None = None
    start: dict[str, Any] | None = None
    end: dict[str, Any] | None = None
    attendees: list[dict[str, Any]] | None = None
    html_link: str | None = None
    status: str | None = None
    created: str | None = None
    updated: str | None = None

    model_config = {"extra": "allow"}


class CalendarEventListResponse(BaseModel):
    events: list[CalendarEvent]
    total: int


class CreateCalendarEventRequest(BaseModel):
    summary: str
    start: str  # ISO-8601
    end: str  # ISO-8601
    calendar_id: str = "primary"
    description: str | None = None
    location: str | None = None
    attendees: list[str] | None = None  # email addresses
    timezone: str = "UTC"


class UpdateCalendarEventRequest(BaseModel):
    summary: str | None = None
    start: str | None = None
    end: str | None = None
    description: str | None = None
    location: str | None = None
    attendees: list[str] | None = None
    timezone: str = "UTC"


class CheckAvailabilityRequest(BaseModel):
    time_min: str  # ISO-8601
    time_max: str  # ISO-8601
    calendar_ids: list[str] | None = None


class AvailabilityResponse(BaseModel):
    calendars: dict[str, Any]


# ── Sheets ───────────────────────────────────────────────────


class SpreadsheetEntry(BaseModel):
    id: str
    name: str
    modified_time: str | None = None
    web_view_link: str | None = None

    model_config = {"extra": "allow"}


class SpreadsheetListResponse(BaseModel):
    spreadsheets: list[SpreadsheetEntry]


class SheetTab(BaseModel):
    sheet_id: int
    title: str
    index: int


class SpreadsheetDetailResponse(BaseModel):
    spreadsheet_id: str
    title: str
    sheets: list[SheetTab]


class ReadRowsResponse(BaseModel):
    values: list[list[Any]]
    row_count: int


class AppendRowsRequest(BaseModel):
    sheet_name: str
    rows: list[list[Any]]


class AppendRowsResponse(BaseModel):
    updated_range: str | None = None
    updated_rows: int = 0


class UpdateRowsRequest(BaseModel):
    range: str  # A1 notation
    rows: list[list[Any]]
