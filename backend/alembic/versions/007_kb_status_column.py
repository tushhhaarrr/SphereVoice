"""Add status column to knowledge_bases table.

Revision ID: 007_kb_status_column
Revises: 006_llm_max_tokens
Create Date: 2026-03-12 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "007_kb_status_column"
down_revision = "006_llm_max_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_bases",
        sa.Column(
            "status",
            sa.String(20),
            server_default="ready",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("knowledge_bases", "status")
