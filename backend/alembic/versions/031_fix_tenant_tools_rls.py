"""Add admin bypass to tenant_tools RLS policy.

Same issue as tenant_integrations (fixed in 024): the policy only checks
tenant_id match, blocking admin users from viewing/managing tools.

Revision ID: 031_fix_tenant_tools_rls
Revises: 030_fix_tenant_integ_rls
Create Date: 2026-03-21 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "031_fix_tenant_tools_rls"
down_revision = "030_fix_tenant_integ_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant_tools")
    op.execute("""
        CREATE POLICY tenant_isolation ON tenant_tools
            FOR ALL
            USING (
                tenant_id = current_setting('app.current_tenant_id', true)::UUID
                OR current_setting('app.user_role', true) = 'admin'
            )
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant_tools")
    op.execute("""
        CREATE POLICY tenant_isolation ON tenant_tools
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """)
