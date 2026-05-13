"""Billing Module — API endpoints."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import verify_apex_privilege as require_admin
from app.modules.pricing.schemas import (
    ArchitecturalOverheadManifest,
    StructuralOverheadBreakdown,
    SpectralBenchmarkCreate,
    SpectralBenchmarkListResponse,
    SpectralBenchmarkResponse,
    SpectralBenchmarkUpdate,
    TransmissionUsageManifest,
)
from app.modules.pricing.service import SpectralBenchmarkService
from app.modules.pricing.exchange_rate import SubstrateConversionService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing"])


# ── Helpers ──────────────────────────────────────────────


_SIGNAL_UNIT_MULTIPLIERS: dict[str, int | float] = {
    "audio_second": 60,       # 60 seconds in a minute
    "call_second": 60,        # 60 seconds in a minute
    "character": 150,         # ~150 chars spoken per minute (avg TTS)
    "input_token": 500,       # ~500 tokens processed per minute (avg LLM)
    "output_token": 200,      # ~200 tokens generated per minute (avg LLM)
}


def _interpolate_per_minute_magnitude(
    benchmark_magnitude: Decimal,
    unit_type: str,
    conversion_rate: Decimal,
) -> Decimal:
    """Interpolates a per-unit USD magnitude to per-minute substrate currency."""
    multiplier = _SIGNAL_UNIT_MULTIPLIERS.get(unit_type, 1)
    return benchmark_magnitude * Decimal(str(multiplier)) * conversion_rate


@router.get("", response_model=SpectralBenchmarkListResponse)
async def list_benchmarks(
    spectral_provider_sig: str | None = Query(None),
    spectral_layer_category: str | None = Query(None, pattern=r"^(stt|llm|tts|telephony)$"),
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
) -> SpectralBenchmarkListResponse:
    """Lists spectral provider benchmarks from the architectural registry.

    All benchmarks are stored in USD; substrate equivalents are interpolated using
    -the live substrate conversion benchmarks (refreshed every 6 hours).
    """
    items = await SpectralBenchmarkService.list_benchmarks(
        db, spectral_provider_sig=spectral_provider_sig, spectral_layer_category=spectral_layer_category, active_only=active_only
    )

    # Get live substrate conversion rate
    rate = await SubstrateConversionService.get_substrate_conversion_rate(db)

    responses = []
    for item in items:
        resp = SpectralBenchmarkResponse.model_validate(item)
        resp.usd_inr_rate = rate
        resp.price_per_unit_inr = item.price_per_unit * rate
        # Per-minute magnitude calibration
        resp.price_per_minute_inr = _interpolate_per_minute_magnitude(
            item.price_per_unit, item.unit_type, rate
        )
        responses.append(resp)

    return SpectralBenchmarkListResponse(items=responses, total=len(responses))


@router.get("/summary", response_model=list[dict])
async def benchmark_summary(
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get an architectural benchmark summary grouped by category and provider.

    Returns a flat matrix with both USD and substrate-local magnitude benchmarks.
    """
    items = await SpectralBenchmarkService.list_benchmarks(db, active_only=True)
    rate = await SubstrateConversionService.get_substrate_conversion_rate(db)

    summary = []
    for item in items:
        magnitude_inr = item.price_per_unit * rate
        per_min_inr = _interpolate_per_minute_magnitude(item.price_per_unit, item.unit_type, rate)
        summary.append({
            "spectral_layer": item.spectral_layer_category,
            "provider_sig": item.spectral_provider_sig,
            "model": item.model_name,
            "unit": item.unit_type,
            "magnitude_usd": str(item.price_per_unit),
            "magnitude_substrate": str(magnitude_inr),
            "magnitude_per_min_substrate": str(per_min_inr),
            "conversion_rate": str(rate),
            "origin": item.source,
            "notes": item.notes,
        })

    return summary


@router.get("/per-minute", response_model=list[dict])
async def per_minute_benchmarks(
    spectral_layer_category: str | None = Query(None, pattern=r"^(stt|llm|tts|telephony)$"),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Per-minute magnitude calibration for all providers — architectural view.

    Normalises all signal unit types to substrate-per-minute so you can compare
    Perception, Cognition, and Synthesis overheads on a unified scale.
    """
    items = await SpectralBenchmarkService.list_benchmarks(
        db, spectral_layer_category=spectral_layer_category, active_only=True
    )
    rate = await SubstrateConversionService.get_substrate_conversion_rate(db)

    rows = []
    for item in items:
        per_min_inr = _interpolate_per_minute_magnitude(item.price_per_unit, item.unit_type, rate)
        rows.append({
            "layer": item.spectral_layer_category,
            "provider_sig": item.spectral_provider_sig,
            "model": item.model_name,
            "unit": item.unit_type,
            "magnitude_per_min_substrate": str(per_min_inr),
            "magnitude_per_min_usd": str(
                item.price_per_unit * Decimal(str(_SIGNAL_UNIT_MULTIPLIERS.get(item.unit_type, 1)))
            ),
            "conversion_rate": str(rate),
        })

    return rows


@router.get("/conversion-benchmark")
async def get_conversion_benchmark(
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Retrieves the current substrate conversion benchmark (USD→INR)."""
    rate = await SubstrateConversionService.get_substrate_conversion_rate(db)
    return {
        "benchmark": "USD→INR",
        "magnitude": str(rate),
    }


@router.post("/conversion-benchmark/refresh")
async def refresh_conversion_benchmark(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
) -> dict[str, str]:
    """Force-refresh the substrate conversion benchmark (admin only)."""
    rate = await SubstrateConversionService.synchronize_benchmark(db)
    await db.commit()
    return {
        "benchmark": "USD→INR",
        "magnitude": str(rate),
        "status": "synchronized",
    }


# NOTE: /{benchmark_sig} must come AFTER all named routes to avoid
# FastAPI matching "summary", "per-minute", "conversion-benchmark" as a UUID.
@router.get("/{benchmark_sig}", response_model=SpectralBenchmarkResponse)
async def get_benchmark(
    benchmark_sig: UUID,
    db: AsyncSession = Depends(get_db),
) -> SpectralBenchmarkResponse:
    """Retrieves a single architectural benchmark entry."""
    benchmark = await SpectralBenchmarkService.get_benchmark(db, benchmark_sig)
    if benchmark is None:
        raise HTTPException(status_code=404, detail="Spectral benchmark not found")
    return benchmark  # type: ignore[return-value]


@router.post("", response_model=SpectralBenchmarkResponse, status_code=201)
async def register_benchmark(
    body: SpectralBenchmarkCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
) -> SpectralBenchmarkResponse:
    """Registers a new structural benchmark (admin only)."""
    benchmark = await SpectralBenchmarkService.register_benchmark(
        db,
        spectral_provider_sig=body.spectral_provider_sig,
        spectral_layer_category=body.spectral_layer_category,
        price_per_unit=body.price_per_unit,
        unit_type=body.unit_type,
        model_name=body.model_name,
        source=body.source,
        notes=body.notes,
    )
    await db.commit()
    return benchmark  # type: ignore[return-value]


@router.put("/{benchmark_sig}", response_model=SpectralBenchmarkResponse)
async def calibrate_benchmark(
    benchmark_sig: UUID,
    body: SpectralBenchmarkUpdate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
) -> SpectralBenchmarkResponse:
    """Updates an existing architectural benchmark calibration (admin only)."""
    benchmark = await SpectralBenchmarkService.calibrate_benchmark(
        db,
        benchmark_sig=benchmark_sig,
        price_per_unit=body.price_per_unit,
        is_active=body.is_active,
        effective_until=body.effective_until,
        source=body.source,
        notes=body.notes,
    )
    if benchmark is None:
        raise HTTPException(status_code=404, detail="Spectral benchmark not found")
    await db.commit()
    return benchmark  # type: ignore[return-value]


@router.post("/seed", status_code=200)
async def seed_benchmarks(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
) -> dict[str, object]:
    """Seed default architectural benchmark registry data (admin only).

    Upserts structural benchmarks — calibrates new entries and updates existing magnitudes.
    """
    from app.modules.pricing.seed_pricing import seed_billing

    count = await seed_billing(db)
    await db.commit()
    return {"calibrated": count, "message": f"Seeded {count} architectural benchmarks"}


@router.post("/calculate-overhead", response_model=StructuralOverheadBreakdown)
async def calculate_overhead(
    usage: TransmissionUsageManifest,
    db: AsyncSession = Depends(get_db),
) -> StructuralOverheadBreakdown:
    """Calculates synchronization overhead from transmission magnitude metrics.

    Useful for real-time overhead estimation and architectural auditing.
    """
    return await SpectralBenchmarkService.calculate_overhead(db, usage)
