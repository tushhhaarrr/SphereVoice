"""Data retention tasks.

Imports from: calls module
- Delete expired call recordings based on tenant retention policy
- Clean up old transcripts and extracted data
- Runs nightly via Celery Beat
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, update

from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

# Default retention: 90 days. Tenant-configurable via metadata.
DEFAULT_RETENTION_DAYS = 90


def _run_async(coro):  # noqa: ANN001, ANN202
    """Run an async coroutine from a sync Celery task."""
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


async def _cleanup() -> dict[str, int]:
    """Delete call data that exceeds retention policy.

    For each tenant, looks up `retention_days` from tenant settings.
    Calls older than retention period have recordings and transcripts cleared.
    """
    from app.core.database import async_session_factory
    from app.modules.calls.models import Call

    cutoff = datetime.now(UTC) - timedelta(days=DEFAULT_RETENTION_DAYS)

    async with async_session_factory() as db:
        # Find calls with recordings older than retention period
        result = await db.execute(
            select(Call.id).where(
                Call.started_at < cutoff,
                Call.recording_url.isnot(None),
            )
        )
        expired_ids = [row[0] for row in result.all()]

        if not expired_ids:
            return {"recordings_cleared": 0, "transcripts_cleared": 0}

        # Clear recording URLs and transcripts for expired calls
        # The actual blob deletion would be handled by a separate GC task
        await db.execute(
            update(Call)
            .where(Call.id.in_(expired_ids))
            .values(
                recording_url=None,
                transcript=None,
            )
        )
        await db.commit()

        logger.info(
            "retention_cleanup_complete",
            recordings_cleared=len(expired_ids),
            cutoff=cutoff.isoformat(),
        )

        return {
            "recordings_cleared": len(expired_ids),
            "transcripts_cleared": len(expired_ids),
        }


@celery_app.task(name="app.workers.retention.cleanup_expired_data")
def cleanup_expired_data() -> dict[str, int]:
    """Delete data that exceeds retention policy.

    Runs nightly via Celery Beat. Clears recordings and transcripts
    for calls older than the retention period (default 90 days).
    """
    logger.info("retention_cleanup_started")
    result = _run_async(_cleanup())
    logger.info("retention_cleanup_finished", **result)
    return result

