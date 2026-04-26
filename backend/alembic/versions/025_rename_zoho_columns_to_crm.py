"""Rename Zoho-specific columns to provider-agnostic CRM names.

Renames columns in crm_contacts_cache and crm_sync_log so the schema
is CRM-provider-neutral, enabling future HubSpot/Salesforce support.

Revision ID: 025_rename_zoho_to_crm
Revises: 024_call_writeback_status
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "025_rename_zoho_to_crm"
down_revision = "024_call_writeback_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── crm_contacts_cache ───────────────────────────────────
    op.alter_column("crm_contacts_cache", "zoho_record_id", new_column_name="crm_record_id")
    op.alter_column("crm_contacts_cache", "zoho_module", new_column_name="crm_module")
    op.alter_column("crm_contacts_cache", "zoho_created_time", new_column_name="crm_created_time")
    op.alter_column("crm_contacts_cache", "zoho_modified_time", new_column_name="crm_modified_time")

    # Rename the unique index that references the old column name
    op.drop_index("idx_crm_cache_tenant_zoho", table_name="crm_contacts_cache")
    op.create_index(
        "idx_crm_cache_tenant_record",
        "crm_contacts_cache",
        ["tenant_id", "crm_record_id"],
        unique=True,
    )

    # ── crm_sync_log ─────────────────────────────────────────
    op.alter_column("crm_sync_log", "zoho_module", new_column_name="crm_module")
    op.alter_column("crm_sync_log", "zoho_record_id", new_column_name="crm_record_id")


def downgrade() -> None:
    # ── crm_sync_log ─────────────────────────────────────────
    op.alter_column("crm_sync_log", "crm_record_id", new_column_name="zoho_record_id")
    op.alter_column("crm_sync_log", "crm_module", new_column_name="zoho_module")

    # ── crm_contacts_cache ───────────────────────────────────
    op.drop_index("idx_crm_cache_tenant_record", table_name="crm_contacts_cache")
    op.create_index(
        "idx_crm_cache_tenant_zoho",
        "crm_contacts_cache",
        ["tenant_id", "zoho_record_id"],
        unique=True,
    )

    op.alter_column("crm_contacts_cache", "crm_modified_time", new_column_name="zoho_modified_time")
    op.alter_column("crm_contacts_cache", "crm_created_time", new_column_name="zoho_created_time")
    op.alter_column("crm_contacts_cache", "crm_module", new_column_name="zoho_module")
    op.alter_column("crm_contacts_cache", "crm_record_id", new_column_name="zoho_record_id")
