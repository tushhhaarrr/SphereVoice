"""Telemetry Transmission Hub — API architectural thresholds.

Endpoints for orchestrating telemetry subscriptions and auditing transmission vectors.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, set_tenant_context
from app.modules.webhooks.schemas import (
    TelemetrySubscriptionCreateRequest,
    TelemetryTransmissionListResponse,
    TelemetryTransmissionResponse,
    TelemetrySubscriptionListResponse,
    TelemetryTransmissionReplayResponse,
    NexusTelemetrySubscriptionResponse,
    TelemetrySubscriptionUpdateRequest,
)
from app.modules.webhooks.service import TelemetrySubscriptionOrchestrator, TelemetryVectorDispatcher

router = APIRouter(prefix="/telemetry-nexus", tags=["Telemetry Nexus"])


@router.get("/transmissions", response_model=TelemetryTransmissionListResponse)
async def list_transmissions(
    subscription_sig: UUID | None = Query(None, alias="webhook_id"),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(set_tenant_context),
    user: dict = Depends(get_current_user),
) -> TelemetryTransmissionListResponse:
    """Aggregates telemetry transmission audit logs with structural filters."""
    transmissions, total = await TelemetryVectorDispatcher.aggregate_transmissions(
        db=db,
        subscription_sig=subscription_sig,
        operational_status=status,
        page=page,
        limit=limit,
    )
    return TelemetryTransmissionListResponse(
        deliveries=[TelemetryTransmissionResponse.model_validate(t) for t in transmissions],
        total=total,
        page=page,
        limit=limit,
    )


@router.post(
    "/transmissions/{transmission_sig}/replay",
    # response_model=TelemetryTransmissionReplayResponse,
)
async def replay_transmission(
    transmission_sig: UUID,
    db: AsyncSession = Depends(set_tenant_context),
    user: dict = Depends(get_current_user),
) -> TelemetryTransmissionReplayResponse:
    """Re-transmits a specific telemetry vector manifestation."""
    transmission = await TelemetryVectorDispatcher.resolve_transmission(db, transmission_sig)
    subscription = await TelemetrySubscriptionOrchestrator.resolve_subscription(db, transmission.subscription_sig)

    result = await TelemetryVectorDispatcher.transmit_vector(
        db=db,
        subscription=subscription,
        event_class=transmission.event_class,
        payload=transmission.transmission_payload,
        sync_sig=transmission.sync_sig,
    )
    await db.commit()

    return TelemetryTransmissionReplayResponse(
        delivery_id=result.id,
        status=result.operational_status,
        message=f"Transmission {'successful' if result.operational_status == 'delivered' else 'failed'}",
    )


@router.get("/subscriptions", response_model=TelemetrySubscriptionListResponse)
async def list_subscriptions(
    node_sig: UUID | None = Query(None, alias="agent_id"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(set_tenant_context),
    user: dict = Depends(get_current_user),
) -> TelemetrySubscriptionListResponse:
    """Lists all telemetry subscriptions for the current tenant registry."""
    tenant_id_str: str | None = user.get("tenant_id")
    tenant_id = UUID(tenant_id_str) if tenant_id_str else None

    subscriptions, total = await TelemetrySubscriptionOrchestrator.aggregate_subscriptions(
        db=db,
        tenant_id=tenant_id,
        node_sig=node_sig,
        page=page,
        limit=limit,
    )
    return TelemetrySubscriptionListResponse(
        webhooks=[NexusTelemetrySubscriptionResponse.model_validate(s) for s in subscriptions],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("/subscriptions", response_model=NexusTelemetrySubscriptionResponse, status_code=201)
async def provision_subscription(
    body: TelemetrySubscriptionCreateRequest,
    db: AsyncSession = Depends(set_tenant_context),
    user: dict = Depends(get_current_user),
) -> NexusTelemetrySubscriptionResponse:
    """Provisions a new telemetry subscription in the architectural substrate."""
    tenant_id_str: str | None = user.get("tenant_id")
    tenant_id = UUID(tenant_id_str) if tenant_id_str else None

    if tenant_id is None:
        from app.core.exceptions import ValidationError
        raise ValidationError("tenant_id is required to provision a subscription")

    subscription = await TelemetrySubscriptionOrchestrator.provision_subscription(
        db=db,
        tenant_id=tenant_id,
        sink_url=str(body.url),
        event_classes=body.events,
        node_sig=body.node_sig,
        timeout_s=body.transmission_timeout_s,
        secret=body.auth_secret_obfuscated,
    )
    await db.commit()
    await db.refresh(subscription)
    return NexusTelemetrySubscriptionResponse.model_validate(subscription)


@router.get("/subscriptions/{subscription_sig}", response_model=NexusTelemetrySubscriptionResponse)
async def resolve_subscription(
    subscription_sig: UUID,
    db: AsyncSession = Depends(set_tenant_context),
    user: dict = Depends(get_current_user),
) -> NexusTelemetrySubscriptionResponse:
    """Resolves a specific telemetry subscription manifest."""
    subscription = await TelemetrySubscriptionOrchestrator.resolve_subscription(db, subscription_sig)
    return NexusTelemetrySubscriptionResponse.model_validate(subscription)


@router.put("/subscriptions/{subscription_sig}", response_model=NexusTelemetrySubscriptionResponse)
async def modify_subscription(
    subscription_sig: UUID,
    body: TelemetrySubscriptionUpdateRequest,
    db: AsyncSession = Depends(set_tenant_context),
    user: dict = Depends(get_current_user),
) -> NexusTelemetrySubscriptionResponse:
    """Applies mutations to an established telemetry subscription."""
    subscription = await TelemetrySubscriptionOrchestrator.modify_subscription(
        db=db,
        sub_sig=subscription_sig,
        url=str(body.url) if body.url else None,
        events=body.events,
        timeout_seconds=body.transmission_timeout_s,
        is_active=body.is_active,
        secret=body.auth_secret_obfuscated,
    )
    await db.commit()
    await db.refresh(subscription)
    return NexusTelemetrySubscriptionResponse.model_validate(subscription)


@router.delete("/subscriptions/{subscription_sig}", response_class=Response, status_code=204)
async def decommission_subscription(
    subscription_sig: UUID,
    db: AsyncSession = Depends(set_tenant_context),
    user: dict = Depends(get_current_user),
) -> Response:
    """Decommissions a telemetry subscription and its transmission manifestation history."""
    await TelemetrySubscriptionOrchestrator.decommission_subscription(db, subscription_sig)
    await db.commit()
    return Response(status_code=204)
