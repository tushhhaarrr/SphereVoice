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
    NodeArchitecturalAdjustment,
    BehavioralProbeSnapshot,
    SyntheticManifestationIntent,
    SyntheticBlueprintResult,
    ArchitecturalAuditResult,
    StructuralViolation,
)
from app.modules.agents.service import ProcessingNexusOrchestrator, BehavioralProbeOrchestrator
from app.modules.auth import User, get_active_user, require_role

agents_router = APIRouter(prefix="/agents", tags=["Agents"])


@agents_router.get("", response_model=NodeClusteredRegistry)
async def list_agents(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    phase: str | None = Query(None),
    class_type: str | None = Query(None, alias="class"),
    tenant_id: str | None = Query(None),
    user: User = Depends(get_active_user),
    db: AsyncSession = Depends(get_db),
    _context: None = Depends(set_tenant_context),
) -> NodeClusteredRegistry:
    """Lists all agents for the current tenant."""
    if not tenant_id or tenant_id in ("undefined", "null", "") or str(tenant_id).startswith("11111111-"):
        domain_sig = user.tenant_id
    else:
        try:
            domain_sig = UUID(tenant_id)
        except ValueError:
            domain_sig = user.tenant_id
            
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


@agents_router.post("", response_model=NodeStateSnapshot, status_code=201)
async def create_agent(
    payload: NodeManifestDefinition,
    request: Request,
    user: User = Depends(get_active_user),
    db: AsyncSession = Depends(get_db),
    _context: None = Depends(set_tenant_context),
) -> NodeStateSnapshot:
    """Creates a new agent."""
    node = await ProcessingNexusOrchestrator.establish_node_manifest(
        db,
        tenant_id=payload.domain_sig,
        label=payload.label,
        node_class=payload.node_class,
        creator_sig=user.id,
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
        db, identity_sig=user.id, nexus_sig=user.tenant_id,
        action="create", resource_type="agent", resource_id=node.id,
        changes={"label": payload.label},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return NodeStateSnapshot.model_validate(node)


@agents_router.get("/{node_sig}", response_model=NodeStateSnapshot)
async def get_agent(
    node_sig: UUID,
    user: User = Depends(get_active_user),
    db: AsyncSession = Depends(get_db),
    _context: None = Depends(set_tenant_context),
) -> NodeStateSnapshot:
    """Retrieves a specific agent."""
    node = await ProcessingNexusOrchestrator.capture_node_instance(db, node_sig)
    return NodeStateSnapshot.model_validate(node)


@agents_router.put("/{node_sig}", response_model=NodeStateSnapshot)
async def update_agent(
    node_sig: UUID,
    payload: NodeArchitecturalAdjustment,
    request: Request,
    user: User = Depends(get_active_user),
    db: AsyncSession = Depends(get_db),
    _context: None = Depends(set_tenant_context),
) -> NodeStateSnapshot:
    """Updates a specific agent."""
    node = await ProcessingNexusOrchestrator.apply_architectural_mutation(
        db, node_sig, **payload.model_dump(exclude_unset=True)
    )
    await EchoLogOrchestrator.log(
        db, identity_sig=user.id, nexus_sig=user.tenant_id,
        action="update", resource_type="agent", resource_id=node.id,
        changes=payload.model_dump(exclude_unset=True, mode="json"),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return NodeStateSnapshot.model_validate(node)


@agents_router.delete("/{node_sig}", status_code=204)
async def delete_agent(
    node_sig: UUID,
    request: Request,
    user: User = Depends(get_active_user),
    db: AsyncSession = Depends(get_db),
    _context: None = Depends(set_tenant_context),
) -> Response:
    """Deletes a specific agent."""
    node = await ProcessingNexusOrchestrator.capture_node_instance(db, node_sig)
    await EchoLogOrchestrator.log(
        db, identity_sig=user.id, nexus_sig=user.tenant_id,
        action="delete", resource_type="agent", resource_id=node_sig,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await ProcessingNexusOrchestrator.decommission_node_instance(db, node_sig)
    return Response(status_code=204)


@agents_router.post("/{node_sig}/activate", response_model=NodeActivationOutcome)
async def activate_agent(
    node_sig: UUID,
    request: Request,
    user: User = Depends(get_active_user),
    db: AsyncSession = Depends(get_db),
    _context: None = Depends(set_tenant_context),
) -> NodeActivationOutcome:
    """Activates a specific agent revision."""
    node = await ProcessingNexusOrchestrator.transition_node_to_active(db, node_sig, author_sig=user.id)
    await EchoLogOrchestrator.log(
        db, identity_sig=user.id, nexus_sig=user.tenant_id,
        action="activate", resource_type="agent", resource_id=node.id,
        changes={"revision": node.revision},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return NodeActivationOutcome(
        sig=node.id, phase=node.node_phase, iteration=node.revision,
        temporal_mark=node.activation_mark
    )


@agents_router.post("/synthetic/blueprint", response_model=SyntheticBlueprintResult)
async def generate_blueprint(
    payload: SyntheticManifestationIntent,
    user: User = Depends(get_active_user),
) -> SyntheticBlueprintResult:
    """Generates an agent blueprint from a description."""
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


@agents_router.post("/{node_sig}/audit-integrity", response_model=ArchitecturalAuditResult)
async def audit_integrity(
    node_sig: UUID,
    payload: dict,
    user: User = Depends(get_active_user),
    db: AsyncSession = Depends(get_db),
    _context: None = Depends(set_tenant_context),
) -> ArchitecturalAuditResult:
    """Audits the architectural integrity of an agent configuration."""
    await ProcessingNexusOrchestrator.capture_node_instance(db, node_sig)
    audit = ProcessingNexusOrchestrator.audit_architectural_integrity(payload.get("nodes", []), payload.get("edges", []))
    return ArchitecturalAuditResult(
        is_integral=audit["is_integral"],
        violations=[StructuralViolation(**v) for v in audit["violations"]],
        alerts=[StructuralViolation(**a) for a in audit["alerts"]],
        block_density=audit["block_count"],
        vector_density=audit["vector_count"]
    )


@agents_router.get("/{node_sig}/behavioral-probes", response_model=list[BehavioralProbeSnapshot])
async def list_probes(
    node_sig: UUID,
    db: AsyncSession = Depends(get_db),
    _context: None = Depends(set_tenant_context),
) -> list[BehavioralProbeSnapshot]:
    """Lists behavioral probes for a specific agent."""
    probes = await BehavioralProbeOrchestrator.catalog_behavioral_probes(db, node_sig)
    return [BehavioralProbeSnapshot.model_validate(p) for p in probes]
