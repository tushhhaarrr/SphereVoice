"""Add CRM writeback status columns to calls table.

Revision ID: 024_call_writeback_status
Revises: 023_lower_default_call_dur
Create Date: 2026-03-19 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "024_call_writeback_status"
down_revision = "023_lower_default_call_dur"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "calls",
        sa.Column("writeback_status", sa.String(20), nullable=True),
    )
    op.add_column(
        "calls",
        sa.Column("writeback_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "calls",
        sa.Column(
            "writeback_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_calls_writeback_status",
        "calls",
        ["writeback_status"],
        postgresql_where=sa.text("writeback_status IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_calls_writeback_status", table_name="calls")
    op.drop_column("calls", "writeback_completed_at")
    op.drop_column("calls", "writeback_error")
    op.drop_column("calls", "writeback_status")
