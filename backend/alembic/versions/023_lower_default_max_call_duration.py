"""Lower default max_call_duration_seconds from 3600 to 240 (4 minutes).

Revision ID: 023_lower_default_call_dur
Revises: 022_agent_ring_duration
Create Date: 2026-03-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "023_lower_default_call_dur"
down_revision = "022_agent_ring_duration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Change the column default for new agents
    op.alter_column(
        "agents",
        "max_call_duration_seconds",
        server_default=sa.text("240"),
    )
    # Update existing agents that still have the old default of 3600
    op.execute(
        sa.text(
            "UPDATE agents SET max_call_duration_seconds = 240 "
            "WHERE max_call_duration_seconds = 3600"
        )
    )


def downgrade() -> None:
    op.alter_column(
        "agents",
        "max_call_duration_seconds",
        server_default=sa.text("3600"),
    )
    op.execute(
        sa.text(
            "UPDATE agents SET max_call_duration_seconds = 3600 "
            "WHERE max_call_duration_seconds = 240"
        )
    )
