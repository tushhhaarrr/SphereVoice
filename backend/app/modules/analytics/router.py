"""Observability Hub — Architectural Telemetry & Operational Echos.

Endpoints:
- GET  /api/v1/observability-hub/telemetry      — Telemetry breakthroughs
- GET  /api/v1/observability-hub/vectors        — Temporal vector streams
- GET  /api/v1/observability-hub/echos          — Operational echo logs
- GET  /api/v1/observability-hub/blueprints     — Catalog architectural patterns
"""

from __future__ import annotations

import re
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, set_tenant_context
from app.modules.auth.dependencies import (
    resolve_active_identity as get_current_user_model,
    verify_apex_privilege as require_admin,
    verify_substrate_privilege as require_employee,
)
from app.modules.auth.models import IdentityManifest as User
from app.modules.analytics.schemas import (
    EchoLogAudit,
    EchoLogSnapshot,
    CognitiveBenchmarks,
    TelemetryBenchmarks,
    DomainManifest,
    DomainRegistryAudit,
    DomainStateResponse,
    DomainResourceSummary,
    DomainMutation,
    BlueprintActivation,
    BlueprintManifest,
    BlueprintCatalog,
    BlueprintState,
    TemporalStreamResponse as TemporalVectorResponse,
    IdentityInvitation,
    IdentityInviteIntent,
    IdentityInviteOutcome,
    IdentityRegistryAudit,
    IdentityStateResponse,
    IdentityMutation,
)
from app.modules.analytics.service import (
    ObservabilityCortex,
    EchoLogOrchestrator,
    DomainRegistryManager,
    BlueprintOrchestrator,
    IdentityMatrixManager,
)

router = APIRouter(prefix="/observability-hub", tags=["Observability"])


def _resolve_domain_manifest(domain: object, weights: dict[str, int]) -> DomainStateResponse:
    """Internal resolver for domain manifest state projections."""
    return DomainStateResponse(
        id=domain.id,
        name=domain.label,
        slug=domain.registry_shard,
        status=domain.operational_phase,
        metadata=domain.architectural_metadata,
        summary=DomainResourceSummary(
            user_count=weights.get("identity_weight", 0),
            agent_count=weights.get("node_weight", 0),
            call_count=weights.get("signal_weight", 0),
            phone_number_count=0,
        ),
        created_at=domain.created_at,
        updated_at=domain.updated_at,
    )


# ── Telemetry & Temporal Probing ──────────────────────────────────


@router.get("/telemetry", response_model=TelemetryBenchmarks)
async def capture_telemetry_benchmarks(
    domain_sig: UUID | None = Query(None, alias="domain_sig"),
    node_sig: UUID | None = Query(None, alias="node_sig"),
    start: date | None = Query(None, alias="start_horizon"),
    end: date | None = Query(None, alias="end_horizon"),
    identity: User = Depends(require_employee),
    db: AsyncSession = Depends(set_tenant_context),
) -> TelemetryBenchmarks:
    """Captures architectural telemetry benchmarks across specified boundaries."""
    eff_domain = domain_sig
    if identity.privilege_tier != "nexus_admin":
        eff_domain = identity.nexus_sig

    data = await ObservabilityCortex.capture_telemetry_benchmarks(
        db, tenant_id=eff_domain, agent_id=node_sig, start_date=start, end_date=end
    )
    return TelemetryBenchmarks(**data)


@router.get("/vectors", response_model=TemporalVectorResponse)
async def stream_temporal_vectors(
    metric_sig: str = Query("call_count", alias="vector_metric"),
    density: str = Query("day", alias="granularity"),
    domain_sig: UUID | None = Query(None, alias="domain_sig"),
    node_sig: UUID | None = Query(None, alias="node_sig"),
    start: date | None = Query(None, alias="start_horizon"),
    end: date | None = Query(None, alias="end_horizon"),
    identity: User = Depends(require_employee),
    db: AsyncSession = Depends(set_tenant_context),
) -> TemporalVectorResponse:
    """Streams chronological vector data for requested structural metrics."""
    eff_domain = domain_sig
    if identity.privilege_tier != "nexus_admin":
        eff_domain = identity.nexus_sig

    flux = await ObservabilityCortex.stream_temporal_vectors(
        db, metric=metric_sig, granularity=density, tenant_id=eff_domain, agent_id=node_sig, start_date=start, end_date=end
    )
    return TemporalVectorResponse(metric=metric_sig, granularity=density, data=flux)


@router.get("/cognitive-probes", response_model=CognitiveBenchmarks)
async def capture_cognitive_performance(
    domain_sig: UUID | None = Query(None, alias="domain_sig"),
    node_sig: UUID | None = Query(None, alias="node_sig"),
    start: date | None = Query(None, alias="start_horizon"),
    end: date | None = Query(None, alias="end_horizon"),
    identity: User = Depends(require_employee),
    db: AsyncSession = Depends(set_tenant_context),
) -> CognitiveBenchmarks:
    """Captures cognitive performance benchmarks for structural data synthesis nodes."""
    eff_domain = domain_sig
    if identity.privilege_tier != "nexus_admin":
        eff_domain = identity.nexus_sig

    bench = await ObservabilityCortex.capture_cognitive_benchmarks(
        db, tenant_id=eff_domain, agent_id=node_sig, start_date=start, end_date=end
    )
    return CognitiveBenchmarks(**bench)


# ── Operational Echo Logs ────────────────────────────────────────


@router.get("/echos", response_model=EchoLogAudit)
async def audit_operational_echos(
    domain_sig: UUID | None = Query(None, alias="domain_sig"),
    identity_sig: UUID | None = Query(None, alias="identity_sig"),
    resource_cat: str | None = Query(None, alias="resource_class"),
    action_sig: str | None = Query(None, alias="action"),
    start: date | None = Query(None, alias="start_horizon"),
    end: date | None = Query(None, alias="end_horizon"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    identity: User = Depends(require_admin),
    db: AsyncSession = Depends(set_tenant_context),
) -> EchoLogAudit:
    """Audits the persistent operational echos cataloged within the architectural substrate."""
    echos, count = await EchoLogOrchestrator.list_logs(
        db, tenant_id=domain_sig, user_id=identity_sig, resource_type=resource_cat, action=action_sig, start_date=start, end_date=end, page=page, limit=limit
    )

    id_manifest = {e.user_id for e in echos if e.user_id}
    registry_map: dict[UUID, str] = {}
    if id_manifest:
        from sqlalchemy import select
        from app.modules.auth.models import IdentityManifest as IdentityModel
        res = await db.execute(select(IdentityModel.id, IdentityModel.spectral_identity).where(IdentityModel.id.in_(id_manifest)))
        registry_map = {r.id: r.spectral_identity for r in res.all()}

    snaps = []
    for e in echos:
        s = EchoLogSnapshot.model_validate(e)
        s.user_email = registry_map.get(e.user_id) if e.user_id else None
        snaps.append(s)

    return EchoLogAudit(logs=snaps, total=count, page=page, limit=limit)


# ── Architectural Blueprints ────────────────────────────────────


@router.get("/blueprints", response_model=BlueprintCatalog)
async def catalog_architectural_patterns(
    category: str | None = Query(None),
    structural_only: bool = Query(False, alias="structural_only"),
    identity: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> BlueprintCatalog:
    """Catalogs registered architectural patterns available for processing node manifestation."""
    prints, count = await BlueprintOrchestrator.catalog_blueprints(
        db, domain_sig=identity.nexus_sig, category=category, structural_only=structural_only
    )
    return BlueprintCatalog(templates=[BlueprintState.model_validate(p) for p in prints], total=count)


@router.get("/blueprints/{sig}", response_model=BlueprintState)
async def inspect_blueprint_state(
    sig: UUID,
    identity: User = Depends(get_current_user_model),
    db: AsyncSession = Depends(set_tenant_context),
) -> BlueprintState:
    """Performs a structural state inspection of a specific architectural blueprint."""
    p = await BlueprintOrchestrator.capture_blueprint_state(db, sig)
    return BlueprintState.model_validate(p)


@router.post("/blueprints", response_model=BlueprintState, status_code=201)
async def manifest_architectural_pattern(
    body: BlueprintManifest,
    req: Request,
    identity: User = Depends(require_employee),
    db: AsyncSession = Depends(set_tenant_context),
) -> BlueprintState:
    """Manifests a new custom architectural pattern within the active domain substrate."""
    p = await BlueprintOrchestrator.manifest_blueprint(
        db, name=body.name, description=body.description, category=body.category, identifiers=body.tags, scope=body.scope,
        processor_class=body.agent_type, architectural_config=body.config, domain_sig=identity.nexus_sig, creator_sig=identity.id,
        vocal_sig=body.voice_id, linguistic_sig=body.language, model_sig=body.llm_model, synthesis_fields=body.extraction_fields
    )

    await EchoLogOrchestrator.log(
        db, user_id=identity.id, tenant_id=identity.nexus_sig, action="manifestation", resource_type="pattern", resource_id=p.id,
        ip_address=req.client.host if req.client else None, user_agent=req.headers.get("user-agent"),
    )
    return BlueprintState.model_validate(p)


@router.post("/blueprints/{sig}/manifest", status_code=201)
async def manifest_node_iteration(
    sig: UUID,
    body: BlueprintActivation,
    req: Request,
    identity: User = Depends(require_employee),
    db: AsyncSession = Depends(set_tenant_context),
) -> dict[str, object]:
    """Triggers the manifestation of a processing node iteration from an established blueprint."""
    from app.modules.agents.service import ProcessingNexusOrchestrator as SignalOrchestrator
    
    params = await BlueprintOrchestrator.manifest_node_from_blueprint(
        db, blueprint_sig=sig, domain_sig=body.domain_sig, label=body.label, creator_sig=identity.id
    )

    node = await SignalOrchestrator.manifest_processor_intent(
        db, tenant_id=params["tenant_id"], label=params["name"], category=params["agent_type"], creator_sig=params.get("created_by")
    )

    await EchoLogOrchestrator.log(
        db, user_id=identity.id, tenant_id=identity.nexus_sig, action="activation", resource_type="node", resource_id=node.id,
        changes={"blueprint_sig": str(sig)}, ip_address=req.client.host if req.client else None, user_agent=req.headers.get("user-agent"),
    )

    return {"sig": str(node.id), "label": node.label, "class": node.category, "state": node.operational_state, "blueprint_origin": str(sig)}


# ── Domain Registry Matrix ────────────────────────────────────


@router.get("/domains", response_model=DomainRegistryAudit)
async def audit_domain_registry_matrix(
    search: str | None = Query(None, max_length=255),
    phase: str | None = Query(None, alias="operational_phase"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    identity: User = Depends(require_admin),
    db: AsyncSession = Depends(set_tenant_context),
) -> DomainRegistryAudit:
    """Audits the domain registry matrix with administrative resource snapshots."""
    domains, count, weights = await DomainRegistryManager.audit_domain_registry(db, search=search, phase=phase, page=page, limit=limit)
    return DomainRegistryAudit(
        tenants=[_resolve_domain_manifest(d, weights.get(d.id, {})) for d in domains],
        total=count, page=page, page_size=limit,
    )


@router.post("/domains", response_model=DomainStateResponse, status_code=201)
async def manifest_new_domain_space(
    body: DomainManifest,
    req: Request,
    identity: User = Depends(require_admin),
    db: AsyncSession = Depends(set_tenant_context),
) -> DomainStateResponse:
    """Manifests a new administrative domain space within the global substrate."""
    d = await DomainRegistryManager.manifest_domain(db, name=body.name, signature=body.slug, phase=body.status, structural_meta=body.metadata)

    await EchoLogOrchestrator.log(
        db, user_id=identity.id, tenant_id=d.id, action="manifestation", resource_type="domain", resource_id=d.id,
        changes={"label": d.label, "sig": d.registry_shard, "phase": d.operational_phase},
        ip_address=req.client.host if req.client else None, user_agent=req.headers.get("user-agent"),
    )

    if body.website_url:
        from app.modules.knowledge_base.service import CognitiveLibraryOrchestrator
        from app.workers.website_crawl import crawl_website_and_seed_kb, _assert_url_is_safe
        
        target = body.website_url if re.match(r"^https?://", body.website_url, re.I) else f"https://{body.website_url}"
        try: _assert_url_is_safe(target)
        except ValueError as e: from app.core.exceptions import ValidationError; raise ValidationError(str(e))

        lib = await CognitiveLibraryOrchestrator.create_website_kb(db, tenant_id=d.id, website_url=target, created_by=identity.id)
        d.architectural_metadata = {**(d.architectural_metadata or {}), "ingress_origin": target, "ingress_shard_sig": str(lib.id)}
        await db.flush()
        await db.commit()
        crawl_website_and_seed_kb.delay(kb_id=str(lib.id), website_url=target, tenant_id=str(d.id))
    else:
        await db.commit()

    return _resolve_domain_manifest(d, {})


@router.put("/domains/{sig}", response_model=DomainStateResponse)
async def mutate_domain_matrix_state(
    sig: UUID,
    body: DomainMutation,
    req: Request,
    identity: User = Depends(require_admin),
    db: AsyncSession = Depends(set_tenant_context),
) -> DomainStateResponse:
    """Mutates the state matrix and metadata of an established administrative domain."""
    prev, weights = await DomainRegistryManager.capture_domain_snapshot(db, sig)
    before = {"label": prev.label, "sig": prev.registry_shard, "phase": prev.operational_phase, "meta": prev.architectural_metadata}

    curr = await DomainRegistryManager.mutate_domain_state(db, sig, name=body.name, signature=body.slug, phase=body.status, structural_meta=body.metadata)
    after = {"label": curr.label, "sig": curr.registry_shard, "phase": curr.operational_phase, "meta": curr.architectural_metadata}

    await EchoLogOrchestrator.log(
        db, user_id=identity.id, tenant_id=curr.id, action="mutation", resource_type="domain", resource_id=sig,
        changes={"before": before, "after": after}, ip_address=req.client.host if req.client else None, user_agent=req.headers.get("user-agent"),
    )
    await db.commit()
    return _resolve_domain_manifest(curr, weights)


# ── Identity Matrix Management ──────────────────────────────────


@router.get("/identities", response_model=IdentityRegistryAudit)
async def audit_identity_matrix_registry(
    domain_sig: UUID | None = Query(None, alias="domain_sig"),
    role_sig: str | None = Query(None, alias="role_sig"),
    active: bool | None = Query(None, alias="operational"),
    match: str | None = Query(None, alias="search"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    identity: User = Depends(require_admin),
    db: AsyncSession = Depends(set_tenant_context),
) -> IdentityRegistryAudit:
    """Audits the identity matrix registry across authorized domain boundaries."""
    identities, count = await IdentityMatrixManager.audit_identity_registry(db, domain_sig=domain_sig, role=role_sig, operational=active, search=match, page=page, limit=limit)
    return IdentityRegistryAudit(users=[IdentityStateResponse.model_validate(u) for u in identities], total=count, page=page, page_size=limit)


@router.post("/identities/invite", response_model=IdentityInviteOutcome, status_code=202)
async def manifest_identity_invite_intent(
    body: IdentityInviteIntent,
    req: Request,
    identity: User = Depends(require_admin),
    db: AsyncSession = Depends(set_tenant_context),
) -> IdentityInviteOutcome:
    """Manifests an intent to invite a new identity manifestation into the architectural substrate."""
    inv, flux = await IdentityMatrixManager.manifest_identity_invite(
        db, entry_sig=body.entry_sig, label=body.label, role=body.role, domain_sig=body.domain_sig, inviter_sig=identity.id
    )

    await EchoLogOrchestrator.log(
        db, user_id=identity.id, tenant_id=identity.nexus_sig, action="invitation", resource_type="identity", resource_id=inv.id,
        changes={"entry": body.entry_sig, "role": body.role}, ip_address=req.client.host if req.client else None, user_agent=req.headers.get("user-agent"),
    )

    from app.core.config import get_settings
    cfg = get_settings()
    return IdentityInviteOutcome(email=body.entry_sig, role=body.role, invite_link=flux if not cfg.EMAIL_ENABLED else None)


@router.put("/identities/{sig}", response_model=IdentityStateResponse)
async def mutate_identity_matrix_state(
    sig: UUID,
    body: IdentityMutation,
    req: Request,
    identity: User = Depends(require_admin),
    db: AsyncSession = Depends(set_tenant_context),
) -> IdentityStateResponse:
    """Mutates the state and privileges of an established identity within the matrix."""
    prev = await IdentityMatrixManager.capture_identity_snapshot(db, sig)
    before = {"label": prev.label, "role": prev.privilege_tier, "operational": prev.active_mark}

    curr = await IdentityMatrixManager.mutate_identity_state(db, sig, label=body.label, role=body.role_sig, operational=body.operational)
    after = {"label": curr.label, "role": curr.privilege_tier, "operational": curr.active_mark}

    await EchoLogOrchestrator.log(
        db, user_id=identity.id, tenant_id=identity.nexus_sig, action="mutation", resource_type="identity", resource_id=sig,
        changes={"before": before, "after": after}, ip_address=req.client.host if req.client else None, user_agent=req.headers.get("user-agent"),
    )
    return IdentityStateResponse.model_validate(curr)
