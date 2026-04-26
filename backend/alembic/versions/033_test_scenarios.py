"""Add test_scenarios and test_call_results tables.

Supports scenario-based test calls: pre-filled CRM context, expected
extraction outcomes, and automated pass/fail validation.

Revision ID: 033_test_scenarios
Revises: 032_call_tool_executions
Create Date: 2026-03-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "033_test_scenarios"
down_revision = "032_call_tool_executions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "test_scenarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("dynamic_variables", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("expected_outcomes", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_test_scenarios_agent", "test_scenarios", ["agent_id"])

    op.create_table(
        "test_call_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_scenarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("call_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_version", sa.Integer(), nullable=True),
        sa.Column("extracted_data", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("expected_outcomes", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("match_results", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("total_fields", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("matched_fields", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_test_call_results_scenario", "test_call_results", ["scenario_id"])
    op.create_index("idx_test_call_results_call", "test_call_results", ["call_id"])


def downgrade() -> None:
    op.drop_table("test_call_results")
    op.drop_table("test_scenarios")
