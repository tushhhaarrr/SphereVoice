"""Add llm_max_tokens column to agents table.

Revision ID: 006_llm_max_tokens
Revises: 005_provider_secret_refs
Create Date: 2026-03-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "006_llm_max_tokens"
down_revision = "005_provider_secret_refs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "llm_max_tokens",
            sa.Integer(),
            nullable=False,
            server_default="1024",
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "llm_max_tokens")
