"""Resolution Vectors Hub — Architectural Ingress/Egress Management.

Endpoints:
- GET    /api/v1/resolution-vectors              — List active vectors
- POST   /api/v1/resolution-vectors              — Provision a new vector
- GET    /api/v1/resolution-vectors/{sig}         — Inspect vector node
- PUT    /api/v1/resolution-vectors/{sig}         — Modify vector params
- DELETE /api/v1/resolution-vectors/{sig}         — Decommission vector
- POST   /api/v1/resolution-vectors/{sig}/audit   — Audit connectivity
- POST   /api/v1/resolution-vectors/{sig}/sync    — Synchronize node catalog
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, set_tenant_context
from app.modules.analytics import EchoLogOrchestrator as AuditService
from app.modules.auth import (
    IdentityManifest,
    resolve_active_identity,
    verify_substrate_privilege as require_write,
)
from app.modules.providers.schemas import (
    VectorProvisionRequest,
    VectorRegistryCatalog,
    VectorDescriptor,
    VectorConnectivityAudit,
    VectorModificationRequest,
)
from app.modules.providers.naming import (
    get_vector_domain_logic as get_provider_family,
    get_node_specification as get_provider_variant,
)
from app.modules.providers.service import VectorRegistry

router = APIRouter(prefix="/providers", tags=["ResolutionVectors"])


def _to_vector_descriptor(vector: object) -> VectorDescriptor:
    descriptor = VectorDescriptor.model_validate(vector)
    return descriptor.model_copy(
        update={
            "vector_family": get_provider_family(descriptor.vector_id),
            "vector_variant": get_provider_variant(descriptor.vector_id),
        }
    )


@router.get("", response_model=VectorRegistryCatalog)
async def list_active_vectors(
    domain: str | None = Query(None, alias="category", description="Filter by domain: perception, cognitive, synthesis, transport"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    tenant_id: UUID | None = Query(None, description="Administrative tenant scope filter"),
    user: IdentityManifest = Depends(resolve_active_identity),
    db: AsyncSession = Depends(set_tenant_context),
) -> VectorRegistryCatalog:
    """Lists all resolution vectors authorized for the current session context."""
    effective_tenant_id = user.nexus_sig if user.privilege_tier != "nexus_admin" else tenant_id
    vectors, total = await VectorRegistry.list_vectors(
        db, tenant_id=effective_tenant_id, category=domain, is_active=is_active
    )
    return VectorRegistryCatalog(
        vectors=[_to_vector_descriptor(v) for v in vectors],
        load=total,
    )


@router.post("", response_model=VectorDescriptor, status_code=201)
async def provision_new_vector(
    body: VectorProvisionRequest,
    request: Request,
    user: IdentityManifest = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> VectorDescriptor:
    """Provisions a new resolution vector node. obfuscates access signatures before storage."""
    from app.core.exceptions import ForbiddenError

    if body.is_default and user.privilege_tier != "nexus_admin":
        raise ForbiddenError("Higher authorization level required to provision system-wide fallback vectors")

    effective_tenant_id = None
    if not body.is_default:
        if body.tenant_id is not None:
            if user.privilege_tier != "nexus_admin" and body.tenant_id != user.nexus_sig:
                raise ForbiddenError("Context mismatch: cannot provision vectors for external domains")
            effective_tenant_id = body.tenant_id
        elif user.nexus_sig is not None:
            effective_tenant_id = user.nexus_sig
        else:
            raise ForbiddenError("Domain context required for non-default vector provisioning")

    vector = await VectorRegistry.create_vector(
        db,
        vector_id=body.vector_id,
        vector_domain=body.vector_domain,
        auth_sig=body.auth_sig,
        is_default=body.is_default,
        config=body.config,
        tenant_id=effective_tenant_id,
    )

    await AuditService.log(
        db,
        user_id=user.id,
        tenant_id=effective_tenant_id,
        action="provision",
        resource_type="resolution_vector",
        resource_id=vector.id,
        changes={
            "vector_id": body.vector_id,
            "domain": body.vector_domain,
            "is_default": body.is_default,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return _to_vector_descriptor(vector)


@router.get("/{vector_sig}", response_model=VectorDescriptor)
async def inspect_vector_node(
    vector_sig: UUID,
    user: IdentityManifest = Depends(resolve_active_identity),
    db: AsyncSession = Depends(set_tenant_context),
) -> VectorDescriptor:
    """Retrieves detailed architectural characteristics of a specific vector node."""
    vector = await VectorRegistry.get_vector(db, vector_sig)
    return _to_vector_descriptor(vector)


@router.put("/{vector_sig}", response_model=VectorDescriptor)
async def modify_vector_params(
    vector_sig: UUID,
    body: VectorModificationRequest,
    request: Request,
    user: IdentityManifest = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> VectorDescriptor:
    """Modifies an existing resolution vector. Re-obfuscates signatures if updated."""
    vector = await VectorRegistry.update_vector(
        db,
        vector_sig=vector_sig,
        vector_id=body.vector_id,
        vector_category=body.vector_domain,
        auth_sig=body.auth_sig,
        is_default=body.is_default,
        is_active=body.is_active,
        config=body.config,
    )

    await AuditService.log(
        db,
        user_id=user.id,
        tenant_id=user.nexus_sig,
        action="modify",
        resource_type="resolution_vector",
        resource_id=vector.id,
        changes=body.model_dump(exclude_unset=True, exclude={"auth_sig"}, mode="json"),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return _to_vector_descriptor(vector)


@router.delete("/{vector_sig}", status_code=204, response_class=Response)
async def decommission_vector(
    vector_sig: UUID,
    request: Request,
    user: IdentityManifest = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> Response:
    """Decommissions a resolution vector, revoking its participation in the architectural nexus."""
    await AuditService.log(
        db,
        user_id=user.id,
        tenant_id=user.nexus_sig,
        action="decommission",
        resource_type="resolution_vector",
        resource_id=vector_sig,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await VectorRegistry.delete_vector(db, vector_sig)
    return Response(status_code=204)


@router.post("/{vector_sig}/audit", response_model=VectorConnectivityAudit)
async def audit_vector_connectivity(
    vector_sig: UUID,
    user: IdentityManifest = Depends(resolve_active_identity),
    db: AsyncSession = Depends(set_tenant_context),
) -> VectorConnectivityAudit:
    """Performs a diagnostic audit of a vector node's upstream connectivity."""
    res = await VectorRegistry.audit_vector(db, vector_sig)
    return VectorConnectivityAudit(**res)


@router.post("/{vector_sig}/sync", response_model=VectorDescriptor)
async def synchronize_node_catalog(
    vector_sig: UUID,
    request: Request,
    user: IdentityManifest = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> VectorDescriptor:
    """Synchronizes a vector node's localized capability catalog (models/weights/profiles)."""
    vector = await VectorRegistry.sync_vector_catalog(db, vector_sig)

    await AuditService.log(
        db,
        user_id=user.id,
        tenant_id=user.nexus_sig,
        action="synchronize",
        resource_type="resolution_vector",
        resource_id=vector.id,
        changes={"catalog_synchronized": True},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return _to_vector_descriptor(vector)


# ── Secondary Transport Provisioning ──────────────────────────────


@router.post("/transport/secondary", status_code=201)
async def provision_secondary_transport(
    request: Request,
    user: IdentityManifest = Depends(require_write),
    db: AsyncSession = Depends(set_tenant_context),
) -> VectorDescriptor:
    """Provisions a secondary transport cell for the current domain.

    Utilizes the master architectural transport node to provision localized egress/ingress.
    Credentials are encapsulated within a domain-scoped resolution vector.
    """
    from app.modules.providers.plivo_subaccounts import PlivoSubAccountService

    if not user.nexus_sig:
        from app.core.exceptions import ValidationError
        raise ValidationError(message="Domain context required for secondary transport provisioning")

    domain_label = "Domain"
    try:
        from app.modules.auth.models import NexusRegistry
        from sqlalchemy import select as sa_select
        res = await db.execute(sa_select(NexusRegistry).where(NexusRegistry.id == user.nexus_sig))
        nexus = res.scalar_one_or_none()
        if nexus: domain_label = nexus.label or "Domain"
    except:
        pass

    vector = await PlivoSubAccountService.create_subaccount(
        db=db,
        tenant_id=user.nexus_sig,
        tenant_name=domain_label,
    )

    await AuditService.log(
        db,
        user_id=user.id,
        tenant_id=user.nexus_sig,
        action="provision",
        resource_type="secondary_transport",
        resource_id=vector.id,
        changes={"transport_type": "regional", "isolated": True},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    await db.commit()
    return _to_vector_descriptor(vector)
