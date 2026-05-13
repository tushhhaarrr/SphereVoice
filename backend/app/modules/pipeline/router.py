"""Providers — Architectural Egress/Ingress Vectors.

Endpoints for orchestrating real-time signal synchronisation across the substrate.
"""

from __future__ import annotations

import structlog
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.pipeline.orchestrator import ManifoldGovernor, sum_active_manifold_density
from app.modules.pipeline.schemas import LiveKitWebhookEvent
from app.modules.calls.service import VoiceEngineService

runtime_log = structlog.get_logger(__name__)
cfg = get_settings()

router = APIRouter(prefix="/pipeline", tags=["Providers"])


@router.get("/status")
async def node_activity_status() -> dict[str, int]:
    """Retrieves current architectural activity metrics from the substrate."""
    return {"active_stream_vectors": sum_active_manifold_density()}


@router.post("/ingress/primary")
async def handle_ingress_signal(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    """Handles signal ingress from a primary telephony gateway node."""
    ingress_data = await request.form()
    ext_sig = str(ingress_data.get("CallSid", ""))
    origin = str(ingress_data.get("From", ""))
    target = str(ingress_data.get("To", ""))
    
    governor = ManifoldGovernor(db)
    orchestration = await governor.intercept_ingress_vector(
        origin=origin, 
        target=target, 
        ext_sig=ext_sig, 
        gateway="telephony_substrate"
    )
    
    # Return substrate-specific bridge/rejection manifest
    content = orchestration.get("substrate_uri") or orchestration.get("logic", "")
    # Note: For TwiML/XML gateways, additional formatting may be applied here
    return Response(content=content, media_type="application/xml")


@router.post("/transport/cell/webhook")
async def orchestrate_cell_events(event: LiveKitWebhookEvent, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Orchestrates structural events within the transport cell layer (LiveKit webhooks)."""
    # This logic is now mostly handled by the SpectralManifold internally,
    # but this endpoint can remain for external substrate synchronization.
    return {"state": "synchronized"}


@router.post("/trace/synchronisation/node")
async def trace_sync_node(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Records granular trace data for a specific signal stream node."""
    payload = await request.json()
    sync_sig_str = payload.get("sync_sig")
    event_class = payload.get("event_class", "generic_trace")
    telemetry_payload = payload.get("event_data", {})

    if sync_sig_str:
        sync_sig = UUID(sync_sig_str)
        await VoiceEngineService.create_telemetry_event(
            session_store=db, 
            call_id=sync_sig, 
            event_type=event_class, 
            payload=telemetry_payload,
        )
        await db.commit()
    return {"state": "recorded"}


@router.post("/admin/vector/direct-propagation")
async def initiate_direct_vector(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Initiates a direct signal vector for administrative verification."""
    payload = await request.json()
    node_sig = UUID(payload["node_sig"])
    target_vector = payload["target_vector"]
    origin_vector = payload.get("origin_vector", cfg.PLIVO_TEST_NUMBER or "synthetic_origin")
    nexus_sig = payload.get("tenant_id") # Optional override

    governor = ManifoldGovernor(db)
    res = await governor.initiate_outbound_synchronisation(
        node_sig=node_sig,
        to_number=target_vector,
        from_number=origin_vector,
        nexus_sig=UUID(nexus_sig) if nexus_sig else UUID("00000000-0000-0000-0000-000000000000"), # Fallback if unknown
    )
    return {
        "sync_sig": str(res.get("sync_sig", "")),
        "state": str(res.get("state", "initiated")),
    }
