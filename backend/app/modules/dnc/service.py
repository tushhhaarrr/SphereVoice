"""DNC module — service layer."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.dnc.models import DncEntry
from app.modules.dnc.schemas import DncCheckResponse, DncEntryCreate

logger = structlog.get_logger(__name__)


class DncService:
    @staticmethod
    async def list_entries(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[DncEntry], int]:
        count_q = select(func.count()).select_from(DncEntry).where(DncEntry.tenant_id == tenant_id)
        total = (await db.execute(count_q)).scalar_one()
        rows_q = (
            select(DncEntry)
            .where(DncEntry.tenant_id == tenant_id)
            .order_by(DncEntry.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        rows = (await db.execute(rows_q)).scalars().all()
        return list(rows), total

    @staticmethod
    async def add_entry(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        data: DncEntryCreate,
        added_by: uuid.UUID | None = None,
    ) -> DncEntry:
        """Add a phone number to the DNC list.

        Raises ConflictError if the tenant already has an entry for this number.
        """
        existing_q = select(DncEntry).where(
            DncEntry.tenant_id == tenant_id,
            DncEntry.phone_number == data.phone_number,
        )
        existing = (await db.execute(existing_q)).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(f"Phone number {data.phone_number} is already on the DNC list")

        entry = DncEntry(
            tenant_id=tenant_id,
            phone_number=data.phone_number,
            source=data.source,
            reason=data.reason,
            added_by=added_by,
            expires_at=data.expires_at,
        )
        db.add(entry)
        await db.flush()
        await db.refresh(entry)
        return entry

    @staticmethod
    async def get_entry(db: AsyncSession, entry_id: uuid.UUID, tenant_id: uuid.UUID) -> DncEntry:
        q = select(DncEntry).where(DncEntry.id == entry_id, DncEntry.tenant_id == tenant_id)
        row = (await db.execute(q)).scalar_one_or_none()
        if row is None:
            raise NotFoundError("DncEntry", str(entry_id))
        return row

    @staticmethod
    async def remove_entry(db: AsyncSession, entry_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        q = select(DncEntry).where(DncEntry.id == entry_id, DncEntry.tenant_id == tenant_id)
        row = (await db.execute(q)).scalar_one_or_none()
        if row is None:
            raise NotFoundError("DncEntry", str(entry_id))
        await db.delete(row)
        await db.flush()

    @staticmethod
    async def check_number(
        db: AsyncSession, tenant_id: uuid.UUID, phone_number: str
    ) -> DncCheckResponse:
        """Return whether a phone number is currently on the DNC list.

        Expired entries (expires_at < NOW()) are treated as NOT blocked.
        """
        now = datetime.now(UTC)
        q = select(DncEntry).where(
            DncEntry.tenant_id == tenant_id,
            DncEntry.phone_number == phone_number,
        )
        row = (await db.execute(q)).scalar_one_or_none()
        if row is None:
            return DncCheckResponse(phone_number=phone_number, is_blocked=False)
        # Treat expired entries as not blocked
        if row.expires_at is not None and row.expires_at < now:
            return DncCheckResponse(phone_number=phone_number, is_blocked=False)
        return DncCheckResponse(
            phone_number=phone_number,
            is_blocked=True,
            reason=row.reason,
            expires_at=row.expires_at,
        )
