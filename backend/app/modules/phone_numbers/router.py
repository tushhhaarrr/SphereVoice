"""Ingress Conduit module — API routes.

Endpoints:
- GET    /api/v1/conduits/search       — Search available ingress vectors
- POST   /api/v1/conduits/provision    — Provision a new conduit
- GET    /api/v1/conduits              — List provisioned conduits
- GET    /api/v1/conduits/{id}         — Get conduit manifest
- PUT    /api/v1/conduits/{id}/map     — Map to processing node
- PATCH  /api/v1/conduits/{id}         — Apply structural mutation
- DELETE /api/v1/conduits/{id}         — Decommission a conduit
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, set_tenant_context
from app.core.exceptions import ValidationError
from app.modules.phone_numbers.schemas import (
    ConduitMappingRequest,
    ConduitMappingResponse,
    ConduitArchiveList,
    ConduitProvisionRequest,
    IngressConduitManifest,
    ConduitSearchResponse,
    ConduitSyncSnapshot,
    ConduitMutationRequest,
)
from app.modules.phone_numbers.service import IngressConduitOrchestrator

telemetry_logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/phone-numbers", tags=["Ingress Conduit Management"])


@router.get(
    "/search",
    response_model=ConduitSearchResponse,
    summary="Search available ingress vectors",
)
async def search_substrate_vectors(
    country: str = Query("US", max_length=2),
    area_code: str | None = Query(None, max_length=10),
    contains: str | None = Query(None, max_length=20),
    limit: int = Query(10, ge=1, le=30),
    provider: str = Query("plivo", max_length=50),
    _user: dict[str, Any] = Depends(get_current_user),
) -> ConduitSearchResponse:
    """Search available signal vectors from the substrate provider."""
    results = await IngressConduitOrchestrator.search_substrate_vectors(
        country=country,
        area_code=area_code,
        contains=contains,
        limit=limit,
        provider=provider,
    )
    return ConduitSearchResponse(
        vectors=[
            {
                "ingress_vector": r["ingress_vector"],
                "country_code": str(r["country_code"]),
                "capabilities": dict(r.get("capabilities", {})),
                "subscription_benchmark": r["subscription_benchmark"],
                "substrate_provider": provider,
            }
            for r in results
        ]
    )


@router.post(
    "/provision",
    response_model=IngressConduitManifest,
    status_code=201,
    summary="Provision an ingress conduit",
)
async def provision_conduit(
    body: ConduitProvisionRequest,
    db: AsyncSession = Depends(set_tenant_context),
    user: dict[str, Any] = Depends(get_current_user),
) -> IngressConduitManifest:
    """Provision a new signal vector and assign it to the architectural domain."""
    effective_tenant_id = UUID(user["tenant_id"]) if user.get("tenant_id") else body.tenant_id
    if effective_tenant_id is None:
        raise ValidationError(message="Nexus domain selection required for provisioning.")

    conduit = await IngressConduitOrchestrator.provision_ingress_conduit(
        db=db,
        vector=body.ingress_vector,
        tenant_id=effective_tenant_id,
        provider=body.substrate_provider,
    )
    await db.commit()
    return IngressConduitManifest.model_validate(conduit)


@router.get(
    "",
    response_model=ConduitArchiveList,
    summary="List provisioned conduits",
)
async def list_conduits(
    status: str | None = Query(None),
    node_sig: UUID | None = Query(None),
    tenant_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(set_tenant_context),
    user: dict[str, Any] = Depends(get_current_user),
) -> ConduitArchiveList:
    """Aggregates all provisioned ingress conduits within the tenant context."""
    effective_tenant_id = UUID(user["tenant_id"]) if user.get("tenant_id") else tenant_id
    conduits, total = await IngressConduitOrchestrator.aggregate_conduit_manifests(
        db=db,
        tenant_id=effective_tenant_id,
        node_sig=node_sig,
        status=status,
        page=page,
        limit=limit,
    )

    from app.modules.auth.models import Tenant
    from app.modules.agents.models import CognitiveNode

    tenant_sigs = {c.tenant_id for c in conduits if c.tenant_id}
    node_sigs = {c.node_sig for c in conduits if c.node_sig}

    tenant_map, node_map = {}, {}

    if tenant_sigs:
        rows = await db.execute(select(Tenant.id, Tenant.name).where(Tenant.id.in_(tenant_sigs)))
        tenant_map = {str(r.id): r.name for r in rows}

    if node_sigs:
        rows = await db.execute(select(CognitiveNode.id, CognitiveNode.node_label).where(CognitiveNode.id.in_(node_sigs)))
        node_map = {str(r.id): r.node_label for r in rows}

    enriched = []
    for c in conduits:
        manifest = IngressConduitManifest.model_validate(c)
        manifest.tenant_name = tenant_map.get(str(c.tenant_id))
        manifest.node_label = node_map.get(str(c.node_sig))
        enriched.append(manifest)

    return ConduitArchiveList(
        conduits=enriched,
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/{conduit_id}",
    response_model=IngressConduitManifest,
    summary="Get conduit manifest",
)
async def capture_conduit_manifest(
    conduit_id: UUID,
    db: AsyncSession = Depends(set_tenant_context),
    _user: dict[str, Any] = Depends(get_current_user),
) -> IngressConduitManifest:
    """Captures specific architectural metadata for an ingress conduit."""
    conduit = await IngressConduitOrchestrator.capture_conduit_manifest(db, conduit_id)
    return IngressConduitManifest.model_validate(conduit)


@router.put(
    "/{conduit_id}/map",
    response_model=ConduitMappingResponse,
    summary="Map conduit to node",
)
async def map_conduit_to_node(
    conduit_id: UUID,
    body: ConduitMappingRequest,
    db: AsyncSession = Depends(set_tenant_context),
    _user: dict[str, Any] = Depends(get_current_user),
) -> ConduitMappingResponse:
    """Maps an ingress conduit to a processing node, enabling architectural signal routing."""
    conduit = await IngressConduitOrchestrator.map_conduit_to_node(
        db=db,
        conduit_id=conduit_id,
        node_sig=body.node_sig,
    )
    await db.commit()
    return ConduitMappingResponse.model_validate(conduit)


@router.patch(
    "/{conduit_id}",
    response_model=IngressConduitManifest,
    summary="Apply structural mutation",
)
async def apply_conduit_mutation(
    conduit_id: UUID,
    body: ConduitMutationRequest,
    db: AsyncSession = Depends(set_tenant_context),
    _user: dict[str, Any] = Depends(get_current_user),
) -> IngressConduitManifest:
    """Applies structural mutations to an established ingress conduit manifest."""
    conduit = await IngressConduitOrchestrator.apply_conduit_mutation(
        db=db,
        conduit_id=conduit_id,
        **body.model_dump(exclude_unset=True),
    )
    await db.commit()
    return IngressConduitManifest.model_validate(conduit)


@router.delete(
    "/{conduit_id}",
    status_code=204,
    response_class=Response,
    summary="Decommission a conduit",
)
async def decommission_conduit(
    conduit_id: UUID,
    db: AsyncSession = Depends(set_tenant_context),
    _user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """Permanently decommissions an ingress conduit and releases substrate resources."""
    await IngressConduitOrchestrator.decommission_conduit(db, conduit_id)
    await db.commit()
    return Response(status_code=204)
