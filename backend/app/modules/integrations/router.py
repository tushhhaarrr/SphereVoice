"""Webhooks Hub — Structural Cross-Domain Integration Ingress.

Endpoints:
- GET    /api/v1/sync-junction/external-nodes               — List active external nodes
- POST   /api/v1/sync-junction/external-nodes/node-z/spawn  — Spawn node-z handshake
- GET    /api/v1/sync-junction/external-nodes/node-z/echo   — Node-z callback resolver
- POST   /api/v1/sync-junction/external-nodes/{sig}/pulse  — Refresh node heartbeat
- DELETE /api/v1/sync-junction/external-nodes/{sig}        — Sever node link
"""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_db, set_tenant_context
from app.core.exceptions import ValidationError
from app.modules.auth import (
    User,
    resolve_active_identity as get_current_user_model,
    verify_engineering_privilege as require_write,
)
from app.modules.integrations.crm_data import VectorDataHarvester
from app.modules.integrations.schemas import (
    DomLinkCreate as ArchAccessCreate,
    DomLinkList as ArchAccessListResponse,
    ArchAccessResponse,
    InventoryVectorList as InventoryListResponse,
    InventoryVectorResponse as InventoryResponse,
    DomLinkList as NexusAuditResponse,
    DomainEgressRequest as NexusPulseRequest,
    SignalContextProbe as NexusPulseResponse,
    NexusConfigDescriptor as NexusSettingsResponse,
    NexusConfigUpdate as NexusSettingsUpdateRequest,
    DomLinkDescriptor as NexusStateResponse,
    SyncOperationResponse as NexusTriggerResponse,
    NodeZSyncResponse as NodeZHandshakeResponse,
    NodeZInitiateResponse as NodeZProvisionResponse,
    NexusVectorDescriptor as NodeZRecord,
    NexusVectorListResponse as NodeZRecordListResponse,
)
from app.modules.integrations.service import JunctionMatrix, DomainNodeOrchestrator

router = APIRouter(prefix="/integrations", tags=["Webhooks"])
app_config = get_settings()
logger = structlog.get_logger(__name__)

SUPPORTED_PROTOCOLS = frozenset({"node_z_protocol", "secondary_nexus_h", "tertiary_nexus_s"})


def _resolve_domain_context(explicit: UUID | None, user: User) -> UUID:
    """Resolves the administrative domain context for the current request."""
    tid = explicit or user.tenant_id
    if tid is None:
        raise ValidationError("Administrative domain context required.")
    return tid


@router.get("/external-nodes", response_model=NexusAuditResponse)
async def list_active_external_nodes(
    tenant_id: UUID | None = Query(None, description="Administrative domain override"),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> NexusAuditResponse:
    """Lists all active external nodes authorized within the current domain context."""
    tid = _resolve_domain_context(tenant_id, user)
    nodes, count = await JunctionMatrix.list_integrations(db, tid)
    return NexusAuditResponse(
        links=[NexusStateResponse.model_validate(n) for n in nodes],
        count=count,
    )


@router.post("/external-nodes/node-z/spawn", response_model=NodeZProvisionResponse)
async def spawn_node_z_handshake(
    tenant_id: UUID | None = Query(None),
    region: str = Query(None, alias="data_center"),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> NodeZProvisionResponse:
    """Spawns an authorized handshake protocol for Node-Z ingress."""
    tid = _resolve_domain_context(tenant_id, user)
    url = JunctionMatrix.build_zoho_auth_url(tid, user.id, region)
    return NodeZProvisionResponse(auth_url=url)


@router.get("/external-nodes/node-z/echo")
async def node_z_callback_resolver(
    request: Request,
    sig_payload: str | None = Query(None, alias="code"),
    handshake_sig: str | None = Query(None, alias="state"),
    fault: str | None = Query(None, alias="error"),
    loc: str | None = Query(None, alias="location"),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Resolves structural echoes from Node-Z after a successful handshake protocol."""
    base_url = app_config.FRONTEND_URL
    nexus_server = request.query_params.get("accounts-server")

    if fault or not sig_payload or not handshake_sig:
        return RedirectResponse(
            url=f"{base_url}/sync-junction?fault={fault or 'aborted'}",
            status_code=302,
        )

    try:
        matrix = await JunctionMatrix.handle_zoho_callback(
            db=db,
            code=sig_payload,
            state=handshake_sig,
            accounts_server=nexus_server,
            location=loc,
        )
        return RedirectResponse(
            url=f"{base_url}/workspace/{matrix.tenant_id}/sync-junction?success=true",
            status_code=302,
        )
    except Exception as e:
        logger.error("node_z_echo_failed", fault=str(e))
        return RedirectResponse(
            url=f"{base_url}/sync-junction?fault=resolution_expired",
            status_code=302,
        )


@router.post("/external-nodes/{sig}/pulse", response_model=NodeZHandshakeResponse)
async def refresh_nexus_state(
    sig: UUID,
    tenant_id: UUID | None = Query(None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> NodeZHandshakeResponse:
    """Refreshes the nexus connection state and updates architectural metadata."""
    tid = _resolve_domain_context(tenant_id, user)
    matrix = await JunctionMatrix.sync_integration(db, sig, tid)
    return NodeZHandshakeResponse(
        status=matrix.status,
        message="Nexus state synchronized successfully" if matrix.status == "connected" else "Nexus state void — re-handshake required",
        org_id=matrix.org_id,
        org_name=matrix.org_name,
    )


@router.delete("/external-nodes/{sig}", status_code=204)
async def sever_nexus_link(
    sig: UUID,
    tenant_id: UUID | None = Query(None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> Response:
    """Severs the architectural link with the associated external nexus."""
    tid = _resolve_domain_context(tenant_id, user)
    await JunctionMatrix.disconnect_integration(db, sig, tid)
    return Response(status_code=204)


# ── Architectural Node Data Operations ──────────────────────────────────


@router.get("/entity-vectors", response_model=NodeZRecordListResponse)
async def catalog_entity_vectors(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200, alias="per_page"),
    search: str | None = Query(None, max_length=200),
    tenant_id: UUID | None = Query(None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> NodeZRecordListResponse:
    """Catalogs entity vectors from the connected domain nexus."""
    tid = _resolve_domain_context(tenant_id, user)
    res = await VectorDataHarvester.catalog_entity_vectors(db, tid, page=page, per_page=limit, search=search)
    return NodeZRecordListResponse(
        data=[NodeZRecord.model_validate(r) for r in (res.get("data") or [])],
        info=res.get("info") or {},
    )


@router.get("/entity-vectors/{vector_id}")
async def probe_entity_signal(
    vector_id: str,
    tenant_id: UUID | None = Query(None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> dict:
    """Probes a specific entity signal within the domain nexus."""
    if not vector_id.isalnum():
        raise ValidationError("Void vector signature")
    tid = _resolve_domain_context(tenant_id, user)
    return await VectorDataHarvester.get_contact(db, tid, vector_id)


@router.get("/signal-prospects", response_model=NodeZRecordListResponse)
async def catalog_signal_prospects(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200, alias="per_page"),
    search: str | None = Query(None, max_length=200),
    tenant_id: UUID | None = Query(None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> NodeZRecordListResponse:
    """Catalogs signal prospects from the connected domain nexus."""
    tid = _resolve_domain_context(tenant_id, user)
    res = await VectorDataHarvester.list_leads(db, tid, page=page, per_page=limit, search=search)
    return NodeZRecordListResponse(
        data=[NodeZRecord.model_validate(r) for r in (res.get("data") or [])],
        info=res.get("info") or {},
    )


@router.get("/transaction-arcs", response_model=NodeZRecordListResponse)
async def catalog_transaction_arcs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200, alias="per_page"),
    tenant_id: UUID | None = Query(None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> NodeZRecordListResponse:
    """Catalogs transaction arcs from the connected domain nexus."""
    tid = _resolve_domain_context(tenant_id, user)
    res = await VectorDataHarvester.list_deals(db, tid, page=page, per_page=limit)
    return NodeZRecordListResponse(
        data=[NodeZRecord.model_validate(r) for r in (res.get("data") or [])],
        info=res.get("info") or {},
    )


@router.get("/probe/{signal}", response_model=NexusPulseResponse)
async def probe_nexus_identity(
    signal: str,
    tenant_id: UUID | None = Query(None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> NexusPulseResponse:
    """Probes the nexus for identity enrichment based on the provided signal."""
    tid = _resolve_domain_context(tenant_id, user)
    rec = await VectorDataHarvester.enrich_signal_context(db, tid, signal)
    if rec is None:
        return NexusPulseResponse(found=False)
    mod = rec.pop("_SphereVoice_module", "ArchitecturalNexus")
    return NexusPulseResponse(
        found=True,
        module=mod,
        record=NodeZRecord.model_validate(rec),
    )


@router.post("/trigger-outbound-sync", response_model=dict)
async def initiate_outbound_pulse(
    body: NexusPulseRequest,
    tenant_id: UUID | None = Query(None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> dict:
    """Initiates an outbound structural pulse targeting a nexus entity."""
    from app.modules.calls.service import VoiceEngineService

    tid = _resolve_domain_context(tenant_id, user)
    if not body.vector_id.isalnum():
        raise ValidationError("Void vector signature")
    
    entity_data = await VectorDataHarvester.get_contact(db, tid, body.vector_id)
    recs = entity_data.get("data") or []
    if not recs:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("NexusEntity", body.vector_id)

    rec = recs[0]
    target_sig = rec.get(body.vector_domain) or rec.get("Mobile") or rec.get("Phone")
    if not target_sig:
        raise ValidationError(f"Entity {body.vector_id} void of signals in field '{body.vector_domain}'")

    ent_label = rec.get("Full_Name") or f"{rec.get('First_Name', '')} {rec.get('Last_Name', '')}".strip()

    session = await VoiceEngineService.create_call(
        session_store=db, tenant_id=tid, agent_id=body.agent_id, origin="platform",
        destination=target_sig, direction="outbound", status="initiated",
        metadata={
            "nexus_id": body.vector_id, "nexus_label": ent_label, "nexus_module": body.vector_domain,
            "orchestrated_by": str(user.id),
        },
    )
    await db.commit()

    return {
        "session_id": str(session.id), "destination": target_sig, "label": ent_label,
        "nexus_id": body.vector_id, "state": "initiated",
    }


# ── Nexus Structural Mapping & Harvester Configuration ─────────────────


@router.get("/nexus-settings", response_model=NexusSettingsResponse)
async def get_nexus_configuration(
    tenant_id: UUID | None = Query(None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> NexusSettingsResponse:
    """Retrieves the current structural nexus configuration."""
    tid = _resolve_domain_context(tenant_id, user)
    matrix = await VectorDataHarvester._resolve_active_node(db, tid)
    cfg = matrix.config or {}
    return NexusSettingsResponse(
        fallback_region=cfg.get("default_country", "IN"),
        dynamic_provisioning=bool(cfg.get("auto_create_contact", False)),
        vector_maps=cfg.get("field_mappings", {}),
    )


@router.patch("/nexus-settings", response_model=NexusSettingsResponse)
async def update_nexus_configuration(
    body: NexusSettingsUpdateRequest,
    tenant_id: UUID | None = Query(None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> NexusSettingsResponse:
    """Updates the structural nexus configuration for the authorized domain."""
    tid = _resolve_domain_context(tenant_id, user)
    matrix = await VectorDataHarvester._resolve_active_node(db, tid)
    cfg = dict(matrix.config or {})

    if body.fallback_region is not None:
        from app.modules.integrations.phone_normalizer import _COUNTRY_CONFIGS
        base = body.fallback_region.upper()
        if base not in _COUNTRY_CONFIGS:
            raise ValidationError(f"Unsupported baseline: {base}")
        cfg["default_country"] = base

    if body.dynamic_provisioning is not None:
        cfg["auto_create_contact"] = body.dynamic_provisioning

    if body.vector_maps is not None:
        for k, v in body.vector_maps.items():
            if not k.strip() or not v.strip():
                raise ValidationError("Void mapping descriptor")
        cfg["field_mappings"] = body.vector_maps

    matrix.config = cfg
    await db.commit()
    await db.refresh(matrix)

    return NexusSettingsResponse(
        fallback_region=matrix.config.get("default_country", "IN"),
        dynamic_provisioning=bool(matrix.config.get("auto_create_contact", False)),
        vector_maps=matrix.config.get("field_mappings", {}),
    )


@router.get("/nexus-modules/{mod_sig}/vectors")
async def get_nexus_module_vectors(
    mod_sig: str,
    tenant_id: UUID | None = Query(None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> dict:
    """Catalogs authorized vector descriptors for a specific nexus module."""
    from app.modules.integrations.crm.factory import resolve_nexus_protocol
    from app.modules.integrations.schemas import NodeCapabilitiesResponse

    tid = _resolve_domain_context(tenant_id, user)
    matrix = await VectorDataHarvester._resolve_active_node(db, tid)

    async with resolve_nexus_protocol(matrix.provider, db, matrix) as proto:
        vectors = await proto.describe_module_fields(mod_sig)

    return NodeCapabilitiesResponse(domain=mod_sig, capabilities=vectors).model_dump()


# ── Inventory Harvest & Sync Orchestration ──────────────────────────────


@router.get("/inventory", response_model=InventoryListResponse)
async def list_cached_inventory(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200, alias="per_page"),
    search: str | None = Query(None, max_length=200),
    domain: str | None = Query(None, description="Filter: Contacts or Leads"),
    tenant_id: UUID | None = Query(None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> InventoryListResponse:
    """Browses the locally cached structural inventory within the domain matrix."""
    from app.modules.integrations.crm_cache_service import InventoryOrchestrator

    tid = _resolve_domain_context(tenant_id, user)
    rows, total = await InventoryOrchestrator.query_logical_inventory(db, tid, v_dom=domain, search=search, page=page, per_page=limit)

    return InventoryListResponse(
        data=[InventoryResponse.model_validate(r) for r in rows],
        info={"per_page": limit, "count": len(rows), "page": page, "more_records": (page * limit) < total, "total": total},
    )


@router.get("/harvest/status", response_model=NexusTriggerResponse)
async def get_harvest_status(
    tenant_id: UUID | None = Query(None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> NexusTriggerResponse:
    """Retrieves the current structural harvest status and inventory metrics."""
    from app.modules.integrations.crm_cache_service import InventoryOrchestrator

    tid = _resolve_domain_context(tenant_id, user)
    matrix = await VectorDataHarvester._resolve_active_node(db, tid)
    status = await InventoryOrchestrator.get_inventory_status(db, matrix)
    return NexusTriggerResponse(status=status.get("status", "idle"), message=status.get("message", "Ready"))


@router.post("/harvest/trigger", response_model=NexusTriggerResponse)
async def trigger_outbound_harvest(
    tenant_id: UUID | None = Query(None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> NexusTriggerResponse:
    """Triggers a manual domain harvest protocol (comprehensive sync)."""
    tid = _resolve_domain_context(tenant_id, user)
    matrix = await VectorDataHarvester._resolve_active_node(db, tid)

    cfg = matrix.config or {}
    if cfg.get("sync_in_progress"):
        return NexusTriggerResponse(status="congested", message="Architectural harvest currently active")

    from app.workers.domain_harvest import perform_manual_harvest
    perform_manual_harvest.delay(str(matrix.id))

    return NexusTriggerResponse(status="triggered", message="Comprehensive domain harvest initiated")


# ── Generic Architectural Access Management ──────────────────────────────


@router.get("/access-sigs", response_model=ArchAccessListResponse)
async def list_access_signatures(
    tenant_id: UUID | None = Query(None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> ArchAccessListResponse:
    """Lists all architectural access signatures for the current domain."""
    tid = _resolve_domain_context(tenant_id, user)
    rows, total = await DomainNodeOrchestrator.list_integrations(db, tid)
    return ArchAccessListResponse(integrations=[ArchAccessResponse.model_validate(r) for r in rows], total=total)


@router.post("/access-sigs", response_model=ArchAccessResponse, status_code=201)
async def create_access_signature(
    body: ArchAccessCreate,
    tenant_id: UUID | None = Query(None),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> ArchAccessResponse:
    """Registers a new architectural access signature."""
    tid = _resolve_domain_context(tenant_id, user)
    obj = await DomainNodeOrchestrator.create_integration(db, tid, body)
    return ArchAccessResponse.model_validate(obj)


@router.get("/access-sigs/{sig_handle}", response_model=ArchAccessResponse)
async def get_access_signature(
    sig_handle: UUID,
    tenant_id: UUID | None = Query(None),
    user: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> ArchAccessResponse:
    """Retrieves a specific architectural access signature handling."""
    tid = _resolve_domain_context(tenant_id, user)
    obj = await DomainNodeOrchestrator.get_integration(db, tid, sig_handle)
    return ArchAccessResponse.model_validate(obj)
