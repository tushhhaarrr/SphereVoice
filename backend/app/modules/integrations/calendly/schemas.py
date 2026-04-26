"""Calendly integration — Pydantic schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


# ── Shared OAuth responses ───────────────────────────────────


class CalendlyInitiateResponse(BaseModel):
    auth_url: str


class CalendlySyncResponse(BaseModel):
    status: str
    message: str
    account_email: str | None = None


class CalendlyIntegrationResponse(BaseModel):
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
    def from_integration(cls, obj: Any) -> "CalendlyIntegrationResponse":
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


class CalendlyIntegrationListResponse(BaseModel):
    integrations: list[CalendlyIntegrationResponse]
    total: int


# ── Event types ──────────────────────────────────────────────


class CalendlyEventType(BaseModel):
    uri: str
    name: str
    scheduling_url: str | None = None
    active: bool = True
    duration_minutes: int | None = None
    kind: str | None = None  # "solo" | "group"
    pooling_type: str | None = None  # "round_robin" | "collective" | null


class CalendlyEventTypeListResponse(BaseModel):
    event_types: list[CalendlyEventType]
    total: int


# ── Available times ──────────────────────────────────────────


class CalendlyAvailableTime(BaseModel):
    status: str
    start_time: str
    invitees_remaining: int | None = None


class CalendlyAvailableTimesResponse(BaseModel):
    available_times: list[CalendlyAvailableTime]
    total: int


# ── Scheduled events ────────────────────────────────────────


class CalendlyScheduledEvent(BaseModel):
    uri: str
    name: str | None = None
    status: str  # "active" | "canceled"
    start_time: str
    end_time: str
    event_type: str | None = None
    location: dict[str, Any] | None = None


class CalendlyScheduledEventListResponse(BaseModel):
    events: list[CalendlyScheduledEvent]
    total: int
