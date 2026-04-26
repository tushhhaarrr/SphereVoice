"""027 — exchange_rates table for USD→INR live rate caching.

Revision ID: 027_exchange_rates
Revises: 026_provider_pricing
"""

revision = "027_exchange_rates"
down_revision = "026_provider_pricing"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("from_currency", sa.String(10), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("to_currency", sa.String(10), nullable=False, server_default=sa.text("'INR'")),
        sa.Column("rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_exchange_rate_pair", "exchange_rates", ["from_currency", "to_currency"])
    op.create_index("idx_exchange_rate_fetched", "exchange_rates", ["fetched_at"])


def downgrade() -> None:
    op.drop_index("idx_exchange_rate_fetched", table_name="exchange_rates")
    op.drop_index("idx_exchange_rate_pair", table_name="exchange_rates")
    op.drop_table("exchange_rates")
