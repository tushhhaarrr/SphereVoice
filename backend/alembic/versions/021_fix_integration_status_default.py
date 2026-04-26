"""Change tenant_integrations status default from 'connected' to 'active'.

Revision ID: 021_fix_integ_status_def
Revises: 020_agent_tools
Create Date: 2026-03-18 00:00:04.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "021_fix_integ_status_def"
down_revision = "020_agent_tools"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "tenant_integrations",
        "status",
        server_default=sa.text("'active'"),
    )
    op.execute("UPDATE tenant_integrations SET status = 'active' WHERE status = 'connected'")


def downgrade() -> None:
    op.alter_column(
        "tenant_integrations",
        "status",
        server_default=sa.text("'connected'"),
    )
    op.execute("UPDATE tenant_integrations SET status = 'connected' WHERE status = 'active'")
