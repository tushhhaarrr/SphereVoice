"""Celery task — periodic USD→INR exchange rate refresh.

Runs every 6 hours via Celery Beat.
Fetches the live rate from a free API, stores in DB, caches in Redis.
"""

from __future__ import annotations

import asyncio

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _run_async(coro):  # noqa: ANN001
    """Run an async coroutine in a new event loop (Celery tasks are sync)."""
    from app.core.database import async_engine

    loop = asyncio.new_event_loop()
    try:
        try:
            loop.run_until_complete(async_engine.dispose())
        except RuntimeError:
            pass
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _refresh_rate() -> dict[str, str]:
    from app.core.database import async_session_factory
    from app.modules.pricing.exchange_rate import ExchangeRateService

    async with async_session_factory() as db:
        rate = await ExchangeRateService.fetch_and_store(db)
        await db.commit()

    return {"rate": str(rate), "status": "ok"}


@celery_app.task(
    name="app.workers.exchange_rate.refresh_usd_inr_rate",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # retry after 5 min if API fails
)
def refresh_usd_inr_rate(self) -> dict[str, str]:  # noqa: ANN001
    """Fetch live USD→INR rate and store in DB + Redis cache."""
    try:
        result = _run_async(_refresh_rate())
        logger.info("exchange_rate_refresh_success", **result)
        return result
    except Exception as exc:
        logger.error("exchange_rate_refresh_failed", error=str(exc))
        raise self.retry(exc=exc)
