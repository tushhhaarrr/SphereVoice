"""028 — Increase cost column precision to Numeric(12, 8).

Revision ID: 028_cost_precision
Revises: 027_exchange_rates

Numeric(10, 4) only captures $0.0001 resolution — far too coarse for
per-call micro-costs (e.g. 50 s Groq Whisper STT = $0.00092593).
Upgrading to Numeric(12, 8) captures sub-cent precision properly.
"""

revision = "028_cost_precision"
down_revision = "027_exchange_rates"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    for col in ("stt_cost", "llm_cost", "tts_cost", "telephony_cost", "total_cost"):
        op.alter_column(
            "calls",
            col,
            type_=sa.Numeric(12, 8),
            existing_type=sa.Numeric(10, 4),
            existing_nullable=True,
        )


def downgrade() -> None:
    for col in ("stt_cost", "llm_cost", "tts_cost", "telephony_cost", "total_cost"):
        op.alter_column(
            "calls",
            col,
            type_=sa.Numeric(10, 4),
            existing_type=sa.Numeric(12, 8),
            existing_nullable=True,
        )
