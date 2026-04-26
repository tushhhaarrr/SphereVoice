"""Do Not Call (DNC) suppression list for outbound campaign compliance.

Revision ID: 016_dnc_entries
Revises: 015_tenant_integrations
Create Date: 2026-03-17 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "016_dnc_entries"
down_revision = "015_tenant_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dnc_entries",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phone_number", sa.String(30), nullable=False),
        sa.Column("source", sa.String(50), server_default=sa.text("'manual'"), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column(
            "added_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    op.create_index(
        "idx_dnc_entries_tenant_phone", "dnc_entries", ["tenant_id", "phone_number"], unique=True
    )
    op.create_index("idx_dnc_entries_expires_at", "dnc_entries", ["expires_at"])

    op.execute("ALTER TABLE dnc_entries ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON dnc_entries
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON dnc_entries TO SphereVoice_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON dnc_entries")
    op.drop_index("idx_dnc_entries_expires_at", table_name="dnc_entries")
    op.drop_index("idx_dnc_entries_tenant_phone", table_name="dnc_entries")
    op.drop_table("dnc_entries")
