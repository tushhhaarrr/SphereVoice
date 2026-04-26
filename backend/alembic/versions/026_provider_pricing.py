"""Add provider_pricing table and usage_metrics column on calls.

Revision ID: 026_provider_pricing
Revises: 025_rename_zoho_to_crm
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "026_provider_pricing"
down_revision = "025_rename_zoho_to_crm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── provider_pricing table ───────────────────────────────
    op.create_table(
        "provider_pricing",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("provider_name", sa.String(100), nullable=False),
        sa.Column("provider_category", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=True),
        sa.Column("price_per_unit", sa.Numeric(18, 12), nullable=False),
        sa.Column("unit_type", sa.String(50), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_index("idx_pricing_provider", "provider_pricing",
                    ["provider_name", "provider_category"])
    op.create_index("idx_pricing_model", "provider_pricing",
                    ["provider_name", "model_name"])
    op.create_index("idx_pricing_active", "provider_pricing",
                    ["is_active", "effective_until"])
    op.create_index("idx_pricing_lookup", "provider_pricing",
                    ["provider_name", "provider_category", "unit_type", "is_active"])

    # ── Add usage_metrics JSONB column to calls ──────────────
    op.add_column(
        "calls",
        sa.Column("usage_metrics", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("calls", "usage_metrics")
    op.drop_index("idx_pricing_lookup", table_name="provider_pricing")
    op.drop_index("idx_pricing_active", table_name="provider_pricing")
    op.drop_index("idx_pricing_model", table_name="provider_pricing")
    op.drop_index("idx_pricing_provider", table_name="provider_pricing")
    op.drop_table("provider_pricing")
