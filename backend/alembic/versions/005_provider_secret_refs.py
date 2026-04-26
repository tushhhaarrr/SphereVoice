"""Add provider secret reference field for vault-backed global keys.

Revision ID: 005_provider_secret_refs
Revises: 004_fix_audit_trigger_nil_tenant
Create Date: 2026-03-07 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "005_provider_secret_refs"
down_revision = "004_fix_audit_trigger_nil_tenant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("provider_keys", sa.Column("secret_ref", sa.String(length=255), nullable=True))
    op.alter_column("provider_keys", "api_key_encrypted", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column(
        "provider_keys",
        "api_key_encrypted",
        existing_type=sa.Text(),
        nullable=False,
        existing_nullable=True,
    )
    op.drop_column("provider_keys", "secret_ref")