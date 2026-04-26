"""CRM integrations table — Zoho CRM OAuth token storage, per-tenant.

Revision ID: 011_crm_integrations
Revises: 010_agent_call_direction
Create Date: 2026-03-14 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "011_crm_integrations"
down_revision = "010_agent_call_direction"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_integrations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), server_default=sa.text("'zoho_crm'"), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'connected'"), nullable=False),
        sa.Column("access_token_encrypted", sa.Text, nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text, nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_center", sa.String(20), server_default=sa.text("'com'"), nullable=False),
        sa.Column("org_id", sa.String(100), nullable=True),
        sa.Column("org_name", sa.String(255), nullable=True),
        sa.Column(
            "config",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "provider", name="uq_crm_integrations_tenant_provider"),
    )

    op.create_index("idx_crm_integrations_tenant", "crm_integrations", ["tenant_id"])
    op.create_index("idx_crm_integrations_provider", "crm_integrations", ["provider"])

    # Attach updated_at trigger (function update_updated_at() defined in migration 001)
    op.execute(
        "CREATE TRIGGER trg_crm_integrations_updated_at "
        "BEFORE UPDATE ON crm_integrations "
        "FOR EACH ROW EXECUTE FUNCTION update_updated_at()"
    )

    # Grant to app role
    op.execute("GRANT ALL ON TABLE crm_integrations TO SphereVoice_app")

    # Enable Row Level Security
    op.execute("ALTER TABLE crm_integrations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE crm_integrations FORCE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY tenant_isolation_crm_integrations ON crm_integrations
            FOR ALL
            USING (
                tenant_id = current_setting('app.current_tenant_id', true)::UUID
                OR current_setting('app.user_role', true) = 'admin'
            )
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_crm_integrations ON crm_integrations")
    op.execute("DROP TRIGGER IF EXISTS trg_crm_integrations_updated_at ON crm_integrations")
    op.drop_table("crm_integrations")
