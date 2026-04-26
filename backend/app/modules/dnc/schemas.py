"""DNC module — Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class DncEntryCreate(BaseModel):
    phone_number: str
    source: str = "manual"
    reason: str | None = None
    expires_at: datetime | None = None


class DncEntryResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    phone_number: str
    source: str
    reason: str | None
    added_by: uuid.UUID | None
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DncEntryListResponse(BaseModel):
    entries: list[DncEntryResponse]
    total: int


class DncCheckRequest(BaseModel):
    phone_number: str


class DncCheckResponse(BaseModel):
    phone_number: str
    is_blocked: bool
    reason: str | None = None
    expires_at: datetime | None = None
