"""Base SQLAlchemy model mixins.

Provides reusable mixins for common patterns:
- ``TimestampMixin``: created_at / updated_at auto-managed columns
- ``TenantMixin``: tenant_id column with index for RLS
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns to a model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        onupdate=datetime.now(UTC),
        nullable=False,
    )


class TenantMixin:
    """Adds ``tenant_id`` column for multi-tenant RLS support.

    Every tenant-scoped table MUST include this mixin.
    PostgreSQL RLS policies filter on ``tenant_id``.
    """

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nexus_registry.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    @classmethod
    def __declare_last__(cls) -> None:
        """Add composite index on tenant_id if not already present."""
        table = cls.__table__  # type: ignore[attr-defined]
        idx_name = f"ix_{table.name}_tenant_id"
        existing_names = {idx.name for idx in table.indexes}
        if idx_name not in existing_names:
            Index(idx_name, table.c.tenant_id)


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary key column ``id`` with server-side default."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
