"""Architectural Domain Harvest — Celery tasks for structural inventory synchronization.

Tasks:
- ``perform_initial_harvest``: Comprehensive synchronization triggered after domain linkage.
- ``perform_periodic_delta``: Incremental logic triggered via temporal scheduling.
- ``perform_manual_harvest``: Manual synchronization request from the administrative matrix.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _execute_async_coro(coro):
    """Executes an asynchronous coroutine within a synchronous task context."""
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


def _initialize_matrix_factory():
    """Initializes a dedicated structural session factory for the worker context."""
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from app.core.config import get_settings

    cfg = get_settings()
    engine = create_async_engine(
        cfg.DATABASE_URL,
        pool_size=5,
        max_overflow=2,
        pool_pre_ping=True,
        pool_recycle=300,
    )
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return engine, factory


async def _execute_comprehensive_harvest(matrix_id: UUID) -> dict[str, int]:
    """Executes a comprehensive artifact harvest for a specific structural matrix."""
    from app.modules.integrations.crm_cache_service import InventoryOrchestrator
    from app.modules.integrations.models import CrmIntegration
    from sqlalchemy import select

    engine, factory = _initialize_matrix_factory()
    try:
        async with factory() as db:
            res = await db.execute(
                select(CrmIntegration).where(
                    CrmIntegration.id == matrix_id,
                    CrmIntegration.status == "connected",
                )
            )
            matrix = res.scalar_one_or_none()
            if not matrix:
                logger.warning("harvest_void_matrix", matrix_id=str(matrix_id))
                return {"contacts": 0, "leads": 0}

            cfg = dict(matrix.config or {})
            cfg["sync_in_progress"] = True
            matrix.config = cfg
            await db.commit()

            try:
                stats = await InventoryOrchestrator.comprehensive_domain_harvest(db, matrix)
            except Exception:
                await db.rollback()
                raise
            finally:
                cfg = dict(matrix.config or {})
                cfg["sync_in_progress"] = False
                matrix.config = cfg
                await db.commit()

            return stats
    finally:
        await engine.dispose()


async def _execute_global_delta_harvest() -> dict[str, object]:
    """Orchestrates delta harvesting across all active architectural domain links."""
    from app.modules.integrations.crm_cache_service import InventoryOrchestrator
    from app.modules.integrations.models import CrmIntegration
    from sqlalchemy import select

    audit: dict[str, object] = {"matrices_processed": 0, "exceptions": 0}

    engine, factory = _initialize_matrix_factory()
    try:
        async with factory() as db:
            res = await db.execute(
                select(CrmIntegration).where(
                    CrmIntegration.status == "connected",
                )
            )
            matrices = list(res.scalars().all())

            for matrix in matrices:
                try:
                    cfg = dict(matrix.config or {})
                    cfg["sync_in_progress"] = True
                    matrix.config = cfg
                    await db.commit()

                    await InventoryOrchestrator.delta_domain_harvest(db, matrix)
                    audit["matrices_processed"] = int(audit["matrices_processed"]) + 1

                except Exception:
                    logger.warning(
                        "delta_harvest_exception",
                        tid=str(matrix.tenant_id),
                        matrix_id=str(matrix.id),
                        exc_info=True,
                    )
                    audit["exceptions"] = int(audit["exceptions"]) + 1
                    await db.rollback()
                finally:
                    cfg = dict(matrix.config or {})
                    cfg["sync_in_progress"] = False
                    matrix.config = cfg
                    await db.commit()
    finally:
        await engine.dispose()

    return audit


@celery_app.task(
    name="app.workers.domain_harvest.perform_initial_harvest",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def perform_initial_harvest(self: object, matrix_id: str) -> dict[str, int]:
    """Comprehensive harvest triggered after structural domain linkage."""
    import time as _t
    from app.core.metrics import WORKER_TASKS_TOTAL, WORKER_TASK_DURATION_SECONDS, CRM_SYNC_TOTAL
    t0 = _t.monotonic()

    logger.info("initial_harvest_initiated", matrix_id=matrix_id)
    try:
        stats = _execute_async_coro(_execute_comprehensive_harvest(UUID(matrix_id)))
        CRM_SYNC_TOTAL.labels(module="comprehensive", status="success").inc()
        WORKER_TASKS_TOTAL.labels(task_name="perform_initial_harvest", status="success").inc()
        WORKER_TASK_DURATION_SECONDS.labels(task_name="perform_initial_harvest").observe(_t.monotonic() - t0)
        return stats
    except Exception as exc:
        logger.error("initial_harvest_failed", matrix_id=matrix_id, exc_info=True)
        CRM_SYNC_TOTAL.labels(module="comprehensive", status="failure").inc()
        WORKER_TASKS_TOTAL.labels(task_name="perform_initial_harvest", status="failure").inc()
        WORKER_TASK_DURATION_SECONDS.labels(task_name="perform_initial_harvest").observe(_t.monotonic() - t0)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.workers.domain_harvest.perform_periodic_delta",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def perform_periodic_delta(self: object) -> dict[str, object]:
    """Periodic delta harvest task matching temporal scheduling protocols."""
    import time as _t
    from app.core.metrics import WORKER_TASKS_TOTAL, WORKER_TASK_DURATION_SECONDS, CRM_SYNC_TOTAL
    t0 = _t.monotonic()

    logger.info("periodic_delta_initiated")
    try:
        audit = _execute_async_coro(_execute_global_delta_harvest())
        CRM_SYNC_TOTAL.labels(module="delta", status="success").inc()
        WORKER_TASKS_TOTAL.labels(task_name="perform_periodic_delta", status="success").inc()
        WORKER_TASK_DURATION_SECONDS.labels(task_name="perform_periodic_delta").observe(_t.monotonic() - t0)
        return audit
    except Exception as exc:
        logger.error("periodic_delta_failed", exc_info=True)
        CRM_SYNC_TOTAL.labels(module="delta", status="failure").inc()
        WORKER_TASKS_TOTAL.labels(task_name="perform_periodic_delta", status="failure").inc()
        WORKER_TASK_DURATION_SECONDS.labels(task_name="perform_periodic_delta").observe(_t.monotonic() - t0)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.workers.domain_harvest.perform_manual_harvest",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def perform_manual_harvest(self: object, matrix_id: str) -> dict[str, int]:
    """Manual harvest triggered from the administrative control matrix."""
    import time as _t
    from app.core.metrics import WORKER_TASKS_TOTAL, WORKER_TASK_DURATION_SECONDS, CRM_SYNC_TOTAL
    t0 = _t.monotonic()

    logger.info("manual_harvest_initiated", matrix_id=matrix_id)
    try:
        stats = _execute_async_coro(_execute_comprehensive_harvest(UUID(matrix_id)))
        CRM_SYNC_TOTAL.labels(module="manual", status="success").inc()
        WORKER_TASKS_TOTAL.labels(task_name="perform_manual_harvest", status="success").inc()
        WORKER_TASK_DURATION_SECONDS.labels(task_name="perform_manual_harvest").observe(_t.monotonic() - t0)
        return stats
    except Exception as exc:
        logger.error("manual_harvest_failed", matrix_id=matrix_id, exc_info=True)
        CRM_SYNC_TOTAL.labels(module="manual", status="failure").inc()
        WORKER_TASKS_TOTAL.labels(task_name="perform_manual_harvest", status="failure").inc()
        WORKER_TASK_DURATION_SECONDS.labels(task_name="perform_manual_harvest").observe(_t.monotonic() - t0)
        raise self.retry(exc=exc)
