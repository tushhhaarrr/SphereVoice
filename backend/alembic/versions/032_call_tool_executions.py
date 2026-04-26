"""Add call_tool_executions table for tool audit logging.

Records every tool call made during a live voice call with arguments,
result, timing, and status for post-call review.

Revision ID: 032_call_tool_executions
Revises: 031_fix_tenant_tools_rls
Create Date: 2026-03-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "032_call_tool_executions"
down_revision = "031_fix_tenant_tools_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "call_tool_executions",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("call_id", UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("tool_category", sa.String(50), nullable=False),
        sa.Column("arguments", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("result", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("duration_ms", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_call_tool_executions_call_id", "call_tool_executions", ["call_id"])
    op.create_index("idx_call_tool_executions_tenant_id", "call_tool_executions", ["tenant_id"])

    # Enable RLS
    op.execute("ALTER TABLE call_tool_executions ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON call_tool_executions
            FOR ALL
            USING (
                tenant_id = current_setting('app.current_tenant_id', true)::UUID
                OR current_setting('app.user_role', true) = 'admin'
                OR tenant_id IS NULL
            )
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON call_tool_executions")
    op.drop_index("idx_call_tool_executions_tenant_id", table_name="call_tool_executions")
    op.drop_index("idx_call_tool_executions_call_id", table_name="call_tool_executions")
    op.drop_table("call_tool_executions")
