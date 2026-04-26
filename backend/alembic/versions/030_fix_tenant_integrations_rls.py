"""Add admin bypass to tenant_integrations RLS policy.

The original policy (migration 015) only checks tenant_id match, which blocks
admin users from viewing integrations when accessing a workspace.  All other
tables (agents, calls, crm_integrations, etc.) include an admin bypass.

Revision ID: 030_fix_tenant_integ_rls
Revises: 029_default_outbound
Create Date: 2026-03-21 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "030_fix_tenant_integ_rls"
down_revision = "029_default_outbound"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old restrictive policy
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant_integrations")

    # Recreate with admin bypass (matches crm_integrations pattern)
    op.execute("""
        CREATE POLICY tenant_isolation ON tenant_integrations
            FOR ALL
            USING (
                tenant_id = current_setting('app.current_tenant_id', true)::UUID
                OR current_setting('app.user_role', true) = 'admin'
            )
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant_integrations")
    op.execute("""
        CREATE POLICY tenant_isolation ON tenant_integrations
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """)
