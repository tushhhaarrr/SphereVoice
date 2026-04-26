"""029 — Add is_default_outbound flag to phone_numbers.

Revision ID: 029_phone_number_default_outbound
Revises: 028_cost_precision

Allows marking one phone number per tenant as the default outbound
caller ID for test calls and outbound campaigns.
"""

revision = "029_default_outbound"
down_revision = "028_cost_precision"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column(
        "phone_numbers",
        sa.Column(
            "is_default_outbound",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("phone_numbers", "is_default_outbound")
