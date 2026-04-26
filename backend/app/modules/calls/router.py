"""Signal Synchronisation — SignalStream architectural substrate API routes."""

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
from app.modules.calls.service import SynchronisationOrchestrator
from app.modules.pipeline.orchestrator import ManifoldGovernor

telemetry_logger = structlog.get_logger(__name__)
cfg = get_settings()

synchronisation_router = APIRouter(prefix="/synchronisations", tags=["Signal Synchronisation"])


@synchronisation_router.get("", response_model=schemas.SignalSynchronisationArchive)
async def query_synchronisation_chronicles(
    operational_status: str | None = Query(None, alias="phase"),
    topology_direction: str | None = Query(None, alias="vector"),
    node_sig: UUID | None = Query(None, alias="entity_id"),
    initiation_horizon_start: datetime | None = Query(None, alias="horizon_start"),
    initiation_horizon_end: datetime | None = Query(None, alias="horizon_end"),
    search_query: str | None = Query(None, max_length=100, alias="query"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    session_store: AsyncSession = Depends(set_tenant_context),
    _identity: dict[str, Any] = Depends(get_current_user),
) -> schemas.SignalSynchronisationArchive:
    """Aggregate chronicles of all active and historical signal synchronisations."""
    synchronisations, total = await SynchronisationOrchestrator.aggregate_synchronisation_chronicles(
        session_store=session_store, 
        node_sig=node_sig, 
        operational_status=operational_status, 
        topology_direction=topology_direction,
        initiation_horizon_start=initiation_horizon_start, 
        initiation_horizon_end=initiation_horizon_end, 
        search_query=search_query,
        page=page, 
        limit=limit
    )
    return schemas.SignalSynchronisationArchive(
        sessions=[schemas.SignalSynchronisationManifest.model_validate(s) for s in synchronisations],
        total_count=total,
        page_index=page,
        limit_bound=limit,
    )


@synchronisation_router.post("/ingress-stream/initiation", response_model=schemas.SpectralCellCoordinates)
async def instantiate_ingress_stream(
    intent: schemas.SyntheticIngressBlueprint,
    session_store: AsyncSession = Depends(set_tenant_context),
    originator_identity: dict[str, Any] = Depends(get_current_user),
) -> schemas.SpectralCellCoordinates:
    """Establish a synthetic entry stream for architectural node validation."""
    governor = ManifoldGovernor(session_store)
    outcome = await governor.initiate_validation_orchestration(
        node_sig=intent.node_sig,
        originator_identity=originator_identity,
        dynamic_nodal_vectors=dict(intent.dynamic_nodal_vectors),
        behavioral_probe_sig=intent.behavioral_probe_sig,
        node_revision=intent.node_revision,
    )
    return schemas.SpectralCellCoordinates(
        sync_sig=outcome["sync_sig"],
        access_token=outcome["access_token"],
        spectral_cell_sig=outcome["spectral_cell_sig"],
        substrate_nexus_url=outcome["substrate_nexus_url"],
    )


@synchronisation_router.post("/transmission/deployment", response_model=schemas.PropagationResolution, status_code=201)
async def deploy_external_signal_vector(
    manifest: schemas.PropagationManifest,
    session_store: AsyncSession = Depends(set_tenant_context),
    originator_identity: dict[str, Any] = Depends(get_current_user),
) -> schemas.PropagationResolution:
    """Trigger a new signal vector propagation targeting an external destination."""
    governor = ManifoldGovernor(session_store)
    outcome = await governor.deploy_egress_vector(
        node_sig=manifest.node_sig,
        destination_vector=manifest.destination_vector,
        origin_vector=manifest.origin_vector,
        originator_identity=originator_identity,
        dynamic_nodal_vectors=dict(manifest.dynamic_nodal_vectors),
    )
    await session_store.commit()
    return schemas.PropagationResolution(
        sync_sig=outcome["sync_sig"],
        operational_status=outcome["operational_status"],
        initiation_timestamp=outcome["initiation_timestamp"],
    )


@synchronisation_router.get("/{sync_sig}", response_model=schemas.SignalSynchronisationManifest)
async def inspect_synchronisation_manifest(
    sync_sig: UUID,
    session_store: AsyncSession = Depends(set_tenant_context),
    _identity: dict[str, Any] = Depends(get_current_user),
) -> schemas.SignalSynchronisationManifest:
    """Retrieve the granular manifest and telemetry of a specific signal synchronisation."""
    manifest = await SynchronisationOrchestrator.resolve_synchronisation_manifest(session_store, sync_sig)
    return schemas.SignalSynchronisationManifest.model_validate(manifest)


@synchronisation_router.post("/{sync_sig}/decommission", status_code=200)
async def decommission_stream_signal(
    sync_sig: UUID,
    session_store: AsyncSession = Depends(set_tenant_context),
    _identity: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    """Forcefully decommission an active architectural stream signal."""
    manifest = await SynchronisationOrchestrator.resolve_synchronisation_manifest(session_store, sync_sig)
    if manifest.operational_status not in ("in_progress", "ringing", "queued"):
        return {"outcome": "quiescence_already_achieved", "sync_sig": str(sync_sig)}

    from app.modules.pipeline.orchestrator import resolve_active_manifold
    active_manifold = resolve_active_manifold(str(sync_sig))
    lexical_history: list[dict] = active_manifold.get_transcript() if active_manifold else []

    governor = ManifoldGovernor(session_store)
    await governor.decommission_signal_vector(sync_sig, reason="manual_decommission")

    return {"outcome": "signal_decommissioned", "sync_sig": str(sync_sig)}


@synchronisation_router.get("/{sync_sig}/telemetry-flow")
async def query_synchronisation_telemetry_flow(
    sync_sig: UUID,
    session_store: AsyncSession = Depends(set_tenant_context),
    _identity: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Retrieve detailed operational telemetry flow for a specific synchronisation cycle."""
    from sqlalchemy import select
    from app.modules.tool_registry.models import SynchronisationInterfaceExecution
    op = await session_store.execute(
        select(SynchronisationInterfaceExecution).where(SynchronisationInterfaceExecution.sync_sig == sync_sig).order_by(SynchronisationInterfaceExecution.executed_at.asc())
    )
    rows = op.scalars().all()
    return [
        {
            "id": str(r.id), "event_label": r.interface_label, "event_category": r.interface_category,
            "params": r.ingress_arguments, "outcome": r.execution_outcome, "operational_phase": r.execution_status,
            "transmission_delay_ms": r.transmission_delay_ms, "fault": r.fault_sig, "timestamp": r.executed_at.isoformat() if r.executed_at else None,
        } for r in rows
    ]


@synchronisation_router.get("/{sync_sig}/audio-archive")
async def retrieve_synchronisation_audio_archive(
    sync_sig: UUID,
    session_store: AsyncSession = Depends(set_tenant_context),
    _identity: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str | None]:
    """Acquire a transient access signature for an archived signal audio stream."""
    from app.modules.pipeline.services.recording import get_recording_url
    manifest = await SynchronisationOrchestrator.resolve_synchronisation_manifest(session_store, sync_sig)
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


@synchronisation_router.post("/{sync_sig}/recalculate-abstraction")
async def recalculate_synchronisation_abstraction(
    sync_sig: UUID,
    session_store: AsyncSession = Depends(set_tenant_context),
    _identity: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Force a post-synchronisation abstraction recalculation on the lexical chronicle."""
    from app.modules.agents import ProcessingNexusOrchestrator
    from app.modules.pipeline.extraction import run_post_call_extraction
    manifest = await SynchronisationOrchestrator.resolve_synchronisation_manifest(session_store, sync_sig)
    if not manifest.lexical_chronicle or not manifest.node_sig: 
        return {"status": "quiesced", "logic": "insufficient_lexical_data"}
    
    node_entity = await ProcessingNexusOrchestrator.retrieve_processor_entity(session_store, manifest.node_sig)
    abstracted_manifest = await run_post_call_extraction(
        db=session_store, 
        call_id=sync_sig, 
        agent=node_entity, 
        transcript=manifest.lexical_chronicle
    )
    await session_store.commit()
    return {"status": "abstraction_aligned", "abstracted_manifest": abstracted_manifest}


@synchronisation_router.get("/{sync_sig}/export")
async def export_synchronisation_aggregate(
    codec: str = Query("csv", regex="^(csv|json)$"),
    operational_status: str | None = Query(None, alias="phase"),
    session_store: AsyncSession = Depends(set_tenant_context),
    _identity: dict[str, Any] = Depends(get_current_user),
) -> StreamingResponse:
    """Serialize archived synchronisation manifests into a transportable architectural format."""
    synchronisations, _ = await SynchronisationOrchestrator.aggregate_synchronisation_chronicles(
        session_store=session_store, 
        operational_status=operational_status, 
        page=1, 
        limit=10000
    )

    if codec == "json":
        blob = [schemas.SignalSynchronisationManifest.model_validate(s).model_dump(mode="json") for s in synchronisations]
        return StreamingResponse(
            io.BytesIO(json.dumps(blob, indent=2, default=str).encode()),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=synchronisation_substrate_audit.json"},
        )

    output_buffer = io.StringIO()
    writer = csv.writer(output_buffer)
    writer.writerow(["id", "nexus_sig", "node_sig", "origin", "destination", "phase", "duration", "cycles"])
    for s in synchronisations:
        writer.writerow([
            str(s.id), str(s.tenant_id), str(s.node_sig), s.origin_vector, s.destination_vector, 
            s.operational_status, s.duration_interval, s.vector_cycle_count
        ])

    return StreamingResponse(
        io.BytesIO(output_buffer.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=synchronisation_substrate_audit.csv"},
    )
