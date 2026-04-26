"""Add dynamic_variables to agent_share_links.

Revision ID: 012_share_link_dynamic_variables
Revises: 011_crm_integrations
Create Date: 2026-03-14 00:00:00.000000

Stores the template variables that were pre-configured by the builder
when creating a share link, so that demo calls use the exact same
pipeline setup as authenticated test calls.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "012_share_link_dynamic_variables"
down_revision = "011_crm_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_share_links",
        sa.Column(
            "dynamic_variables",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_share_links", "dynamic_variables")
