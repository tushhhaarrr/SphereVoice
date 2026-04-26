"""CRM sync log — tracks every push of call data to Zoho CRM, per tenant.

Revision ID: 013_crm_sync_log
Revises: 012_share_link_dynamic_variables
Create Date: 2026-03-15 00:00:00.000000

This table records every post-call CRM push so we can audit, debug, and
display sync status in the frontend.  It also adds a `crm_contact_id`
column to the calls table for inbound-call enrichment caching.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "013_crm_sync_log"
down_revision = "012_share_link_dynamic_variables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── crm_sync_log table ───────────────────────────────────
    op.create_table(
        "crm_sync_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_id", UUID(as_uuid=True), sa.ForeignKey("crm_integrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("call_id", UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="SET NULL"), nullable=True),
        sa.Column("direction", sa.String(20), nullable=False),  # "push" | "enrich"
        sa.Column("status", sa.String(20), nullable=False, server_default="success"),  # "success" | "error"
        sa.Column("zoho_module", sa.String(50), nullable=True),  # "Contacts" | "Leads" | "Calls"
        sa.Column("zoho_record_id", sa.String(100), nullable=True),
        sa.Column("details", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_index("idx_crm_sync_log_tenant", "crm_sync_log", ["tenant_id"])
    op.create_index("idx_crm_sync_log_call", "crm_sync_log", ["call_id"])
    op.create_index("idx_crm_sync_log_created", "crm_sync_log", ["created_at"])

    # Enable RLS
    op.execute("ALTER TABLE crm_sync_log ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON crm_sync_log
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """)
    op.execute("GRANT SELECT, INSERT ON crm_sync_log TO SphereVoice_app")

    # ── Add crm_contact_id to calls table ────────────────────
    op.add_column(
        "calls",
        sa.Column("crm_contact_id", sa.String(100), nullable=True),
    )
    op.create_index("idx_calls_crm_contact", "calls", ["crm_contact_id"])


def downgrade() -> None:
    op.drop_index("idx_calls_crm_contact", table_name="calls")
    op.drop_column("calls", "crm_contact_id")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON crm_sync_log")
    op.drop_index("idx_crm_sync_log_created", table_name="crm_sync_log")
    op.drop_index("idx_crm_sync_log_call", table_name="crm_sync_log")
    op.drop_index("idx_crm_sync_log_tenant", table_name="crm_sync_log")
    op.drop_table("crm_sync_log")
