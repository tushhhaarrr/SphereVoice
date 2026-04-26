"""Spectral Manifold Substrate — Substrate Conversion Registry.

Provides real-time interpolation of the architectural conversion rate 
between the global settlement currency (USD) and the target substrate 
execution currency (INR). 

Flow:
  Architectural Pulse (Celery) → Synchronize live benchmarks → Registry Persistence → Redis Cache
  Inference Cycle → Redis Lookup (Low Latency) → Registry Fallback → System Default
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import structlog
from sqlalchemy import DateTime, Index, Numeric, String, desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base
from app.modules.pricing.models import SpectralProviderBenchmark

runtime_logger = structlog.get_logger(__name__)

# ── Architectural Conversion Defaults ────────────────────────
_SUBSTRATE_FALLBACK_RATE = Decimal("94.00")
SUBSTRATE_RATE_CACHE_KEY = "substrate_conversion:usd_inr"
SUBSTRATE_RATE_CACHE_TTL = 7 * 3600


class SubstrateConversionRate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Historical snapshots of substrate conversion benchmarks."""

    __tablename__ = "substrate_conversion_registry"

    origin_currency: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'USD'")
    )
    target_currency: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'INR'")
    )
    rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False
    )
    benchmark_source: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    synchronized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        Index("idx_substrate_conversion_pair", "origin_currency", "target_currency"),
        Index("idx_substrate_conversion_sync", "synchronized_at"),
    )


class SubstrateConversionService:
    """Orchestrates architectural currency conversion across the substrate."""

    @staticmethod
    async def get_substrate_conversion_rate(db: AsyncSession) -> Decimal:
        """Retrieves the active substrate conversion rate for overhead calculation.

        Resolution priority:
        1. Substrate cache (Redis)
        2. Registry persistence (PostgreSQL)
        3. Registry-based system benchmarks
        4. Static substrate fallback
        """
        # 1. Substrate Cache Lookup
        rate = await SubstrateConversionService._get_from_cache()
        if rate is not None:
            return rate

        # 2. Registry Persistence Lookup
        rate = await SubstrateConversionService._get_from_registry(db)
        if rate is not None:
            await SubstrateConversionService._update_cache(rate)
            return rate

        # 3. System Benchmark Fallback
        try:
            result = await db.execute(
                select(SpectralProviderBenchmark.price_per_unit).where(
                    SpectralProviderBenchmark.spectral_provider_sig == "system_benchmarks",
                    SpectralProviderBenchmark.unit_type == "usd_inr_rate",
                    SpectralProviderBenchmark.is_active.is_(True),
                )
            )
            price = result.scalar_one_or_none()
            if price:
                return price
        except Exception:
            pass

        # 4. System Static Fallback
        runtime_logger.warning("substrate_conversion_fallback", rate=str(_SUBSTRATE_FALLBACK_RATE))
        return _SUBSTRATE_FALLBACK_RATE

    @staticmethod
    async def synchronize_benchmark(db: AsyncSession) -> Decimal:
        """Synchronizes the live substrate conversion benchmark from external nexus points."""
        import httpx

        rate: Decimal | None = None
        nexus_source = ""

        # Primary Benchmark Nexus
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get("https://open.er-api.com/v6/latest/USD")
                resp.raise_for_status()
                data = resp.json()
                if data.get("result") == "success" and "INR" in data.get("rates", {}):
                    rate = Decimal(str(data["rates"]["INR"]))
                    nexus_source = "open.er-api.com"
        except Exception:
            runtime_logger.warning("primary_benchmark_nexus_fault")

        # Auxiliary Benchmark Nexus
        if rate is None:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(
                        "https://api.frankfurter.app/latest",
                        params={"from": "USD", "to": "INR"},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    if "INR" in data.get("rates", {}):
                        rate = Decimal(str(data["rates"]["INR"]))
                        nexus_source = "frankfurter.app"
            except Exception:
                runtime_logger.warning("auxiliary_benchmark_nexus_fault")

        if rate is None:
            runtime_logger.error("all_benchmark_nexus_points_exhausted")
            return _SUBSTRATE_FALLBACK_RATE

        # Persist to Registry
        sync_ts = datetime.now(timezone.utc)
        record = SubstrateConversionRate(
            origin_currency="USD",
            target_currency="INR",
            rate=rate,
            benchmark_source=nexus_source,
            synchronized_at=sync_ts,
        )
        db.add(record)
        await db.flush()

        # Update Cache
        await SubstrateConversionService._update_cache(rate)

        runtime_logger.info("substrate_conversion_synchronized", rate=str(rate), source=nexus_source)
        return rate

    @staticmethod
    async def _get_from_cache() -> Optional[Decimal]:
        """Internal: Retrieve benchmark from Redis substrate cache."""
        try:
            import redis.asyncio as aioredis
            from app.core.config import get_settings
            client = aioredis.from_url(get_settings().REDIS_URL, decode_responses=True)
            try:
                val = await client.get(SUBSTRATE_RATE_CACHE_KEY)
                if val: return Decimal(val)
            finally: await client.aclose()
        except Exception: pass
        return None

    @staticmethod
    async def _update_cache(rate: Decimal) -> None:
        """Internal: Update Redis substrate cache with live benchmark."""
        try:
            import redis.asyncio as aioredis
            from app.core.config import get_settings
            client = aioredis.from_url(get_settings().REDIS_URL, decode_responses=True)
            try:
                await client.set(SUBSTRATE_RATE_CACHE_KEY, str(rate), ex=SUBSTRATE_RATE_CACHE_TTL)
            finally: await client.aclose()
        except Exception: pass

    @staticmethod
    async def _get_from_registry(db: AsyncSession) -> Optional[Decimal]:
        """Internal: Retrieve latest benchmark from substrate conversion registry."""
        result = await db.execute(
            select(SubstrateConversionRate.rate)
            .where(
                SubstrateConversionRate.origin_currency == "USD",
                SubstrateConversionRate.target_currency == "INR",
            )
            .order_by(desc(SubstrateConversionRate.synchronized_at))
            .limit(1)
        )
        return result.scalar_one_or_none()
