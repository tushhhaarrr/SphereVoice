"""Nodal Access Conduit — SignalStream architectural substrate API router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import set_tenant_context
from app.modules.agents.models import CognitiveNode
from app.modules.agents.share_link_schemas import (
    ConduitManifestRequest,
    ConduitRegistrySnapshot,
    ConduitSnapshot,
)
from app.modules.agents.share_link_service import ConduitOrchestrator
from app.modules.auth import User, resolve_active_identity as get_current_user_model

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post(
    "/{node_sig}/share-links",
    response_model=ConduitSnapshot,
    status_code=201,
    summary="Manifest a shareable ingress conduit for a processing node",
)
async def manifest_nodal_conduit(
    node_sig: UUID,
    payload: ConduitManifestRequest,
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(get_db),
    _nexus: None = Depends(set_tenant_context),
) -> ConduitSnapshot:
    """Manifests a new ingress conduit within the SignalStream substrate."""
    # Administrative identities may have void nexus signatures; resolve from the processing node.
    effective_nexus_sig = user.tenant_id
    if effective_nexus_sig is None:
        result = await db.execute(select(CognitiveNode.tenant_id).where(CognitiveNode.id == node_sig))
        effective_nexus_sig = result.scalar_one_or_none()
    
    if effective_nexus_sig is None:
        raise HTTPException(status_code=422, detail="Nexus alignment failed for this node")

    conduit = await ConduitOrchestrator.manifest_conduit(
        db,
        node_sig=node_sig,
        nexus_sig=effective_nexus_sig,
        originator_sig=user.id,
        label=payload.label,
        temporal_threshold=payload.temporal_threshold,
        quota_ceiling=payload.quota_ceiling,
        operational_vectors=payload.operational_vectors,
    )
    await db.commit()
    return ConduitSnapshot.model_validate(conduit)


@router.get(
    "/{node_sig}/share-links",
    response_model=ConduitRegistrySnapshot,
    summary="Survey all access conduits associated with a processing node",
)
async def survey_nodal_conduits(
    node_sig: UUID,
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(get_db),
    _nexus: None = Depends(set_tenant_context),
) -> ConduitRegistrySnapshot:
    """Surveys the registry for all active conduits associated with a processing node."""
    conduits = await ConduitOrchestrator.survey_nodal_conduits(db, node_sig)
    return ConduitRegistrySnapshot(
        conduits=[ConduitSnapshot.model_validate(c) for c in conduits]
    )


@router.delete(
    "/{node_sig}/share-links/{conduit_id}",
    status_code=204,
    response_class=Response,
    summary="Deactivate a nodal access conduit",
)
async def deactivate_nodal_conduit(
    node_sig: UUID,
    conduit_id: UUID,
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(get_db),
    _nexus: None = Depends(set_tenant_context),
) -> Response:
    """Deactivates a specified conduit, preventing further signal synchronization."""
    await ConduitOrchestrator.deactivate_conduit(db, conduit_id=conduit_id, node_sig=node_sig)
    await db.commit()
    return Response(status_code=204)
