"""Campaign definitions for bulk outbound call campaigns.

Revision ID: 017_campaigns
Revises: 016_dnc_entries
Create Date: 2026-03-18 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "017_campaigns"
down_revision = "016_dnc_entries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("agent_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "source_type",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'crm'"),
        ),
        sa.Column("source_config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("variable_mapping", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "writeback_mapping", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("from_number", sa.String(20), nullable=True),
        sa.Column("max_concurrent", sa.Integer, nullable=False, server_default=sa.text("5")),
        sa.Column("calls_per_minute", sa.Integer, nullable=False, server_default=sa.text("10")),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default=sa.text("2")),
        sa.Column("retry_delay_minutes", sa.Integer, nullable=False, server_default=sa.text("60")),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calling_window", JSONB, nullable=True, server_default=sa.text("'{}'::jsonb")),
        sa.Column("total_contacts", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("completed_calls", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("successful_calls", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("failed_calls", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    op.create_index("ix_campaigns_tenant_id", "campaigns", ["tenant_id"])
    op.create_index("ix_campaigns_status", "campaigns", ["status"])
    op.create_index("ix_campaigns_agent_id", "campaigns", ["agent_id"])

    op.execute("ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON campaigns
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON campaigns TO SphereVoice_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON campaigns")
    op.drop_index("ix_campaigns_agent_id", table_name="campaigns")
    op.drop_index("ix_campaigns_status", table_name="campaigns")
    op.drop_index("ix_campaigns_tenant_id", table_name="campaigns")
    op.drop_table("campaigns")
