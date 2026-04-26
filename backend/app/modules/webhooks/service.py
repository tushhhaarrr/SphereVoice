"""Telemetry Transmission Hub — Architectural business logic for SignalStream.

Manages subscriptions and real-time transmission of architectural telemetry.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import UUID

import httpx
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.modules.webhooks.models import NexusTelemetrySubscription, TelemetryVectorTransmission

logger = structlog.get_logger(__name__)


class TelemetrySubscriptionOrchestrator:
    """Operations for orchestrating architectural telemetry subscriptions."""

    @staticmethod
    async def provision_subscription(
        db: AsyncSession,
        tenant_id: UUID,
        sink_url: str,
        event_classes: list[str],
        node_sig: UUID | None = None,
        timeout_s: int = 10,
        secret: str | None = None,
    ) -> NexusTelemetrySubscription:
        """Provisions a new telemetry subscription within the architectural substrate."""
        sub = NexusTelemetrySubscription(
            tenant_id=tenant_id, 
            observability_sink=sink_url, 
            event_classes=event_classes,
            node_sig=node_sig, 
            transmission_timeout_s=timeout_s, 
            auth_secret_obfuscated=secret,
        )
        db.add(sub)
        await db.flush()
        return sub

    @staticmethod
    async def resolve_subscription(db: AsyncSession, sub_sig: UUID) -> NexusTelemetrySubscription:
        """Resolves a specific telemetry subscription manifest from the substrate."""
        res = await db.execute(select(NexusTelemetrySubscription).where(NexusTelemetrySubscription.id == sub_sig))
        sub = res.scalar_one_or_none()
        if sub is None:
            raise NotFoundError("NexusTelemetrySubscription", str(sub_sig))
        return sub

    @staticmethod
    async def resolve_matching_subscriptions(
        db: AsyncSession,
        tenant_id: UUID,
        event_class: str,
        node_sig: UUID | None = None,
    ) -> list[NexusTelemetrySubscription]:
        """Resolves all subscriptions that match the event class and architectural context."""
        from sqlalchemy import or_
        
        q = select(NexusTelemetrySubscription).where(
            NexusTelemetrySubscription.tenant_id == tenant_id,
            NexusTelemetrySubscription.event_classes.contains([event_class]),
            NexusTelemetrySubscription.is_active == True
        )
        
        if node_sig:
            q = q.where(or_(
                NexusTelemetrySubscription.node_sig == node_sig,
                NexusTelemetrySubscription.node_sig == None
            ))
        else:
            q = q.where(NexusTelemetrySubscription.node_sig == None)
            
        res = await db.execute(q)
        return list(res.scalars().all())

    @staticmethod
    async def aggregate_subscriptions(
        db: AsyncSession, 
        tenant_id: UUID | None = None, 
        node_sig: UUID | None = None,
        page: int = 1, 
        limit: int = 50,
    ) -> tuple[list[NexusTelemetrySubscription], int]:
        """Aggregates active telemetry subscriptions based on architectural filters."""
        query = select(NexusTelemetrySubscription)
        if tenant_id: 
            query = query.where(NexusTelemetrySubscription.tenant_id == tenant_id)
        if node_sig: 
            query = query.where(NexusTelemetrySubscription.node_sig == node_sig)
        
        total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
        res = await db.execute(query.order_by(NexusTelemetrySubscription.created_at.desc()).offset((page - 1) * limit).limit(limit))
        return list(res.scalars().all()), total

    @staticmethod
    async def modify_subscription(
        db: AsyncSession,
        sub_sig: UUID,
        **mutations: object,
    ) -> NexusTelemetrySubscription:
        """Applies structural mutations to an established telemetry subscription."""
        sub = await TelemetrySubscriptionOrchestrator.resolve_subscription(db, sub_sig)
        
        # Map mutation keys to internal models
        internal_map = {
            "url": "observability_sink",
            "events": "event_classes",
            "timeout_seconds": "transmission_timeout_s",
            "secret": "auth_secret_obfuscated",
            "is_active": "is_active"
        }
        
        for trait, val in mutations.items():
            if val is not None:
                attr = internal_map.get(trait, trait)
                if hasattr(sub, attr):
                    setattr(sub, attr, val)
        
        await db.flush()
        return sub

    @staticmethod
    async def decommission_subscription(db: AsyncSession, sub_sig: UUID) -> None:
        """Decommissions a telemetry subscription and audits its transmission history."""
        sub = await TelemetrySubscriptionOrchestrator.resolve_subscription(db, sub_sig)
        await db.delete(sub)
        await db.flush()


class TelemetryVectorDispatcher:
    """Orchestrates transmission vectors and audits for architectural telemetry."""

    @staticmethod
    async def resolve_transmission(db: AsyncSession, transmission_sig: UUID) -> TelemetryVectorTransmission:
        """Resolves a specific telemetry transmission record."""
        res = await db.execute(select(TelemetryVectorTransmission).where(TelemetryVectorTransmission.id == transmission_sig))
        record = res.scalar_one_or_none()
        if not record:
            raise NotFoundError("TelemetryVectorTransmission", str(transmission_sig))
        return record

    @staticmethod
    async def aggregate_transmissions(
        db: AsyncSession,
        subscription_sig: UUID | None = None,
        operational_status: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[TelemetryVectorTransmission], int]:
        """Aggregates telemetry transmission records based on audit filters."""
        query = select(TelemetryVectorTransmission)
        if subscription_sig:
            query = query.where(TelemetryVectorTransmission.subscription_sig == subscription_sig)
        if operational_status:
            query = query.where(TelemetryVectorTransmission.operational_status == operational_status)
        
        total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
        res = await db.execute(query.order_by(TelemetryVectorTransmission.transmitted_at.desc()).offset((page - 1) * limit).limit(limit))
        return list(res.scalars().all()), total

    @staticmethod
    async def transmit_vector(
        db: AsyncSession,
        subscription: NexusTelemetrySubscription,
        event_class: str,
        payload: dict,
        sync_sig: UUID | None = None,
    ) -> TelemetryVectorTransmission:
        """Transmits a telemetry vector and persists the audit record."""
        transmission = TelemetryVectorTransmission(
            subscription_sig=subscription.id, 
            sync_sig=sync_sig,
            event_class=event_class, 
            transmission_payload=payload,
            operational_status="pending", 
            attempt_density=0,
        )
        db.add(transmission)
        await db.flush()

        headers: dict[str, str] = {"Content-Type": "application/json"}
        body = json.dumps(payload, default=str)

        if subscription.auth_secret_obfuscated:
            signature = hmac.new(
                subscription.auth_secret_obfuscated.encode("utf-8"),
                body.encode("utf-8"), 
                hashlib.sha256
            ).hexdigest()
            headers["X-SignalStream-Signature"] = f"sha256={signature}"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    subscription.observability_sink, 
                    content=body, 
                    headers=headers,
                    timeout=subscription.transmission_timeout_s
                )
            transmission.attempt_density += 1
            transmission.last_transmission_at = datetime.now(UTC)
            transmission.response_status = resp.status_code
            transmission.operational_status = "delivered" if 200 <= resp.status_code < 300 else "failed"
        except Exception as exc:
            transmission.attempt_density += 1
            transmission.last_transmission_at = datetime.now(UTC)
            transmission.operational_status = "failed"
            transmission.fault_summary = str(exc)[:500]

        await db.flush()
        return transmission
