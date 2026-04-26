"""Local CRM contacts cache for sub-5ms inbound call enrichment.

Revision ID: 014_crm_contacts_cache
Revises: 013_crm_sync_log
Create Date: 2026-03-20 00:00:00.000000

Stores a synced copy of Zoho CRM Contacts and Leads with normalised
E.164 phone numbers.  Populated by initial sync + 15-min incremental
sync + write-through on post-call push.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "014_crm_contacts_cache"
down_revision = "013_crm_sync_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_contacts_cache",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_id", UUID(as_uuid=True), sa.ForeignKey("crm_integrations.id", ondelete="CASCADE"), nullable=False),
        # Zoho identity
        sa.Column("zoho_record_id", sa.String(100), nullable=False),
        sa.Column("zoho_module", sa.String(20), nullable=False),
        # Normalised phones
        sa.Column("phone_e164", sa.String(30), nullable=True),
        sa.Column("phone_raw", sa.String(50), nullable=True),
        sa.Column("mobile_e164", sa.String(30), nullable=True),
        sa.Column("mobile_raw", sa.String(50), nullable=True),
        # Core fields
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        # Lead fields
        sa.Column("lead_status", sa.String(100), nullable=True),
        sa.Column("lead_source", sa.String(100), nullable=True),
        # Location
        sa.Column("mailing_city", sa.String(100), nullable=True),
        sa.Column("mailing_state", sa.String(100), nullable=True),
        sa.Column("mailing_country", sa.String(100), nullable=True),
        # Owner
        sa.Column("owner_name", sa.String(255), nullable=True),
        # Raw snapshot
        sa.Column("raw_data", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        # Zoho timestamps
        sa.Column("zoho_created_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("zoho_modified_time", sa.DateTime(timezone=True), nullable=True),
        # Sync tracking
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        # Standard timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # Indexes
    op.create_index("idx_crm_cache_tenant_zoho", "crm_contacts_cache", ["tenant_id", "zoho_record_id"], unique=True)
    op.create_index("idx_crm_cache_phone", "crm_contacts_cache", ["phone_e164"])
    op.create_index("idx_crm_cache_mobile", "crm_contacts_cache", ["mobile_e164"])
    op.create_index("idx_crm_cache_email", "crm_contacts_cache", ["email"])
    op.create_index("idx_crm_cache_integration", "crm_contacts_cache", ["integration_id"])
    op.create_index("idx_crm_cache_name", "crm_contacts_cache", ["full_name"])

    # RLS
    op.execute("ALTER TABLE crm_contacts_cache ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON crm_contacts_cache
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON crm_contacts_cache TO SphereVoice_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON crm_contacts_cache")
    op.drop_index("idx_crm_cache_name", table_name="crm_contacts_cache")
    op.drop_index("idx_crm_cache_integration", table_name="crm_contacts_cache")
    op.drop_index("idx_crm_cache_email", table_name="crm_contacts_cache")
    op.drop_index("idx_crm_cache_mobile", table_name="crm_contacts_cache")
    op.drop_index("idx_crm_cache_phone", table_name="crm_contacts_cache")
    op.drop_index("idx_crm_cache_tenant_zoho", table_name="crm_contacts_cache")
    op.drop_table("crm_contacts_cache")
