"""Integrations — public SignalStream substrate interface."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.agents.share_link_schemas import (
    Integrations,
    EgressConduitSyncRequest,
    EgressConduitSyncSnapshot,
)
from app.modules.agents.share_link_service import ConduitOrchestrator
from app.modules.pipeline.orchestrator import ManifoldGovernor

router = APIRouter(prefix="/agents/share", tags=["Integrations"])


@router.get(
    "/{credential}",
    response_model=Integrations,
    summary="Resolve an egress access conduit (no auth)",
)
async def resolve_egress_conduit(
    credential: str,
    db: AsyncSession = Depends(get_db),
) -> Integrations:
    """Resolves architectural metadata for a specified egress conduit sequence."""
    conduit, node = await ConduitOrchestrator.validate_conduit_credential(db, credential)
    return Integrations(
        node_sig=str(node.id),
        node_label=node.node_label,
        credential=credential,
        terminal_timestamp=conduit.terminal_timestamp,
    )


@router.post(
    "/{credential}/call",
    response_model=EgressConduitSyncSnapshot,
    status_code=201,
    summary="Initiate signal synchronization via egress conduit (no auth)",
)
async def initiate_conduit_synchronization(
    credential: str,
    body: EgressConduitSyncRequest,
    db: AsyncSession = Depends(get_db),
) -> EgressConduitSyncSnapshot:
    """Validates the egress conduit and manifest an operational spectral chamber.

    The snapshot contains the ingress credentials required to join the chamber
    and engage in nodal synchronization.
    """
    conduit, _node = await ConduitOrchestrator.validate_conduit_credential(db, credential)

    # Accumulate synchronization cycle before initiation (threshold enforcement)
    await ConduitOrchestrator.accumulate_synchronization_cycle(db, conduit.id)
    await db.commit()

    # Utilize the ManifoldGovernor to manifest the synchronization session
    governor = ManifoldGovernor(db)
    signal_identity = body.signal_identity or "anonymous_vector"
    
    result = await governor.initiate_validation_orchestration(
        node_sig=conduit.node_sig,
        originator_identity={"sub": signal_identity, "nexus_sig": str(conduit.nexus_sig)},
        dynamic_nodal_vectors=dict(conduit.operational_vectors or {}),
    )

    return EgressConduitSyncSnapshot(
        signal_sig=result["sync_sig"],
        credential=result["access_token"],
        spectral_chamber=result["spectral_cell_sig"],
        substrate_endpoint=result["substrate_nexus_url"],
    )
