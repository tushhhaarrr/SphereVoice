"""Metrics aggregation Celery task.

Runs nightly via Celery Beat — pre-computes daily metric rollups
into the metric_aggregates table for fast dashboard queries.

Imports from: calls module, analytics module.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import func, select

from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


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


async def _aggregate_metrics(target_date: date) -> dict[str, int]:
    """Pre-compute daily metrics per tenant+agent combination.

    For the given date, queries the calls table and upserts
    rollup rows into metric_aggregates with granularity='day'.
    """
    from app.core.database import async_session_factory
    from app.modules.calls.models import Call
    from app.modules.analytics.models import MetricAggregate

    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=UTC)
    day_end = day_start + timedelta(days=1)

    async with async_session_factory() as db:
        # Query calls grouped by tenant_id + agent_id for the target date.
        # peak_concurrent cannot be computed as max(count(...)) — PostgreSQL
        # forbids nested aggregates.  We compute it separately via a subquery
        # that counts overlapping active calls at each call's start time, then
        # join the max of those counts per (tenant, agent) group.
        from sqlalchemy import and_
        from sqlalchemy.orm import aliased

        c2 = aliased(Call, flat=True)

        # Subquery: for each call in the window, count how many other calls
        # from the same tenant+agent were active (started <= this call's start
        # AND ended after, or are still running) at that moment.
        overlap_count = (
            select(
                Call.tenant_id.label("t_id"),
                Call.agent_id.label("a_id"),
                func.count(c2.id).label("concurrent"),
            )
            .join(
                c2,
                and_(
                    c2.tenant_id == Call.tenant_id,
                    c2.agent_id == Call.agent_id,
                    c2.started_at <= Call.started_at,
                    # ended_at NULL means still running
                    (c2.ended_at > Call.started_at) | (c2.ended_at.is_(None)),
                ),
            )
            .where(
                Call.started_at >= day_start,
                Call.started_at < day_end,
            )
            .group_by(Call.tenant_id, Call.agent_id, Call.id)
            .subquery()
        )

        peak_subq = (
            select(
                overlap_count.c.t_id,
                overlap_count.c.a_id,
                func.max(overlap_count.c.concurrent).label("peak_concurrent"),
            )
            .group_by(overlap_count.c.t_id, overlap_count.c.a_id)
            .subquery()
        )

        result = await db.execute(
            select(
                Call.tenant_id,
                Call.agent_id,
                func.count(Call.id).label("total_calls"),
                func.count(Call.id).filter(Call.status == "completed").label("completed_calls"),
                func.count(Call.id).filter(Call.status == "failed").label("failed_calls"),
                func.avg(Call.duration_seconds).label("avg_duration"),
                func.sum(Call.duration_seconds).label("total_duration"),
                func.avg(Call.avg_latency_ms).label("avg_latency_p50"),
                func.avg(Call.avg_latency_ms).label("avg_latency_p99"),
                func.coalesce(peak_subq.c.peak_concurrent, 0).label("peak_concurrent"),
            )
            .outerjoin(
                peak_subq,
                and_(
                    peak_subq.c.t_id == Call.tenant_id,
                    peak_subq.c.a_id == Call.agent_id,
                ),
            )
            .where(
                Call.started_at >= day_start,
                Call.started_at < day_end,
            )
            .group_by(Call.tenant_id, Call.agent_id, peak_subq.c.peak_concurrent)
        )

        rows = result.all()
        upserted = 0

        for row in rows:
            total = row.total_calls or 0
            completed = row.completed_calls or 0
            failed = row.failed_calls or 0
            success_rate = (completed / total) if total > 0 else 0.0

            # Check if aggregate already exists (idempotent)
            existing = await db.execute(
                select(MetricAggregate).where(
                    MetricAggregate.tenant_id == row.tenant_id,
                    MetricAggregate.agent_id == row.agent_id,
                    MetricAggregate.period_date == target_date,
                    MetricAggregate.granularity == "day",
                )
            )
            agg = existing.scalar_one_or_none()

            if agg:
                agg.total_calls = total
                agg.completed_calls = completed
                agg.failed_calls = failed
                agg.avg_duration_seconds = float(row.avg_duration or 0)
                agg.total_duration_seconds = float(row.total_duration or 0)
                agg.p50_latency_ms = float(row.avg_latency_p50 or 0)
                agg.p99_latency_ms = float(row.avg_latency_p99 or 0)
                agg.success_rate = success_rate
                agg.peak_concurrency = row.peak_concurrent or 0
            else:
                agg = MetricAggregate(
                    tenant_id=row.tenant_id,
                    agent_id=row.agent_id,
                    period_date=target_date,
                    granularity="day",
                    total_calls=total,
                    completed_calls=completed,
                    failed_calls=failed,
                    avg_duration_seconds=float(row.avg_duration or 0),
                    total_duration_seconds=float(row.total_duration or 0),
                    p50_latency_ms=float(row.avg_latency_p50 or 0),
                    p99_latency_ms=float(row.avg_latency_p99 or 0),
                    success_rate=success_rate,
                    peak_concurrency=row.peak_concurrent or 0,
                )
                db.add(agg)

            upserted += 1

        await db.commit()

        logger.info(
            "metrics_aggregation_complete",
            target_date=target_date.isoformat(),
            rows_upserted=upserted,
        )

        return {"date": target_date.isoformat(), "rows_upserted": upserted}


@celery_app.task(
    name="app.workers.metrics_aggregation.aggregate_daily_metrics",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def aggregate_daily_metrics(self, target_date_iso: str | None = None) -> dict[str, object]:
    """Pre-compute daily metric rollups.

    Runs nightly via Celery Beat. Aggregates yesterday's call data
    into metric_aggregates table for fast dashboard queries.

    Args:
        target_date_iso: ISO date string (YYYY-MM-DD). Defaults to yesterday.
    """
    if target_date_iso:
        target = date.fromisoformat(target_date_iso)
    else:
        target = (datetime.now(UTC) - timedelta(days=1)).date()

    logger.info("metrics_aggregation_started", target_date=target.isoformat())

    try:
        result = _run_async(_aggregate_metrics(target))
        logger.info("metrics_aggregation_finished", **result)
        return result
    except Exception as exc:
        logger.error("metrics_aggregation_failed", error=str(exc), target_date=target.isoformat())
        raise self.retry(exc=exc)
