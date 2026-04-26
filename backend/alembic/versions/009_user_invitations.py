"""Add user_invitations table for token-based email invite flow.

Revision ID: 009_user_invitations
Revises: 008_agent_share_links
Create Date: 2026-03-13 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "009_user_invitations"
down_revision = "008_agent_share_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_invitations",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column(
            "role",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'read_only'"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "invited_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_user_invitations_token", "user_invitations", ["token"], unique=True
    )
    op.create_index(
        "ix_user_invitations_email", "user_invitations", ["email"]
    )


def downgrade() -> None:
    op.drop_index("ix_user_invitations_email", table_name="user_invitations")
    op.drop_index("ix_user_invitations_token", table_name="user_invitations")
    op.drop_table("user_invitations")
