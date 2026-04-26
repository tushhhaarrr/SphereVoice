"""Add A/B testing and scheduling columns to campaigns.

- campaigns: variant_agent_id, ab_split_percent
- campaign_contacts: assigned_agent_id

Revision ID: 034_ab_testing_scheduling
Revises: 033_test_scenarios
Create Date: 2026-03-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "034_ab_testing_scheduling"
down_revision = "033_test_scenarios"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A/B testing columns on campaigns
    op.add_column(
        "campaigns",
        sa.Column("variant_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "campaigns",
        sa.Column(
            "ab_split_percent",
            sa.Integer(),
            server_default=sa.text("50"),
            nullable=False,
        ),
    )

    # Track which agent variant handled each contact
    op.add_column(
        "campaign_contacts",
        sa.Column("assigned_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Index for variant agent lookups
    op.create_index(
        "ix_campaigns_variant_agent_id",
        "campaigns",
        ["variant_agent_id"],
        unique=False,
    )
    op.create_index(
        "ix_campaign_contacts_assigned_agent_id",
        "campaign_contacts",
        ["assigned_agent_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_campaign_contacts_assigned_agent_id", table_name="campaign_contacts")
    op.drop_index("ix_campaigns_variant_agent_id", table_name="campaigns")
    op.drop_column("campaign_contacts", "assigned_agent_id")
    op.drop_column("campaigns", "ab_split_percent")
    op.drop_column("campaigns", "variant_agent_id")
