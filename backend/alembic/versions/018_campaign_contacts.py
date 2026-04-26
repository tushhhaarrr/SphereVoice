"""Campaign contacts — per-row state machine for each contact in a campaign.

Revision ID: 018_campaign_contacts
Revises: 017_campaigns
Create Date: 2026-03-18 00:00:01.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "018_campaign_contacts"
down_revision = "017_campaigns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaign_contacts",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "campaign_id",
            UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phone_number", sa.String(30), nullable=False),
        sa.Column("crm_record_id", sa.String(100), nullable=True),
        sa.Column("crm_module", sa.String(50), nullable=True),
        sa.Column("contact_data", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("call_id", UUID(as_uuid=True), nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default=sa.text("3")),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extracted_data", JSONB, nullable=True, server_default=sa.text("'{}'::jsonb")),
        sa.Column("writeback_status", sa.String(20), nullable=True),
        sa.Column("writeback_error", sa.Text, nullable=True),
        sa.Column("tool_results", JSONB, nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("priority", sa.Integer, nullable=False, server_default=sa.text("0")),
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

    op.create_index("ix_campaign_contacts_campaign_id", "campaign_contacts", ["campaign_id"])
    op.create_index(
        "ix_campaign_contacts_status",
        "campaign_contacts",
        ["campaign_id", "status"],
    )
    op.create_index("ix_campaign_contacts_phone_number", "campaign_contacts", ["phone_number"])
    op.create_index("ix_campaign_contacts_next_retry_at", "campaign_contacts", ["next_retry_at"])
    op.create_index("ix_campaign_contacts_crm_record_id", "campaign_contacts", ["crm_record_id"])

    op.execute("ALTER TABLE campaign_contacts ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON campaign_contacts
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON campaign_contacts TO SphereVoice_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON campaign_contacts")
    op.drop_index("ix_campaign_contacts_crm_record_id", table_name="campaign_contacts")
    op.drop_index("ix_campaign_contacts_next_retry_at", table_name="campaign_contacts")
    op.drop_index("ix_campaign_contacts_phone_number", table_name="campaign_contacts")
    op.drop_index("ix_campaign_contacts_status", table_name="campaign_contacts")
    op.drop_index("ix_campaign_contacts_campaign_id", table_name="campaign_contacts")
    op.drop_table("campaign_contacts")
