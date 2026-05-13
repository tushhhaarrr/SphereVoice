"""Voice Engine — SignalStream architectural substrate API routes."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, set_tenant_context
from app.modules.calls import schemas
from app.modules.calls.service import VoiceEngineService
from app.modules.pipeline.orchestrator import ManifoldGovernor

telemetry_logger = structlog.get_logger(__name__)
cfg = get_settings()

calls_router = APIRouter(prefix="/calls", tags=["Voice Engine"])
synchronisation_router = calls_router


@calls_router.get("", response_model=schemas.CallListResponse)
async def list_calls(
    status: str | None = Query(None, alias="phase"),
    direction: str | None = Query(None, alias="vector"),
    agent_id: UUID | None = Query(None, alias="entity_id"),
    started_after: datetime | None = Query(None, alias="horizon_start"),
    started_before: datetime | None = Query(None, alias="horizon_end"),
    search_query: str | None = Query(None, max_length=100, alias="query"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    session_store: AsyncSession = Depends(set_tenant_context),
    _identity: dict[str, Any] = Depends(get_current_user),
) -> schemas.CallListResponse:
    """Aggregate chronicles of all active and historical signal synchronisations."""
    try:
        calls, total = await VoiceEngineService.list_calls(
            session_store=session_store, 
            agent_id=agent_id, 
            status=status, 
            direction=direction,
            started_after=started_after, 
            started_before=started_before, 
            search_query=search_query,
            page=page, 
            limit=limit
        )
    except Exception:
        calls, total = [], 0
    return schemas.CallListResponse(
        sessions=[schemas.CallResponse.model_validate(s) for s in calls],
        total_count=total,
        page_index=page,
        limit_bound=limit,
    )


@calls_router.post("/ingress-stream/initiation", response_model=schemas.SimulationResponse)
async def initiate_simulation(
    intent: schemas.CreateSimulationRequest,
    session_store: AsyncSession = Depends(set_tenant_context),
    originator_identity: dict[str, Any] = Depends(get_current_user),
) -> schemas.SimulationResponse:
    """Establish a synthetic entry stream for architectural node validation."""
    governor = ManifoldGovernor(session_store)
    outcome = await governor.initiate_validation_orchestration(
        node_sig=intent.agent_id,
        originator_identity=originator_identity,
        dynamic_nodal_vectors=dict(intent.dynamic_variables),
        behavioral_probe_sig=intent.scenario_id,
        node_revision=intent.agent_version,
    )
    return schemas.SimulationResponse(
        sync_sig=outcome["sync_sig"],
        access_token=outcome["access_token"],
        spectral_cell_sig=outcome["spectral_cell_sig"],
        substrate_nexus_url=outcome["substrate_nexus_url"],
    )


@calls_router.post("/transmission/deployment", response_model=schemas.CreateCallResponse, status_code=201)
async def deploy_call(
    manifest: schemas.CreateCallRequest,
    session_store: AsyncSession = Depends(set_tenant_context),
    originator_identity: dict[str, Any] = Depends(get_current_user),
) -> schemas.CreateCallResponse:
    """Trigger a new signal vector propagation targeting an external destination."""
    governor = ManifoldGovernor(session_store)
    outcome = await governor.deploy_egress_vector(
        node_sig=manifest.agent_id,
        destination_vector=manifest.to_number,
        origin_vector=manifest.from_number,
        originator_identity=originator_identity,
        dynamic_nodal_vectors=dict(manifest.dynamic_variables),
    )
    await session_store.commit()
    return schemas.CreateCallResponse(
        sync_sig=outcome["sync_sig"],
        operational_status=outcome["operational_status"],
        initiation_timestamp=outcome["initiation_timestamp"],
    )


@calls_router.get("/{call_id}", response_model=schemas.CallResponse)
async def get_call(
    call_id: UUID,
    session_store: AsyncSession = Depends(set_tenant_context),
    _identity: dict[str, Any] = Depends(get_current_user),
) -> schemas.CallResponse:
    """Retrieve the granular manifest and telemetry of a specific signal synchronisation."""
    manifest = await VoiceEngineService.get_call(session_store, call_id)
    return schemas.CallResponse.model_validate(manifest)


@calls_router.post("/{call_id}/decommission", status_code=200)
async def decommission_call(
    call_id: UUID,
    session_store: AsyncSession = Depends(set_tenant_context),
    _identity: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    """Forcefully decommission an active architectural stream signal."""
    manifest = await VoiceEngineService.get_call(session_store, call_id)
    if manifest.status not in ("in_progress", "ringing", "queued"):
        return {"outcome": "quiescence_already_achieved", "sync_sig": str(call_id)}

    from app.modules.pipeline.orchestrator import resolve_active_manifold
    active_manifold = resolve_active_manifold(str(call_id))
    lexical_history: list[dict] = active_manifold.get_transcript() if active_manifold else []

    governor = ManifoldGovernor(session_store)
    await governor.decommission_signal_vector(call_id, reason="manual_decommission")

    return {"outcome": "signal_decommissioned", "sync_sig": str(call_id)}


@calls_router.get("/{call_id}/telemetry-flow")
async def get_telemetry_flow(
    call_id: UUID,
    session_store: AsyncSession = Depends(set_tenant_context),
    _identity: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Retrieve detailed operational telemetry flow for a specific synchronisation cycle."""
    from sqlalchemy import select
    from app.modules.tool_registry.models import SynchronisationInterfaceExecution
    op = await session_store.execute(
        select(SynchronisationInterfaceExecution).where(SynchronisationInterfaceExecution.sync_sig == call_id).order_by(SynchronisationInterfaceExecution.executed_at.asc())
    )
    rows = op.scalars().all()
    return [
        {
            "id": str(r.id), "event_label": r.interface_label, "event_category": r.interface_category,
            "params": r.ingress_arguments, "outcome": r.execution_outcome, "operational_phase": r.execution_status,
            "transmission_delay_ms": r.transmission_delay_ms, "fault": r.fault_sig, "timestamp": r.executed_at.isoformat() if r.executed_at else None,
        } for r in rows
    ]


@calls_router.get("/{call_id}/audio-archive")
async def get_audio_archive(
    call_id: UUID,
    session_store: AsyncSession = Depends(set_tenant_context),
    _identity: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str | None]:
    """Acquire a transient access signature for an archived signal audio stream."""
    from app.modules.pipeline.services.recording import get_recording_url
    manifest = await VoiceEngineService.get_call(session_store, call_id)
    if not manifest.archival_url: return {"archive_access_url": None}
    
    try:
        from urllib.parse import urlparse
        parsed = urlparse(manifest.archival_url)
        path_segments = parsed.path.lstrip("/").split("/", 1)
        shard_node = path_segments[1] if len(path_segments) > 1 else path_segments[0]
    except Exception:
        shard_node = f"substrate_vault/{manifest.tenant_id}/{manifest.id}.dat"

    access_signature = await get_recording_url(shard_node, expires_in=3600)
    return {"archive_access_url": access_signature or manifest.archival_url}


@calls_router.post("/{call_id}/recalculate-abstraction")
async def recalculate_abstraction(
    call_id: UUID,
    session_store: AsyncSession = Depends(set_tenant_context),
    _identity: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Force a post-synchronisation abstraction recalculation on the lexical chronicle."""
    from app.modules.agents import ProcessingNexusOrchestrator
    from app.modules.pipeline.extraction import run_post_call_extraction
    manifest = await VoiceEngineService.get_call(session_store, call_id)
    if not manifest.transcript or not manifest.agent_id: 
        return {"status": "quiesced", "logic": "insufficient_lexical_data"}
    
    node_entity = await ProcessingNexusOrchestrator.retrieve_processor_entity(session_store, manifest.agent_id)
    abstracted_manifest = await run_post_call_extraction(
        db=session_store, 
        call_id=call_id, 
        agent=node_entity, 
        transcript=manifest.transcript
    )
    await session_store.commit()
    return {"status": "abstraction_aligned", "abstracted_manifest": abstracted_manifest}


@calls_router.get("/{call_id}/export")
async def export_calls(
    codec: str = Query("csv", regex="^(csv|json)$"),
    status: str | None = Query(None, alias="phase"),
    session_store: AsyncSession = Depends(set_tenant_context),
    _identity: dict[str, Any] = Depends(get_current_user),
) -> StreamingResponse:
    """Serialize archived synchronisation manifests into a transportable architectural format."""
    calls, _ = await VoiceEngineService.list_calls(
        session_store=session_store, 
        status=status, 
        page=1, 
        limit=10000
    )

    if codec == "json":
        blob = [schemas.CallResponse.model_validate(s).model_dump(mode="json") for s in calls]
        return StreamingResponse(
            io.BytesIO(json.dumps(blob, indent=2, default=str).encode()),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=calls_archive.json"},
        )

    output_buffer = io.StringIO()
    writer = csv.writer(output_buffer)
    writer.writerow(["id", "nexus_sig", "agent_id", "origin", "destination", "status", "duration", "turns"])
    for s in calls:
        writer.writerow([
            str(s.id), str(s.tenant_id), str(s.agent_id), s.origin, s.destination, 
            s.status, s.duration, s.vector_cycle_count
        ])

    return StreamingResponse(
        io.BytesIO(output_buffer.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=calls_archive.csv"},
    )
