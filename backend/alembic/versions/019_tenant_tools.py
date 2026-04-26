"""Tenant tool library — reusable tools assignable to agents for in-call function calling.

Revision ID: 019_tenant_tools
Revises: 018_campaign_contacts
Create Date: 2026-03-18 00:00:02.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "019_tenant_tools"
down_revision = "018_campaign_contacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_tools",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "integration_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenant_integrations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column(
            "parameters_schema",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "execution_type",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'integration'"),
        ),
        sa.Column(
            "execution_config",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
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
        sa.UniqueConstraint("tenant_id", "name", name="uq_tenant_tools_tenant_name"),
    )

    op.create_index("ix_tenant_tools_tenant_id", "tenant_tools", ["tenant_id"])
    op.create_index("ix_tenant_tools_name", "tenant_tools", ["name"])
    op.create_index("ix_tenant_tools_category", "tenant_tools", ["category"])

    op.execute("ALTER TABLE tenant_tools ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON tenant_tools
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_tools TO SphereVoice_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant_tools")
    op.drop_index("ix_tenant_tools_category", table_name="tenant_tools")
    op.drop_index("ix_tenant_tools_name", table_name="tenant_tools")
    op.drop_index("ix_tenant_tools_tenant_id", table_name="tenant_tools")
    op.drop_table("tenant_tools")
