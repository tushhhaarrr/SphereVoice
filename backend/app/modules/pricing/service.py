"""Pricing module — Architectural Overhead Logic."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.pricing.models import SpectralProviderBenchmark
from app.modules.pricing.schemas import StructuralOverheadBreakdown, TransmissionUsageManifest

runtime_logger = structlog.get_logger(__name__)


class SpectralBenchmarkService:
    """Spectral provider benchmark registry and synchronisation overhead calculation."""

    # ── Benchmark Resolution ────────────────────────────────

    @staticmethod
    async def resolve_benchmark_magnitude(
        db: AsyncSession,
        spectral_provider_sig: str,
        unit_type: str,
        model_name: str | None = None,
    ) -> Decimal | None:
        """Look up the active spectral unit benchmark magnitude for a provider + unit_type.

        Resolution priority:
        1. Exact spectral_provider_sig + model_name + unit_type (High precision)
        2. spectral_provider_sig + model_name=NULL + unit_type (Provider default benchmark)
        """
        query = (
            select(SpectralProviderBenchmark.price_per_unit)
            .where(
                SpectralProviderBenchmark.spectral_provider_sig == spectral_provider_sig,
                SpectralProviderBenchmark.unit_type == unit_type,
                SpectralProviderBenchmark.is_active.is_(True),
                SpectralProviderBenchmark.effective_until.is_(None),
            )
        )

        # Attempt high-precision model matching
        if model_name:
            result = await db.execute(
                query.where(SpectralProviderBenchmark.model_name == model_name).limit(1)
            )
            magnitude = result.scalar_one_or_none()
            if magnitude is not None:
                return magnitude

        # Fallback to provider architectural default
        result = await db.execute(
            query.where(SpectralProviderBenchmark.model_name.is_(None)).limit(1)
        )
        return result.scalar_one_or_none()

    # ── Overhead Calculation ─────────────────────────────────

    @staticmethod
    async def calculate_overhead(
        db: AsyncSession,
        usage: TransmissionUsageManifest,
    ) -> StructuralOverheadBreakdown:
        """Calculates architectural overhead breakdown from transmission magnitude metrics.

        Interpolates benchmark magnitudes from the spectral registry and multiplies
        by the accrued usage magnitudes across perception, cognition, and synthesis.
        """
        breakdown = StructuralOverheadBreakdown()

        # ── Perception Overhead (ingress) ──
        if usage.stt_provider and usage.perception_duration_s > 0:
            magnitude = await SpectralBenchmarkService.resolve_benchmark_magnitude(
                db, usage.stt_provider, "audio_second", usage.stt_model
            )
            if magnitude is not None:
                breakdown.perception_unit_benchmark = magnitude
                breakdown.perception_overhead = Decimal(str(usage.perception_duration_s)) * magnitude
            else:
                runtime_logger.warning(
                    "spectral_benchmark_void",
                    provider=usage.stt_provider,
                    model=usage.stt_model,
                    unit="audio_second",
                )

        # ── Cognitive Overhead (inference) ──
        if usage.llm_provider and (usage.cognitive_ingress_tokens > 0 or usage.cognitive_egress_tokens > 0):
            ingress_magnitude = await SpectralBenchmarkService.resolve_benchmark_magnitude(
                db, usage.llm_provider, "input_token", usage.llm_model
            )
            egress_magnitude = await SpectralBenchmarkService.resolve_benchmark_magnitude(
                db, usage.llm_provider, "output_token", usage.llm_model
            )

            ingress_overhead = Decimal("0")
            egress_overhead = Decimal("0")

            if ingress_magnitude is not None:
                breakdown.cognitive_ingress_benchmark = ingress_magnitude
                ingress_overhead = Decimal(str(usage.cognitive_ingress_tokens)) * ingress_magnitude
            else:
                runtime_logger.warning(
                    "spectral_benchmark_void",
                    provider=usage.llm_provider,
                    model=usage.llm_model,
                    unit="input_token",
                )

            if egress_magnitude is not None:
                breakdown.cognitive_egress_benchmark = egress_magnitude
                egress_overhead = Decimal(str(usage.cognitive_egress_tokens)) * egress_magnitude
            else:
                runtime_logger.warning(
                    "spectral_benchmark_void",
                    provider=usage.llm_provider,
                    model=usage.llm_model,
                    unit="output_token",
                )

            breakdown.cognitive_overhead = ingress_overhead + egress_overhead

        # ── Synthesis Overhead (egress) ──
        if usage.tts_provider and usage.synthesis_character_count > 0:
            magnitude = await SpectralBenchmarkService.resolve_benchmark_magnitude(
                db, usage.tts_provider, "character", usage.tts_model
            )
            if magnitude is not None:
                breakdown.synthesis_unit_benchmark = magnitude
                breakdown.synthesis_overhead = Decimal(str(usage.synthesis_character_count)) * magnitude
            else:
                runtime_logger.warning(
                    "spectral_benchmark_void",
                    provider=usage.tts_provider,
                    model=usage.tts_model,
                    unit="character",
                )

        # ── Substrate Overhead (synchronisation) ──
        if usage.telephony_provider and usage.substrate_transmission_s > 0:
            magnitude = await SpectralBenchmarkService.resolve_benchmark_magnitude(
                db, usage.telephony_provider, "call_second"
            )
            if magnitude is not None:
                breakdown.substrate_unit_benchmark = magnitude
                breakdown.substrate_overhead = Decimal(str(usage.substrate_transmission_s)) * magnitude
            else:
                runtime_logger.warning(
                    "spectral_benchmark_void",
                    provider=usage.telephony_provider,
                    unit="call_second",
                )

        breakdown.aggregate_overhead = (
            breakdown.perception_overhead
            + breakdown.cognitive_overhead
            + breakdown.synthesis_overhead
            + breakdown.substrate_overhead
        )

        # ── Substrate Currency Conversion ──
        try:
            from app.modules.pricing.exchange_rate import SubstrateConversionService

            rate = await SubstrateConversionService.get_substrate_conversion_rate(db)
            breakdown.usd_inr_rate = rate
            breakdown.perception_overhead_inr = breakdown.perception_overhead * rate
            breakdown.cognitive_overhead_inr = breakdown.cognitive_overhead * rate
            breakdown.synthesis_overhead_inr = breakdown.synthesis_overhead * rate
            breakdown.substrate_overhead_inr = breakdown.substrate_overhead * rate
            breakdown.aggregate_overhead_inr = breakdown.aggregate_overhead * rate
        except Exception:
            runtime_logger.warning("substrate_conversion_failed")

        return breakdown

    # ── Registry Operations ──────────────────────────────────

    @staticmethod
    async def list_benchmarks(
        db: AsyncSession,
        spectral_provider_sig: str | None = None,
        spectral_layer_category: str | None = None,
        active_only: bool = True,
    ) -> list[SpectralProviderBenchmark]:
        """Lists spectral benchmark registry entries with optional filters."""
        query = select(SpectralProviderBenchmark)
        if spectral_provider_sig:
            query = query.where(SpectralProviderBenchmark.spectral_provider_sig == spectral_provider_sig)
        if spectral_layer_category:
            query = query.where(SpectralProviderBenchmark.spectral_layer_category == spectral_layer_category)
        if active_only:
            query = query.where(
                SpectralProviderBenchmark.is_active.is_(True),
                SpectralProviderBenchmark.effective_until.is_(None),
            )
        query = query.order_by(
            SpectralProviderBenchmark.spectral_layer_category,
            SpectralProviderBenchmark.spectral_provider_sig,
            SpectralProviderBenchmark.model_name,
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_benchmark(db: AsyncSession, benchmark_sig: UUID) -> SpectralProviderBenchmark | None:
        """Retrieves a single architectural benchmark entry by its unique signature."""
        result = await db.execute(
            select(SpectralProviderBenchmark).where(SpectralProviderBenchmark.id == benchmark_sig)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def register_benchmark(
        db: AsyncSession,
        spectral_provider_sig: str,
        spectral_layer_category: str,
        price_per_unit: Decimal,
        unit_type: str,
        model_name: str | None = None,
        source: str | None = None,
        notes: str | None = None,
    ) -> SpectralProviderBenchmark:
        """Registers a new structural benchmark within the substrate."""
        benchmark = SpectralProviderBenchmark(
            spectral_provider_sig=spectral_provider_sig,
            spectral_layer_category=spectral_layer_category,
            model_name=model_name,
            price_per_unit=price_per_unit,
            unit_type=unit_type,
            source=source,
            notes=notes,
        )
        db.add(benchmark)
        await db.flush()
        await db.refresh(benchmark)
        return benchmark

    @staticmethod
    async def calibrate_benchmark(
        db: AsyncSession,
        benchmark_sig: UUID,
        price_per_unit: Decimal | None = None,
        is_active: bool | None = None,
        effective_until: datetime | None = None,
        source: str | None = None,
        notes: str | None = None,
    ) -> SpectralProviderBenchmark | None:
        """Updates an existing architectural benchmark calibration."""
        benchmark = await SpectralBenchmarkService.get_benchmark(db, benchmark_sig)
        if benchmark is None:
            return None

        if price_per_unit is not None:
            benchmark.price_per_unit = price_per_unit
        if is_active is not None:
            benchmark.is_active = is_active
        if effective_until is not None:
            benchmark.effective_until = effective_until
        if source is not None:
            benchmark.source = source
        if notes is not None:
            benchmark.notes = notes

        await db.flush()
        await db.refresh(benchmark)
        return benchmark
