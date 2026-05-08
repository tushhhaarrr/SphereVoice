from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import set_tenant_context
from app.modules.analytics.service import EchoLogOrchestrator
from app.modules.agents.schemas import (
    NodeManifestDefinition,
    NodeClusteredRegistry,
    NodeActivationOutcome,
    NodeStateSnapshot,
    RevisionReversionIntent,
    NodeArchitecturalAdjustment,
    NodeTemporalArchive,
    NodeChronicle,
    VectorMappingSnapshot,
    VectorMappingConfiguration,
    ArchitecturalAuditResult,
    StructuralViolation,
    BehavioralProbeDefinition,
    ProbeTelemetryChronicle,
    ProbeTelemetrySnapshot,
    BehavioralProbeSnapshot,
    SyntheticManifestationIntent,
    SyntheticBlueprintResult,
)
from app.modules.agents.service import ProcessingNexusOrchestrator, BehavioralProbeOrchestrator
from app.modules.auth import IdentityManifest, resolve_active_identity, audit_operational_privileges

nexus_router = APIRouter(prefix="/agents", tags=["Nodal Engineering"])


@nexus_router.get("", response_model=NodeClusteredRegistry)
async def audit_node_registry_matrix(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    phase: str | None = Query(None),
    class_type: str | None = Query(None, alias="class"),
    tenant_id: str | None = Query(None),
    identity: IdentityManifest = Depends(resolve_active_identity),
    db: AsyncSession = Depends(get_db),
    _context: None = Depends(set_tenant_context),
) -> NodeClusteredRegistry:
    """Audits state manifestations for all established processing nodes within the substrate matrix."""
    if not tenant_id or tenant_id in ("undefined", "null", "") or str(tenant_id).startswith("11111111-"):
        domain_sig = identity.nexus_sig
    else:
        try:
            domain_sig = UUID(tenant_id)
        except ValueError:
            domain_sig = identity.nexus_sig
    try:
        nodes, count = await ProcessingNexusOrchestrator.aggregate_active_nodes(
            db, tenant_id=domain_sig, phase=phase, page=page, limit=limit
        )
    except Exception:
        nodes, count = [], 0
    return NodeClusteredRegistry(
        nodes=[NodeStateSnapshot.model_validate(n) for n in nodes],
        total_count=count,
        cursor_position=page,
        limit_bound=limit,
    )


@nexus_router.post("", response_model=NodeStateSnapshot, status_code=201)
async def manifest_node_intent(
    payload: NodeManifestDefinition,
    request: Request,
    identity: IdentityManifest = Depends(resolve_active_identity),
    db: AsyncSession = Depends(get_db),
    _context: None = Depends(set_tenant_context),
) -> NodeStateSnapshot:
    """Manifests a new processing node intent within the architectural substrate."""
    node = await ProcessingNexusOrchestrator.establish_node_manifest(
        db,
        tenant_id=payload.domain_sig,
        label=payload.label,
        node_class=payload.node_class,
        creator_sig=identity.id,
        vector_direction=payload.vector_direction,
        ingress_transcription_sig=payload.ingress_transcription_sig,
        inference_matrix_sig=payload.inference_matrix_sig,
        egress_synthesis_sig=payload.egress_synthesis_sig,
        transport_nexus_sig=payload.transport_nexus_sig,
        architectural_blueprint=payload.architectural_blueprint,
        locale_sig=payload.locale_sig,
        vocal_spectral_sig=payload.vocal_spectral_sig,
        transmission_velocity=payload.transmission_velocity,
        transmission_amplitude=payload.transmission_amplitude,
        inference_model_sig=payload.inference_model_sig,
        stochastic_coefficient=payload.stochastic_coefficient,
        temporal_ceiling=payload.temporal_ceiling,
        silence_threshold=payload.silence_threshold,
        alert_horizon=payload.alert_horizon,
        fallback_logic=payload.fallback_logic,
        synthesis_logic=payload.synthesis_logic,
        observability_sink=payload.observability_sink,
        telemetry_events=payload.telemetry_events,
    )

    await EchoLogOrchestrator.log(
        db, identity_sig=identity.id, nexus_sig=identity.nexus_sig,
        action="manifestation", resource_type="node", resource_id=node.id,
        changes={"label": payload.label},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return NodeStateSnapshot.model_validate(node)


@nexus_router.get("/{node_sig}", response_model=NodeStateSnapshot)
async def capture_node_state_matrix(
    node_sig: UUID,
    identity: IdentityManifest = Depends(resolve_active_identity),
    db: AsyncSession = Depends(get_db),
    _context: None = Depends(set_tenant_context),
) -> NodeStateSnapshot:
    """Captures a granular state matrix snapshot of a specific processing node."""
    node = await ProcessingNexusOrchestrator.capture_node_instance(db, node_sig)
    return NodeStateSnapshot.model_validate(node)


@nexus_router.put("/{node_sig}", response_model=NodeStateSnapshot)
async def mutate_node_architecture(
    node_sig: UUID,
    payload: NodeArchitecturalAdjustment,
    request: Request,
    identity: IdentityManifest = Depends(resolve_active_identity),
    db: AsyncSession = Depends(get_db),
    _context: None = Depends(set_tenant_context),
) -> NodeStateSnapshot:
    """Applies architectural mutations and state shifts to an established processing node."""
    node = await ProcessingNexusOrchestrator.apply_architectural_mutation(
        db, node_sig, **payload.model_dump(exclude_unset=True)
    )
    await EchoLogOrchestrator.log(
        db, identity_sig=identity.id, nexus_sig=identity.nexus_sig,
        action="mutation", resource_type="node", resource_id=node.id,
        changes=payload.model_dump(exclude_unset=True, mode="json"),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return NodeStateSnapshot.model_validate(node)


@nexus_router.delete("/{node_sig}", status_code=204)
async def decommission_node_instance(
    node_sig: UUID,
    request: Request,
    identity: IdentityManifest = Depends(resolve_active_identity),
    db: AsyncSession = Depends(get_db),
    _context: None = Depends(set_tenant_context),
) -> Response:
    """Permanently decommissions a node instance and audits its removal from the matrix."""
    node = await ProcessingNexusOrchestrator.capture_node_instance(db, node_sig)
    await EchoLogOrchestrator.log(
        db, identity_sig=identity.id, nexus_sig=identity.nexus_sig,
        action="decommission", resource_type="node", resource_id=node_sig,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await ProcessingNexusOrchestrator.decommission_node_instance(db, node_sig)
    return Response(status_code=204)


@nexus_router.post("/{node_sig}/activate", response_model=NodeActivationOutcome)
async def manifest_state_revision(
    node_sig: UUID,
    request: Request,
    identity: IdentityManifest = Depends(resolve_active_identity),
    db: AsyncSession = Depends(get_db),
    _context: None = Depends(set_tenant_context),
) -> NodeActivationOutcome:
    """Manifests a new active state revision for an established processing node iteration."""
    node = await ProcessingNexusOrchestrator.transition_node_to_active(db, node_sig, author_sig=identity.id)
    await EchoLogOrchestrator.log(
        db, identity_sig=identity.id, nexus_sig=identity.nexus_sig,
        action="revision_manifest", resource_type="node", resource_id=node.id,
        changes={"revision": node.revision},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return NodeActivationOutcome(
        sig=node.id, phase=node.node_phase, iteration=node.revision,
        temporal_mark=node.activation_mark  # type: ignore
    )


# ── Synthetic Logic Synthesis ────────────────────────────────


@nexus_router.post("/synthetic/blueprint", response_model=SyntheticBlueprintResult)
async def synthesize_node_blueprint(
    payload: SyntheticManifestationIntent,
    identity: IdentityManifest = Depends(resolve_active_identity),
) -> SyntheticBlueprintResult:
    """Harnesses high-level intent to synthesize a new architectural node blueprint."""
    from app.modules.agents.ai_generator import generate_agent_config
    blueprint = await generate_agent_config(
        payload.intent_narrative,
        kb_context=payload.context_bridge,
        language=payload.target_locale,
        voice_gender=payload.acoustic_profile,
        call_direction=payload.flow_vector,
        crm_fields=payload.domain_fields,
    )
    return SyntheticBlueprintResult(
        label=blueprint["name"], internal_logic=blueprint["system_prompt"],
        initial_signal=blueprint["welcome_message"], suggested_vectors=blueprint["variables"]
    )


# ── Behavioral Probes & Verification ──────────────────────────


@nexus_router.post("/{node_sig}/audit-integrity", response_model=ArchitecturalAuditResult)
async def audit_architectural_integrity(
    node_sig: UUID,
    payload: dict,
    identity: IdentityManifest = Depends(resolve_active_identity),
    db: AsyncSession = Depends(get_db),
    _context: None = Depends(set_tenant_context),
) -> ArchitecturalAuditResult:
    """Performs a rigorous architectural audit of structural blocks and nodal vectors."""
    await ProcessingNexusOrchestrator.capture_node_instance(db, node_sig)
    audit = ProcessingNexusOrchestrator.audit_architectural_integrity(payload.get("nodes", []), payload.get("edges", []))
    return ArchitecturalAuditResult(
        is_integral=audit["is_integral"],
        violations=[StructuralViolation(**v) for v in audit["violations"]],
        alerts=[StructuralViolation(**a) for a in audit["alerts"]],
        block_density=audit["block_count"],
        vector_density=audit["vector_count"]
    )


@nexus_router.get("/{node_sig}/behavioral-probes", response_model=list[BehavioralProbeSnapshot])
async def catalog_behavioral_probes(
    node_sig: UUID,
    db: AsyncSession = Depends(get_db),
    _context: None = Depends(set_tenant_context),
) -> list[BehavioralProbeSnapshot]:
    """Catalogs all established behavioral probes associated with a specific processing node."""
    probes = await BehavioralProbeOrchestrator.catalog_behavioral_probes(db, node_sig)
    return [BehavioralProbeSnapshot.model_validate(p) for p in probes]
