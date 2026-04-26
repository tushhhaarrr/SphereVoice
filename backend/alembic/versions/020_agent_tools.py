"""Agent-to-tool join table — binds tenant tools to specific agents for in-call function calling.

Revision ID: 020_agent_tools
Revises: 019_tenant_tools
Create Date: 2026-03-18 00:00:03.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "020_agent_tools"
down_revision = "019_tenant_tools"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_tools",
        sa.Column(
            "agent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "tool_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenant_tools.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "config",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    op.create_index("ix_agent_tools_agent_id", "agent_tools", ["agent_id"])
    op.create_index("ix_agent_tools_tool_id", "agent_tools", ["tool_id"])

    # No RLS on this join table — access is controlled at the tenant_tools level
    op.execute("GRANT SELECT, INSERT, DELETE ON agent_tools TO SphereVoice_app")


def downgrade() -> None:
    op.drop_index("ix_agent_tools_tool_id", table_name="agent_tools")
    op.drop_index("ix_agent_tools_agent_id", table_name="agent_tools")
    op.drop_table("agent_tools")
