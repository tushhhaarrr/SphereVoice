"""Add agent_share_links table for shareable public demo links.

Revision ID: 008_agent_share_links
Revises: 007_kb_status_column
Create Date: 2026-03-12 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "008_agent_share_links"
down_revision = "007_kb_status_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_share_links",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        "ix_agent_share_links_agent_id",
        "agent_share_links",
        ["agent_id"],
    )
    op.create_index(
        "ix_agent_share_links_token",
        "agent_share_links",
        ["token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_share_links_token", table_name="agent_share_links")
    op.drop_index("ix_agent_share_links_agent_id", table_name="agent_share_links")
    op.drop_table("agent_share_links")
