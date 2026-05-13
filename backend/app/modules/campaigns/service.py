"""Campaigns Campaigns — Architectural business logic substrate."""

from __future__ import annotations

import uuid
from typing import Any
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.campaigns.models import CampaignsCampaign, PropagationTarget

logger = structlog.get_logger(__name__)


class CampaignsOrchestrator:
    """Service layer for CampaignsCampaign and PropagationTarget lifecycle management."""

    @staticmethod
    async def aggregate_propagation_campaigns(
        db: AsyncSession, 
        tenant_id: uuid.UUID, 
        skip: int = 0, 
        limit: int = 100, 
        status: str | None = None,
    ) -> tuple[list[CampaignsCampaign], int]:
        count_q = select(func.count()).select_from(CampaignsCampaign).where(CampaignsCampaign.tenant_id == tenant_id)
        rows_q = select(CampaignsCampaign).where(CampaignsCampaign.tenant_id == tenant_id).order_by(CampaignsCampaign.created_at.desc())
        
        if status:
            count_q = count_q.where(CampaignsCampaign.operational_status == status)
            rows_q = rows_q.where(CampaignsCampaign.operational_status == status)
            
        total = (await db.execute(count_q)).scalar_one()
        rows = (await db.execute(rows_q.offset(skip).limit(limit))).scalars().all()
        return list(rows), total

    @staticmethod
    async def get_campaign(
        db: AsyncSession, 
        campaign_id: uuid.UUID, 
        tenant_id: uuid.UUID | None = None
    ) -> CampaignsCampaign:
        """Resolve a propagation campaign by identifier."""
        q = select(CampaignsCampaign).where(CampaignsCampaign.id == campaign_id)
        if tenant_id:
            q = q.where(CampaignsCampaign.tenant_id == tenant_id)
            
        row = (await db.execute(q)).scalar_one_or_none()
        if not row:
            raise NotFoundError("CampaignsCampaign", str(campaign_id))
        return row

    @staticmethod
    async def provision_propagation_campaign(
        db: AsyncSession, 
        tenant_id: uuid.UUID, 
        data: Any, 
        created_by: uuid.UUID | None = None
    ) -> CampaignsCampaign:
        """Provision a new signal propagation campaign."""
        campaign = CampaignsCampaign(
            tenant_id=tenant_id,
            name=data.name,
            description=data.description,
            node_sig=data.node_sig if hasattr(data, "node_sig") else getattr(data, "agent_id", None),
            operational_status="draft",
            source_type=data.source_type,
            source_config=data.source_config,
            vector_mapping=data.vector_mapping if hasattr(data, "vector_mapping") else getattr(data, "variable_mapping", {}),
            writeback_mapping=data.writeback_mapping,
            origin_vector=data.origin_vector if hasattr(data, "origin_vector") else getattr(data, "from_number", None),
            signals_per_minute=data.signals_per_minute if hasattr(data, "signals_per_minute") else getattr(data, "calls_per_minute", 10),
            max_concurrent=data.max_concurrent,
            max_retries=data.max_retries,
            scheduled_at=data.scheduled_at,
        )
        db.add(campaign)
        await db.flush()
        return campaign

    @staticmethod
    async def activate_propagation_cycle(
        db: AsyncSession, 
        campaign_id: uuid.UUID, 
        tenant_id: uuid.UUID
    ) -> CampaignsCampaign:
        """Activate a propagation campaign, transitioning it to the 'running' state."""
        campaign = await CampaignsOrchestrator.get_campaign(db, campaign_id, tenant_id)
        if campaign.operational_status not in ("draft", "scheduled", "paused"):
            raise ValidationError(f"Cannot activate propagation campaign in state '{campaign.operational_status}'.")
        
        campaign.operational_status = "running"
        await db.flush()
        return campaign

    @staticmethod
    async def complete_campaign(db: AsyncSession, campaign_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        """Finalize a propagation campaign."""
        campaign = await CampaignsOrchestrator.get_campaign(db, campaign_id, tenant_id)
        campaign.operational_status = "completed"
        await db.flush()

    @staticmethod
    async def fetch_next_batch(
        db: AsyncSession, 
        campaign_id: uuid.UUID, 
        batch_size: int = 10
    ) -> list[PropagationTarget]:
        """Fetch the subsequent batch of pending propagation targets."""
        q = select(PropagationTarget).where(
            PropagationTarget.campaign_id == campaign_id,
            PropagationTarget.status.in_(["pending", "retry_scheduled"]),
        )
        
        # Priority: pending then retry_scheduled (if retry time reached)
        now = datetime.now(UTC)
        q = q.where(
            (PropagationTarget.status == "pending") | 
            ((PropagationTarget.status == "retry_scheduled") & (PropagationTarget.next_retry_at <= now))
        )
        
        q = q.limit(batch_size)
        return list((await db.execute(q)).scalars().all())

    @staticmethod
    async def mark_contact_queued(db: AsyncSession, target_id: uuid.UUID) -> None:
        """Mark a propagation target as enqueued for substrate execution."""
        await db.execute(
            update(PropagationTarget)
            .where(PropagationTarget.id == target_id)
            .values(status="queued")
        )
        await db.flush()

    @staticmethod
    async def mark_contact_calling(db: AsyncSession, target_id: uuid.UUID, sync_sig: uuid.UUID) -> None:
        """Link a propagation target to an active synchronisation cycle."""
        await db.execute(
            update(PropagationTarget)
            .where(PropagationTarget.id == target_id)
            .values(status="calling", sync_sig=sync_sig)
        )
        await db.flush()

    @staticmethod
    async def update_contact_result(
        db: AsyncSession, 
        contact_id: uuid.UUID, 
        status: str, 
        extracted_data: dict | None = None,
        tool_results: list | None = None
    ) -> None:
        """Finalize a propagation target with results from the substrate."""
        await db.execute(
            update(PropagationTarget)
            .where(PropagationTarget.id == contact_id)
            .values(
                status=status, 
                abstracted_manifest=extracted_data,
                interface_results=tool_results
            )
        )
        await db.flush()

    @staticmethod
    async def increment_campaign_stats(
        db: AsyncSession, 
        campaign_id: uuid.UUID, 
        completed: int = 0, 
        successful: int = 0, 
        failed: int = 0
    ) -> None:
        """Accrue propagation benchmarks for a campaign."""
        await db.execute(
            update(CampaignsCampaign)
            .where(CampaignsCampaign.id == campaign_id)
            .values(
                finalised_signals=CampaignsCampaign.finalised_signals + completed,
                successful_signals=CampaignsCampaign.successful_signals + successful,
                voided_signals=CampaignsCampaign.voided_signals + failed,
            )
        )
        await db.flush()
