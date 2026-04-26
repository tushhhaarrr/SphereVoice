"""Generic tenant integration registry for all provider categories.

Revision ID: 015_tenant_integrations
Revises: 014_crm_contacts_cache
Create Date: 2026-03-17 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "015_tenant_integrations"
down_revision = "014_crm_contacts_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_integrations",
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
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'connected'"), nullable=False),
        sa.Column("credentials_encrypted", sa.Text, nullable=True),
        sa.Column("config", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
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

    op.create_index(
        "idx_tenant_integrations_tenant_name",
        "tenant_integrations",
        ["tenant_id", "name"],
        unique=True,
    )
    op.create_index(
        "idx_tenant_integrations_category",
        "tenant_integrations",
        ["tenant_id", "category", "provider"],
    )

    op.execute("ALTER TABLE tenant_integrations ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON tenant_integrations
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_integrations TO SphereVoice_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant_integrations")
    op.drop_index("idx_tenant_integrations_category", table_name="tenant_integrations")
    op.drop_index("idx_tenant_integrations_tenant_name", table_name="tenant_integrations")
    op.drop_table("tenant_integrations")
