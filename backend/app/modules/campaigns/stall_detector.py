"""Campaign stall detector — periodic Celery task.

Detects campaigns stuck in 'running' status with no progress for
longer than CAMPAIGN_STALL_TIMEOUT_MINUTES.  Emits a warning-level
structured log so external alerting (Grafana / Azure Monitor) can fire
notifications.

Registered as a Celery beat task running every 5 minutes.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import structlog
import structlog.contextvars
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.campaigns.models import Campaign
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _run_async(coro):  # noqa: ANN001, ANN202
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.modules.campaigns.stall_detector.detect_stalled_campaigns")
def detect_stalled_campaigns() -> None:
    """Check for campaigns that appear stalled and emit alerts."""
    _run_async(_detect_stalled_campaigns_async())


async def _detect_stalled_campaigns_async() -> None:
    """Query for running campaigns with no recent updated_at and log alerts."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    settings = get_settings()
    stall_threshold = datetime.now(UTC) - timedelta(
        minutes=settings.CAMPAIGN_STALL_TIMEOUT_MINUTES,
    )

    # Create a fresh engine for this task invocation to avoid
    # "Future attached to a different loop" with asyncpg in Celery fork pool.
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=2,
        max_overflow=2,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as session:
            query = select(Campaign).where(
                Campaign.status == "running",
                Campaign.updated_at < stall_threshold,
            )
            result = await session.execute(query)
            stalled = result.scalars().all()
    finally:
        await engine.dispose()

    if not stalled:
        logger.debug("stall_detector.no_stalled_campaigns")
        return

    for campaign in stalled:
        structlog.contextvars.bind_contextvars(
            campaign_id=str(campaign.id),
            tenant_id=str(campaign.tenant_id),
        )
        try:
            minutes_stalled = int((datetime.now(UTC) - campaign.updated_at).total_seconds() / 60)
            logger.warning(
                "stall_detector.campaign_stalled",
                campaign_name=campaign.name,
                minutes_stalled=minutes_stalled,
                last_updated=campaign.updated_at.isoformat(),
                completed_calls=campaign.completed_calls,
                total_contacts=campaign.total_contacts,
            )
        finally:
            structlog.contextvars.unbind_contextvars("campaign_id", "tenant_id")

    logger.info(
        "stall_detector.check_complete",
        stalled_count=len(stalled),
    )
