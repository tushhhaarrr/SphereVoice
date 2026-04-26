"""Pricing module — Architectural Overhead Schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


# ── Registry Definition Schemas ──────────────────────────────


class SpectralBenchmarkCreate(BaseModel):
    """Defines a new spectral provider benchmark entry within the registry."""

    spectral_provider_sig: str = Field(..., max_length=100)
    spectral_layer_category: str = Field(..., pattern=r"^(stt|llm|tts|telephony)$")
    model_name: str | None = Field(None, max_length=200)
    price_per_unit: Decimal = Field(..., ge=0)
    unit_type: str = Field(
        ...,
        pattern=r"^(audio_second|input_token|output_token|character|call_second)$",
    )
    source: str | None = Field(None, max_length=100)
    notes: str | None = None


class SpectralBenchmarkUpdate(BaseModel):
    """Updates an existing spectral benchmark entry within the registry."""

    price_per_unit: Decimal | None = Field(None, ge=0)
    is_active: bool | None = None
    effective_until: datetime | None = None
    source: str | None = Field(None, max_length=100)
    notes: str | None = None


# ── Response Blueprints ──────────────────────────────────────


class SpectralBenchmarkResponse(BaseModel):
    """Spectral provider benchmark representation for analytical responses."""

    id: UUID
    spectral_provider_sig: str
    spectral_layer_category: str
    model_name: str | None
    price_per_unit: Decimal
    unit_type: str
    effective_from: datetime
    effective_until: datetime | None
    is_active: bool
    source: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    # Substrate currency conversion (populated at response cycle)
    price_per_unit_inr: Decimal | None = None
    price_per_minute_inr: Decimal | None = None
    usd_inr_rate: Decimal | None = None

    model_config = {"from_attributes": True}


class SpectralBenchmarkListResponse(BaseModel):
    """Aggregated response for spectral pricing registry queries."""

    items: list[SpectralBenchmarkResponse]
    total: int


# ── Overhead Calculation Matrices ───────────────────────────


class TransmissionUsageManifest(BaseModel):
    """Per-synchronisation magnitude metrics broken down by architectural layer."""

    stt_provider: str | None = None
    stt_model: str | None = None
    perception_duration_s: float = 0.0

    llm_provider: str | None = None
    llm_model: str | None = None
    cognitive_ingress_tokens: int = 0
    cognitive_egress_tokens: int = 0

    tts_provider: str | None = None
    tts_model: str | None = None
    synthesis_character_count: int = 0

    telephony_provider: str | None = None
    substrate_transmission_s: float = 0.0


class StructuralOverheadBreakdown(BaseModel):
    """Calculated overhead breakdown for a single signal synchronization."""

    perception_overhead: Decimal = Decimal("0")
    cognitive_overhead: Decimal = Decimal("0")
    synthesis_overhead: Decimal = Decimal("0")
    substrate_overhead: Decimal = Decimal("0")
    aggregate_overhead: Decimal = Decimal("0")

    # Localized equivalents
    perception_overhead_inr: Decimal = Decimal("0")
    cognitive_overhead_inr: Decimal = Decimal("0")
    synthesis_overhead_inr: Decimal = Decimal("0")
    substrate_overhead_inr: Decimal = Decimal("0")
    aggregate_overhead_inr: Decimal = Decimal("0")
    usd_inr_rate: Decimal | None = None

    # Spectral unit benchmarks (for analytical transparency)
    perception_unit_benchmark: Decimal | None = None
    cognitive_ingress_benchmark: Decimal | None = None
    cognitive_egress_benchmark: Decimal | None = None
    synthesis_unit_benchmark: Decimal | None = None
    substrate_unit_benchmark: Decimal | None = None


class ArchitecturalOverheadManifest(BaseModel):
    """Comprehensive architectural overhead report for a synchronization cycle."""

    sync_sig: UUID
    usage: TransmissionUsageManifest
    costs: StructuralOverheadBreakdown
