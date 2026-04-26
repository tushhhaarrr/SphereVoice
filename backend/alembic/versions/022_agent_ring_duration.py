"""Add ring_duration_seconds to agents table.

Revision ID: 022_agent_ring_duration
Revises: 021_fix_integ_status_def
Create Date: 2026-03-19 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "022_agent_ring_duration"
down_revision = "021_fix_integ_status_def"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "ring_duration_seconds",
            sa.Integer(),
            server_default=sa.text("30"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "ring_duration_seconds")
