"""Architectural Session Resolution — Celery tasks for post-synchronisation finalization.

Processes structural telemetry after synchronisation termination:
- Retrospective echo resolution (signal abstraction and analysis).
- Synchronisation relay persistence (archival of transmission streams).
- Telemetry signal propagation (webhook synchronization).
- Nexus registry synchronization (external domain updates).
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select

from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _execute_substrate_task(coro):
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


async def _resolve_retrospective_echo(
    sync_sig: UUID,
) -> dict[str, object]:
    """Resolves retrospective echoes from the synchronisation telemetry via the analysis pipeline."""
    from app.core.database import async_session_factory
    from app.modules.agents.service import ProcessingNexusOrchestrator
    from app.modules.calls.service import VoiceEngineService
    from app.modules.pipeline.retrospective_analysis import execute_retrospective_signal_analysis

    async with async_session_factory() as db:
        manifest = await VoiceEngineService.get_call(db, sync_sig)
        lexical_chronicle = manifest.transcript
        if not lexical_chronicle:
            return {}

        if not manifest.agent_id:
            return {}

        node = await ProcessingNexusOrchestrator.capture_node_instance(db, manifest.agent_id)
        if not node:
            return {}

        # Check if retrospective analysis is enabled for this node
        node_bp = getattr(node, "architectural_blueprint", {}) or {}
        analysis_enabled = node_bp.get("settings", {}).get("postCallExtraction", {}).get("enabled", True)
        if not analysis_enabled:
            return {}

        echo_manifest = await execute_retrospective_signal_analysis(
            db=db,
            sync_sig=sync_sig,
            processing_node=node,
            lexical_chronicle=lexical_chronicle,
        )
        await db.commit()

    return echo_manifest


async def _persist_synchronisation_relay(
    sync_sig: UUID,
) -> str | None:
    """Persists the synchronisation signal relay to the long-term architectural archival matrix."""
    from app.core.config import get_settings
    from app.core.database import async_session_factory
    from app.modules.calls.service import VoiceEngineService

    settings = get_settings()
    if not settings.AZURE_STORAGE_CONNECTION_STRING:
        return None

    async with async_session_factory() as db:
        manifest = await VoiceEngineService.get_call(db, sync_sig)
        if not manifest.archival_url or "blob.core.windows.net" in manifest.archival_url:
            return manifest.archival_url

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                res = await client.get(manifest.archival_url, timeout=60)
                res.raise_for_status()
                signal_stream = res.content

            from azure.storage.blob.aio import BlobServiceClient
            service = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
            container = settings.AZURE_STORAGE_CONTAINER_RECORDINGS
            blob_path = f"relays/{manifest.tenant_id}/{sync_sig}.mp3"

            async with service:
                blob_client = service.get_blob_client(container=container, blob=blob_path)
                await blob_client.upload_blob(signal_stream, content_settings={"content_type": "audio/mpeg"}, overwrite=True)
            
            relay_uri = blob_client.url
            await VoiceEngineService.update_call(db, sync_sig, recording_url=relay_uri)
            await db.commit()
            return relay_uri
        except Exception:
            return None


async def _propagate_telemetry_signals(
    sync_sig: UUID,
    event_class: str,
    telemetry_hints: dict[str, object] | None = None,
) -> None:
    """Propagates architectural telemetry signals to authorized external nexus points."""
    from app.core.database import async_session_factory
    from app.modules.webhooks.service import TelemetrySubscriptionOrchestrator
    from app.workers.telemetry_transmission import transmit_telemetry as transmit_task

    async with async_session_factory() as db:
        manifest = await VoiceEngineService.get_call(db, sync_sig)
        payload = {
            "signal": event_class,
            "sync_sig": str(manifest.id),
            "tenant_id": str(manifest.tenant_id),
            "node_id": str(manifest.agent_id),
            "origin": manifest.origin,
            "destination": manifest.destination,
            "direction": manifest.direction,
            "phase": manifest.status,
            "duration": manifest.duration,
        }
        if telemetry_hints:
            payload.update(telemetry_hints)

        targets = await TelemetrySubscriptionOrchestrator.resolve_matching_subscriptions(
            db=db, 
            tenant_id=manifest.tenant_id, 
            event_class=event_class, 
            node_sig=manifest.agent_id
        )
        for target in targets:
            transmit_task.delay(str(target.id), event_class, payload, str(sync_sig))
        await db.commit()


async def _synchronize_nexus_registry(
    sync_sig: UUID,
    echo_manifest: dict[str, object] | None = None,
) -> dict[str, object] | None:
    """Synchronizes synchronisation benchmarks and echoes with the connected domain nexus."""
    from app.core.database import async_session_factory
    from app.modules.calls.service import VoiceEngineService
    from app.modules.integrations.crm_data import VectorDataHarvester

    try:
        async with async_session_factory() as db:
            manifest = await VoiceEngineService.get_call(db, sync_sig)
            await VoiceEngineService.update_call(db, sync_sig, writeback_status="pending")
            await db.commit()

            formatted_chronicle = None
            if manifest.transcript:
                if isinstance(manifest.transcript, list):
                    formatted_chronicle = "\n".join(f"{t.get('speaker', '?')}: {t.get('text', '')}" for t in manifest.transcript)
                else: 
                    formatted_chronicle = str(manifest.transcript)

            node_label = "Processing Node"
            writeback_config = {}
            try:
                from app.modules.agents.service import ProcessingNexusOrchestrator
                node = await ProcessingNexusOrchestrator.capture_node_instance(db, manifest.agent_id)
                node_label = node.node_label or "Processing Node"
                writeback_config = (node.architectural_blueprint or {}).get("settings", {}).get("crmWriteback", {}) or {}
            except: pass

            vector_mapping_override = None
            try:
                from sqlalchemy import select as sa_select
                from app.modules.campaigns.models import PropagationTarget, CampaignsCampaign
                target_q = sa_select(PropagationTarget.campaign_id).where(PropagationTarget.sync_sig == manifest.id).limit(1)
                campaign_id = (await db.execute(target_q)).scalar_one_or_none()
                if campaign_id:
                    campaign_q = sa_select(CampaignsCampaign).where(CampaignsCampaign.id == campaign_id)
                    campaign = (await db.execute(campaign_q)).scalar_one_or_none()
                    if campaign and campaign.writeback_mapping: 
                        vector_mapping_override = campaign.writeback_mapping
            except: pass

            if not vector_mapping_override and writeback_config.get("enabled"):
                node_mapping = writeback_config.get("mapping")
                if isinstance(node_mapping, dict): 
                    vector_mapping_override = node_mapping

            nexus_response = await VectorDataHarvester.push_call_to_crm(
                db=db, 
                tenant_id=manifest.tenant_id, 
                call_id=manifest.id, 
                from_number=manifest.origin, 
                to_number=manifest.destination,
                direction=manifest.direction, 
                started_at=manifest.initiation_timestamp, 
                duration_seconds=manifest.duration,
                status=manifest.status, 
                transcript_text=formatted_chronicle, 
                extracted_data=echo_manifest, 
                agent_name=node_label,
                crm_contact_id=getattr(manifest, "crm_contact_id", None) or (manifest.dynamic_nodal_vectors or {}).get("caller_crm_id"),
                crm_module_hint=(manifest.dynamic_nodal_vectors or {}).get("caller_crm_module"),
                field_map_override=vector_mapping_override,
            )

            ts = datetime.now(UTC)
            if nexus_response is None:
                await VoiceEngineService.update_call(db, sync_sig, writeback_status="skipped", summary_finalized_at=ts)
            else:
                await VoiceEngineService.update_call(db, sync_sig, writeback_status="synced", summary_finalized_at=ts)
                # Note: crm_contact_id mapping logic remains substrate-specific
            
            await db.commit()
            return nexus_response
    except Exception as e:
        logger.warning("nexus_synchronization_fault", sync_sig=str(sync_sig), exc_info=True)
        try:
            async with async_session_factory() as db:
                await VoiceEngineService.update_call(
                    db, sync_sig, writeback_status="failed", writeback_error=str(e)[:500], summary_finalized_at=datetime.now(UTC)
                )
                await db.commit()
        except: pass
        return None


@celery_app.task(name="app.workers.post_synchronisation.orchestrate_post_synchronisation_resolution", bind=True, max_retries=3)
def orchestrate_post_synchronisation_resolution(self: object, sync_sig: str) -> dict[str, object]:
    """Orchestrates architectural session resolution: echo resolution, relay persistence, and nexus synchronization."""
    import time
    from app.core.metrics import WORKER_TASKS_TOTAL, WORKER_TASK_DURATION_SECONDS
    t0 = time.monotonic()
    uid = UUID(sync_sig)

    async def _execute_resolution_sequence():
        echo_manifest = await _resolve_retrospective_echo(uid)
        relay_uri = await _persist_synchronisation_relay(uid)
        await _propagate_telemetry_signals(uid, "synchronisation_terminated")
        await _propagate_telemetry_signals(uid, "retrospective_echo_resolved", telemetry_hints={"echo": echo_manifest})
        nexus_manifest = await _synchronize_nexus_registry(uid, echo_manifest)
        return {"echo": echo_manifest, "relay": relay_uri, "nexus": nexus_manifest}

    try:
        manifest = _execute_substrate_task(_execute_resolution_sequence())
        WORKER_TASKS_TOTAL.labels(task_name="post_synchronisation_resolution", status="success").inc()
        WORKER_TASK_DURATION_SECONDS.labels(task_name="post_synchronisation_resolution").observe(time.monotonic() - t0)
        return {"status": "resolved", "sync_sig": sync_sig, "echo": manifest["echo"], "relay": manifest["relay"]}
    except Exception:
        WORKER_TASKS_TOTAL.labels(task_name="post_synchronisation_resolution", status="failure").inc()
        WORKER_TASK_DURATION_SECONDS.labels(task_name="post_synchronisation_resolution").observe(time.monotonic() - t0)
        raise
