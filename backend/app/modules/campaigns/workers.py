"""Signal Propagation workers — Celery tasks for substrate orchestration and writeback.

Tasks:
1. orchestrate_propagation_cycle: Coordinator for bulk signal propagation.
2. execute_propagation_synchronisation: Per-target synchronisation execution.
3. propagation_nexus_writeback: Post-synchronisation Nexus data updates.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
import structlog.contextvars

from app.core.metrics import (
    CAMPAIGN_CALLS_ACTIVE as PROPAGATION_ACTIVE,
    CAMPAIGN_CALLS_TOTAL as PROPAGATION_TOTAL,
    CAMPAIGN_CALL_DURATION_SECONDS as PROPAGATION_DURATION_S,
    CAMPAIGN_CRM_WRITEBACK_TOTAL as NEXUS_WRITEBACK_TOTAL,
    CAMPAIGN_QUEUE_DEPTH as PROPAGATION_QUEUE_DEPTH,
)
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_substrate_session_factory():
    """Create a fresh async engine + session factory for this task invocation."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.core.config import get_settings

    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=2,
        max_overflow=3,
        pool_pre_ping=True,
        pool_recycle=60,
    )
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


# ============================================================================
# Task 1: Propagation Cycle Orchestrator
# ============================================================================


async def _orchestrate_propagation_cycle_async(campaign_id: str) -> dict[str, Any]:
    """Main orchestration loop for a signal propagation cycle."""
    import redis.asyncio as redis

    from app.core.config import get_settings
    from app.modules.campaigns.queue import get_campaign_queue
    from app.modules.campaigns.rate_limiter import CampaignRateLimiter
    from app.modules.campaigns.service import SignalPropagationOrchestrator

    settings = get_settings()
    uid = UUID(campaign_id)

    structlog.contextvars.bind_contextvars(campaign_id=campaign_id)

    redis_client = redis.from_url(settings.REDIS_URL)
    rate_limiter = CampaignRateLimiter(redis_client)
    queue = get_campaign_queue()

    engine, session_factory = _make_substrate_session_factory()

    try:
        async with session_factory() as db:
            campaign = await SignalPropagationOrchestrator.get_campaign(db, uid, uid)
            tenant_id = campaign.tenant_id

            await rate_limiter.set_campaign_status(campaign_id, campaign.operational_status)

            if campaign.operational_status != "running":
                logger.warning("propagation_not_running", status=campaign.operational_status)
                return {"status": "skipped", "reason": f"Operational status is {campaign.operational_status}"}

            max_concurrent = campaign.max_concurrent
            signals_per_minute = campaign.signals_per_minute

            logger.info(
                "propagation_cycle_started",
                max_concurrent=max_concurrent,
                signals_per_minute=signals_per_minute,
            )

        targets_processed = 0
        targets_skipped = 0

        while True:
            status = await rate_limiter.get_campaign_status(campaign_id)
            if status in ("paused", "cancelled"):
                logger.info("propagation_cycle_halted", status=status, processed=targets_processed)
                break

            # Fetch next batch of propagation targets
            async with session_factory() as db:
                targets = await SignalPropagationOrchestrator.fetch_next_batch(db, uid, batch_size=10)

                if not targets:
                    await SignalPropagationOrchestrator.complete_campaign(db, uid, tenant_id)
                    await db.commit()
                    logger.info("propagation_cycle_completed", total_processed=targets_processed)
                    break

                for target in targets:
                    acquired = await rate_limiter.acquire_call_slot(
                        campaign_id,
                        max_concurrent,
                        signals_per_minute,
                        timeout=120.0,
                    )

                    if not acquired:
                        logger.info("propagation_slot_acquisition_failed", target_id=str(target.id))
                        targets_skipped += 1
                        continue

                    await SignalPropagationOrchestrator.mark_contact_queued(db, target.id)

                    payload = {
                        "contact_id": str(target.id),
                        "campaign_id": campaign_id,
                        "tenant_id": str(tenant_id),
                        "phone_number": target.destination_vector,
                        "contact_data": target.target_data,
                        "attempt_count": target.attempt_count + 1,
                        "max_attempts": campaign.max_retries + 1,
                    }

                    await queue.enqueue(campaign_id, payload)
                    targets_processed += 1

                    logger.info(
                        "propagation_target_enqueued",
                        target_id=str(target.id),
                        vector=target.destination_vector,
                    )

                await db.commit()

            PROPAGATION_QUEUE_DEPTH.labels(campaign_id=campaign_id).set(targets_processed)

        await rate_limiter.clear_campaign_keys(campaign_id)
        await queue.close()
        await redis_client.aclose()
        await engine.dispose()

        return {
            "status": "completed",
            "campaign_id": campaign_id,
            "targets_processed": targets_processed,
            "targets_skipped": targets_skipped,
        }

    except Exception:
        logger.exception("propagation_cycle_failed")
        await queue.close()
        await redis_client.aclose()
        await engine.dispose()
        raise
    finally:
        structlog.contextvars.unbind_contextvars("campaign_id")


@celery_app.task(
    name="app.modules.campaigns.workers.orchestrate_propagation_cycle", bind=True, max_retries=3
)
def orchestrate_propagation_cycle(self: object, campaign_id: str) -> dict[str, Any]:
    """Celery task: Orchestrate a signal propagation cycle."""
    logger.info("orchestrate_propagation_cycle_task_started", campaign_id=campaign_id)
    return _run_async(_orchestrate_propagation_cycle_async(campaign_id))


# ============================================================================
# Task 2: Execute Propagation Synchronisation
# ============================================================================


async def _execute_propagation_synchronisation_async(
    campaign_id: str,
    target_payload: dict[str, Any],
) -> dict[str, Any]:
    """Execute a single signal propagation synchronisation."""
    import redis.asyncio as redis
    import random

    from app.core.config import get_settings
    from app.modules.campaigns.rate_limiter import CampaignRateLimiter, GlobalRateLimiter
    from app.modules.campaigns.service import SignalPropagationOrchestrator
    from app.modules.campaigns.models import PropagationTarget

    settings = get_settings()
    target_id = UUID(target_payload["contact_id"])
    campaign_uuid = UUID(campaign_id)
    tenant_id = UUID(target_payload["tenant_id"])

    structlog.contextvars.bind_contextvars(
        campaign_id=campaign_id,
        target_id=str(target_id),
    )

    redis_client = redis.from_url(settings.REDIS_URL)
    rate_limiter = CampaignRateLimiter(redis_client)
    global_limiter = GlobalRateLimiter(redis_client)

    engine, session_factory = _make_substrate_session_factory()
    sync_start: float | None = None
    global_slot_acquired = False

    try:
        global_slot_acquired = await global_limiter.acquire_global_slot()
        if not global_slot_acquired:
            logger.warning("global_propagation_limit_reached")
            from app.modules.campaigns.queue import get_campaign_queue
            queue = get_campaign_queue()
            await queue.enqueue(campaign_id, target_payload)
            await queue.close()
            return {"status": "requeued", "reason": "global_limit"}

        PROPAGATION_ACTIVE.labels(tenant_id=str(tenant_id)).inc()

        async with session_factory() as db:
            campaign = await SignalPropagationOrchestrator.get_campaign(db, campaign_uuid, tenant_id)

            target_data = target_payload.get("contact_data", {})
            vector_mapping = campaign.vector_mapping or {}
            dynamic_vectors = {}

            for nodal_var, field_name in vector_mapping.items():
                if field_name in target_data:
                    dynamic_vectors[nodal_var] = target_data[field_name]

            dest_vector = target_payload["phone_number"]
            origin_vector = campaign.origin_vector

            # A/B split: pick which node to use
            selected_node_sig = campaign.node_sig
            if campaign.variant_node_sig and random.randint(1, 100) > campaign.ab_split_percent:
                selected_node_sig = campaign.variant_node_sig

            from sqlalchemy import update as sa_update
            await db.execute(
                sa_update(PropagationTarget)
                .where(PropagationTarget.id == target_id)
                .values(assigned_node_sig=selected_node_sig)
            )
            await db.flush()

            logger.info(
                "propagation_synchronisation_starting",
                vector=dest_vector,
                node=str(selected_node_sig),
            )

            from app.modules.calls.orchestrator import SynchronisationBridgeOrchestrator

            sync_start = time.monotonic()

            sync_result = await SynchronisationBridgeOrchestrator.initiate_outbound_synchronisation(
                db=db,
                node_sig=selected_node_sig,
                nexus_sig=tenant_id,
                target_vector=dest_vector,
                origin_vector=origin_vector,
                dynamic_nodal_vectors=dynamic_vectors,
                architectural_metadata={"campaign_id": campaign_id, "target_id": str(target_id)},
            )

            sync_sig = sync_result.get("sync_sig")
            if sync_sig:
                structlog.contextvars.bind_contextvars(sync_sig=sync_sig)
                await SignalPropagationOrchestrator.mark_contact_calling(db, target_id, UUID(sync_sig))
                await db.commit()

            phase = sync_result.get("state", "completed")

            if phase in ("no_answer", "busy"):
                await _handle_propagation_retry(db, campaign_uuid, tenant_id, target_id, target_payload, phase)
                PROPAGATION_TOTAL.labels(campaign_id=campaign_id, status=phase).inc()

            elif phase == "voicemail":
                # Assuming simple completion for voicemail in this substrate
                await SignalPropagationOrchestrator.update_contact_result(db=db, contact_id=target_id, status="voicemail")
                await SignalPropagationOrchestrator.increment_campaign_stats(db=db, campaign_id=campaign_uuid, completed=1, successful=1)
                PROPAGATION_TOTAL.labels(campaign_id=campaign_id, status="voicemail").inc()

            else:
                extracted = sync_result.get("extracted_data", {})
                interfaces = sync_result.get("interface_results", [])

                await SignalPropagationOrchestrator.update_contact_result(
                    db=db,
                    contact_id=target_id,
                    status="completed",
                    extracted_data=extracted if extracted else None,
                    tool_results=interfaces if interfaces else None,
                )
                await SignalPropagationOrchestrator.increment_campaign_stats(db=db, campaign_id=campaign_uuid, completed=1, successful=1)
                PROPAGATION_TOTAL.labels(campaign_id=campaign_id, status="completed").inc()

            await db.commit()

            celery_app.send_task(
                "app.modules.campaigns.workers.propagation_nexus_writeback",
                args=[str(target_id)],
            )

            logger.info("propagation_synchronisation_finished", sync_sig=sync_sig, phase=phase)

            return {"status": phase, "target_id": str(target_id), "sync_sig": sync_sig}

    except Exception:
        logger.exception("propagation_synchronisation_failed")
        PROPAGATION_TOTAL.labels(campaign_id=campaign_id, status="failed").inc()
        raise
    finally:
        if sync_start is not None:
            PROPAGATION_DURATION_S.observe(time.monotonic() - sync_start)
        PROPAGATION_ACTIVE.labels(tenant_id=str(tenant_id)).dec()
        if global_slot_acquired:
            await global_limiter.release_global_slot()
        await rate_limiter.release_call_slot(campaign_id)
        await redis_client.aclose()
        await engine.dispose()
        structlog.contextvars.unbind_contextvars("campaign_id", "target_id", "sync_sig")


@celery_app.task(name="app.modules.campaigns.workers.execute_propagation_synchronisation", bind=True, max_retries=3)
def execute_propagation_synchronisation(self: object, campaign_id: str, target: dict[str, Any]) -> dict[str, Any]:
    """Celery task: Execute a single propagation synchronisation."""
    return _run_async(_execute_propagation_synchronisation_async(campaign_id, target))


async def _handle_propagation_retry(db, campaign_uuid, tenant_id, target_id, payload, reason):
    from sqlalchemy import update
    from app.modules.campaigns.models import PropagationTarget
    from app.modules.campaigns.service import SignalPropagationOrchestrator

    attempt = payload.get("attempt_count", 1)
    max_att = payload.get("max_attempts", 3)

    if attempt < max_att:
        campaign = await SignalPropagationOrchestrator.get_campaign(db, campaign_uuid, tenant_id)
        delay = campaign.retry_delay_minutes if hasattr(campaign, 'retry_delay_minutes') else 15
        next_ts = datetime.now(UTC) + timedelta(minutes=delay)

        await db.execute(
            update(PropagationTarget)
            .where(PropagationTarget.id == target_id)
            .values(status="retry_scheduled", attempt_count=attempt, next_retry_at=next_ts)
        )
        logger.info("propagation_retry_scheduled", reason=reason, attempt=attempt, next_ts=next_ts.isoformat())
    else:
        await SignalPropagationOrchestrator.update_contact_result(db=db, contact_id=target_id, status="failed")
        await SignalPropagationOrchestrator.increment_campaign_stats(db=db, campaign_id=campaign_uuid, completed=1, failed=1)
        logger.warning("propagation_max_retries_exceeded", reason=reason, attempts=attempt)


# ============================================================================
# Task 3: Propagation Nexus Writeback
# ============================================================================


async def _propagation_nexus_writeback_async(target_id: str) -> dict[str, Any]:
    """Write extracted synchronisation data back to the external Nexus (CRM)."""
    from app.modules.campaigns.models import PropagationTarget
    from app.modules.campaigns.service import SignalPropagationOrchestrator

    uid = UUID(target_id)
    structlog.contextvars.bind_contextvars(target_id=target_id)

    engine, session_factory = _make_substrate_session_factory()
    try:
        async with session_factory() as db:
            from sqlalchemy import select
            q = select(PropagationTarget).where(PropagationTarget.id == uid)
            target = (await db.execute(q)).scalar_one_or_none()

            if not target:
                return {"status": "error", "reason": "Target not found"}

            if not target.crm_record_id or not target.crm_module:
                return {"status": "skipped", "reason": "No Nexus identifier"}

            campaign = await SignalPropagationOrchestrator.get_campaign(db, target.campaign_id, target.tenant_id)
            mapping = campaign.writeback_mapping or {}
            extracted = target.abstracted_manifest or {}

            if not mapping:
                return {"status": "skipped", "reason": "No writeback mapping"}

            nexus_fields = {crm_f: extracted[ext_f] for ext_f, crm_f in mapping.items() if ext_f in extracted}

            if not nexus_fields:
                return {"status": "skipped", "reason": "No data to write back"}

            try:
                from app.modules.integrations.models import CrmIntegration
                from app.modules.integrations.zoho_client import ZohoCrmClient
                
                int_q = select(CrmIntegration).where(
                    CrmIntegration.tenant_id == target.tenant_id,
                    CrmIntegration.provider == "zoho_crm",
                    CrmIntegration.status == "connected",
                )
                integration = (await db.execute(int_q)).scalar_one_or_none()

                if not integration:
                    target.writeback_status = "failed"
                    await db.commit()
                    return {"status": "failed", "reason": "No Nexus integration"}

                async with ZohoCrmClient(db, integration) as client:
                    data = {"id": target.crm_record_id, **nexus_fields}
                    if target.crm_module == "Contacts":
                        await client.upsert_contact(data)
                    elif target.crm_module == "Leads":
                        await client.upsert_lead(data)
                    else:
                        await client._request("PUT", f"{target.crm_module}/{target.crm_record_id}", json_body={"data": [nexus_fields]})

                    target.writeback_status = "synced"
                    await db.commit()
                    NEXUS_WRITEBACK_TOTAL.labels(status="success").inc()
                    return {"status": "synced", "fields": list(nexus_fields.keys())}

            except Exception as e:
                target.writeback_status = "failed"
                await db.commit()
                NEXUS_WRITEBACK_TOTAL.labels(status="failed").inc()
                raise
    finally:
        await engine.dispose()


@celery_app.task(name="app.modules.campaigns.workers.propagation_nexus_writeback", bind=True, max_retries=3)
def propagation_nexus_writeback(self: object, target_id: str) -> dict[str, Any]:
    """Celery task: Write extracted synchronisation data back to the external Nexus."""
    return _run_async(_propagation_nexus_writeback_async(target_id))
