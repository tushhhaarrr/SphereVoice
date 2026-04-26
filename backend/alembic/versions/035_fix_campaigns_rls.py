"""Add admin bypass to campaigns and campaign_contacts RLS policies.

The original policies (migrations 017 & 018) only check tenant_id match,
which blocks admin users from viewing or creating campaigns when accessing
a workspace.  All other tables include an admin bypass.

Revision ID: 035_fix_campaigns_rls
Revises: 034_ab_testing_scheduling
Create Date: 2026-03-26 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "035_fix_campaigns_rls"
down_revision = "034_ab_testing_scheduling"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── campaigns table ─────────────────────────────────────────────────
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON campaigns")
    op.execute("""
        CREATE POLICY tenant_isolation ON campaigns
            FOR ALL
            USING (
                tenant_id = current_setting('app.current_tenant_id', true)::UUID
                OR current_setting('app.user_role', true) = 'admin'
            )
    """)

    # ── campaign_contacts table ─────────────────────────────────────────
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON campaign_contacts")
    op.execute("""
        CREATE POLICY tenant_isolation ON campaign_contacts
            FOR ALL
            USING (
                tenant_id = current_setting('app.current_tenant_id', true)::UUID
                OR current_setting('app.user_role', true) = 'admin'
            )
    """)


def downgrade() -> None:
    # Restore original restrictive policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON campaigns")
    op.execute("""
        CREATE POLICY tenant_isolation ON campaigns
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """)

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON campaign_contacts")
    op.execute("""
        CREATE POLICY tenant_isolation ON campaign_contacts
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """)
