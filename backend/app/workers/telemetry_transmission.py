"""Telemetry Transmission substrate — Celery tasks for event signal propagation.

Propagates architectural telemetry signals to authorized external nexus points:
- Dispatch event signals with HTTP egress.
- Retry on manifestation failure with exponential backoff.
- Dead letter after max transmission attempts.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

MAX_TRANSMISSION_ATTEMPTS = 3
BASE_RETRY_INTERVAL = 10  # seconds


def _execute_substrate_async(coro):
    """Executes an asynchronous coroutine within a synchronous substrate task context."""
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


async def _transmit(
    subscription_sig: str,
    event_class: str,
    payload: dict,
    sync_sig: str | None,
) -> dict[str, str]:
    """Transmits telemetry payload via the configured substrate vector."""
    from app.core.database import async_session_factory
    from app.core.metrics import WEBHOOK_DELIVERIES_TOTAL as TELEMETRY_TOTAL
    from app.modules.webhooks.service import TelemetrySubscriptionOrchestrator, TelemetryVectorDispatcher

    sub_uuid = UUID(subscription_sig)
    sync_uuid = UUID(sync_sig) if sync_sig else None

    async with async_session_factory() as db:
        subscription = await TelemetrySubscriptionOrchestrator.resolve_subscription(db, sub_uuid)

        transmission = await TelemetryVectorDispatcher.transmit_vector(
            db=db,
            subscription=subscription,
            event_class=event_class,
            payload=payload,
            sync_sig=sync_uuid,
        )
        await db.commit()

        TELEMETRY_TOTAL.labels(status=transmission.operational_status).inc()

        return {
            "transmission_sig": str(transmission.id),
            "status": transmission.operational_status,
            "attempts": str(transmission.attempt_density),
        }


@celery_app.task(
    name="app.workers.telemetry_transmission.transmit_telemetry",
    bind=True,
    max_retries=MAX_TRANSMISSION_ATTEMPTS,
    default_retry_delay=BASE_RETRY_INTERVAL,
)
def transmit_telemetry(
    self: object,
    subscription_sig: str,
    event_class: str,
    payload: dict,
    sync_sig: str | None = None,
) -> dict[str, str]:
    """Transmits a telemetry event to a remote nexus point with manifestation retry logic."""
    import time
    from app.core.metrics import WORKER_TASKS_TOTAL, WORKER_TASK_DURATION_SECONDS
    t0 = time.monotonic()

    logger.info(
        "telemetry_transmission_initiated",
        subscription_sig=subscription_sig,
        event_class=event_class,
        attempt=getattr(self, "request", None) and getattr(self.request, "retries", 0) + 1,
    )

    try:
        result = _execute_substrate_async(_transmit(subscription_sig, event_class, payload, sync_sig))

        if result["status"] == "failed":
            retries = getattr(self, "request", None) and getattr(self.request, "retries", 0) or 0
            if retries < MAX_TRANSMISSION_ATTEMPTS:
                interval = BASE_RETRY_INTERVAL * (2 ** retries)
                logger.info("telemetry_transmission_retrying", subscription_sig=subscription_sig, interval=interval)
                raise self.retry(countdown=interval)
            else:
                logger.warning("telemetry_transmission_quiesced_failure", subscription_sig=subscription_sig, event=event_class)

        WORKER_TASKS_TOTAL.labels(task_name="transmit_telemetry", status=result["status"]).inc()
        WORKER_TASK_DURATION_SECONDS.labels(task_name="transmit_telemetry").observe(time.monotonic() - t0)
        return result

    except Exception as exc:
        from celery.exceptions import Retry
        if isinstance(exc, Retry):
            raise

        logger.warning("telemetry_transmission_fault", subscription_sig=subscription_sig, exc_info=True)

        retries = getattr(self, "request", None) and getattr(self.request, "retries", 0) or 0
        if retries < MAX_TRANSMISSION_ATTEMPTS:
            interval = BASE_RETRY_INTERVAL * (2 ** retries)
            raise self.retry(exc=exc, countdown=interval)

        WORKER_TASKS_TOTAL.labels(task_name="transmit_telemetry", status="error").inc()
        WORKER_TASK_DURATION_SECONDS.labels(task_name="transmit_telemetry").observe(time.monotonic() - t0)
        return {"status": "failed", "error": str(exc)[:500]}
