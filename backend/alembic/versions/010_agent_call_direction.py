"""Add call_direction column to agents table.

Revision ID: 010_agent_call_direction
Revises: 009_user_invitations
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa

revision = "010_agent_call_direction"
down_revision = "009_user_invitations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "call_direction",
            sa.String(20),
            server_default=sa.text("'inbound'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "call_direction")
