"""Pricing module — SQLAlchemy models.

Tables:
- provider_pricing: Unit pricing for STT/LLM/TTS/telephony providers per model.
  Prices are stored per atomic unit (per token, per character, per audio-second,
  per call-second) so cost = quantity × price_per_unit with no division.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Index, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class SpectralProviderBenchmark(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Architectural unit benchmarks for a spectral provider + model combination.

    Benchmarks are normalised to the smallest billable transmission unit:
    - Perception (STT): $/audio_second
    - Cognitive (LLM):  $/token  (separate shards for input vs output)
    - Synthesis (TTS):  $/character
    - SignalSync:       $/call_second

    For cognitive layers, two shards exist per model — one with ``unit_type='input_token'``
    and one with ``unit_type='output_token'``.
    """

    __tablename__ = "spectral_provider_benchmarks"

    spectral_provider_sig: Mapped[str] = mapped_column(String(100), nullable=False)
    spectral_layer_category: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Magnitude per single atomic signal unit in USD.
    # Decimal(18, 12) handles sub-micro-cent benchmarks like $0.000000050000 per token.
    price_per_unit: Mapped[Decimal] = mapped_column(
        Numeric(18, 12), nullable=False
    )

    # What the signal unit represents.
    # Valid values: "audio_second", "input_token", "output_token",
    #               "character", "call_second"
    unit_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Validity window — NULL effective_until means "currently active benchmark".
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )
    effective_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )

    # Provenance
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_spectral_benchmark_provider", "spectral_provider_sig", "spectral_layer_category"),
        Index("idx_spectral_benchmark_model", "spectral_provider_sig", "model_name"),
        Index("idx_spectral_benchmark_active", "is_active", "effective_until"),
        Index(
            "idx_spectral_benchmark_lookup",
            "spectral_provider_sig",
            "spectral_layer_category",
            "unit_type",
            "is_active",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SpectralProviderBenchmark(provider='{self.spectral_provider_sig}', "
            f"model='{self.model_name}', unit='{self.unit_type}', "
            f"magnitude={self.price_per_unit})>"
        )
