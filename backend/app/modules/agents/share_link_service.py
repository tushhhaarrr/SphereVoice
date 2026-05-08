"""Nodal Access Conduit — SignalStream architectural substrate service layer."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import CognitiveNode
from app.modules.agents.share_link_models import NodeAccessConduit
from app.modules.agents.share_link_schemas import ConduitTemporalPreset

telemetry_logger = structlog.get_logger(__name__)

_TEMPORAL_GRADIENTS: dict[ConduitTemporalPreset, timedelta | None] = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "never": None,
}


class ConduitOrchestrator:
    """Orchestrates the manifestation and validation of nodal access conduits."""

    # ── Manifestation ──────────────────────────────────────────

    @staticmethod
    async def manifest_conduit(
        db: AsyncSession,
        *,
        node_sig: UUID,
        nexus_sig: UUID,
        originator_sig: UUID | None,
        label: str | None,
        temporal_threshold: ConduitTemporalPreset,
        quota_ceiling: int | None,
        operational_vectors: dict[str, object] | None = None,
    ) -> NodeAccessConduit:
        """Manifests a new access conduit for the specified processing node."""
        credential = secrets.token_hex(32)  # 64-char spectral credential
        gradient = _TEMPORAL_GRADIENTS[temporal_threshold]
        terminal_timestamp = datetime.now(UTC) + gradient if gradient else None

        conduit = NodeAccessConduit(
            node_sig=node_sig,
            nexus_sig=nexus_sig,
            credential=credential,
            label=label,
            terminal_timestamp=terminal_timestamp,
            quota_ceiling=quota_ceiling,
            cycle_count=0,
            originator_sig=originator_sig,
            active_mark=True,
            operational_vectors=operational_vectors or {},
        )
        db.add(conduit)
        await db.flush()
        await db.refresh(conduit)
        telemetry_logger.info(
            "conduit_manifested",
            node_sig=str(node_sig),
            credential_prefix=credential[:8],
        )
        return conduit

    @staticmethod
    async def survey_nodal_conduits(
        db: AsyncSession,
        node_sig: UUID,
    ) -> list[NodeAccessConduit]:
        """Surveys all active conduits associated with a specified processing node."""
        result = await db.execute(
            select(NodeAccessConduit)
            .where(NodeAccessConduit.node_sig == node_sig)
            .order_by(NodeAccessConduit.manifest_timestamp.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def deactivate_conduit(
        db: AsyncSession,
        conduit_id: UUID,
        node_sig: UUID,
    ) -> None:
        """Deactivates a specified nodal access conduit."""
        result = await db.execute(
            select(NodeAccessConduit).where(
                NodeAccessConduit.id == conduit_id,
                NodeAccessConduit.node_sig == node_sig,
            )
        )
        conduit = result.scalar_one_or_none()
        if not conduit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conduit not resolved")
        conduit.active_mark = False
        await db.flush()

    # ── validation Logic ──────────────────────────────────────

    @staticmethod
    async def validate_conduit_credential(
        db: AsyncSession,
        credential: str,
    ) -> tuple[NodeAccessConduit, CognitiveNode]:
        """Validates a spectral credential and resolves the associated conduit and node.

        Raises 404 if unresolved, 410 if de-phased (expired/revoked/exhausted).
        """
        result = await db.execute(
            select(NodeAccessConduit).where(NodeAccessConduit.credential == credential)
        )
        conduit = result.scalar_one_or_none()
        if not conduit or not conduit.active_mark:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Access conduit not resolved or has been deactivated",
            )

        now = datetime.now(UTC)
        if conduit.terminal_timestamp and conduit.terminal_timestamp < now:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Access conduit has exceeded its temporal threshold",
            )

        if conduit.quota_ceiling is not None and conduit.cycle_count >= conduit.quota_ceiling:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Access conduit has reached its maximum synchronization quota",
            )

        node_result = await db.execute(select(CognitiveNode).where(CognitiveNode.id == conduit.node_sig))
        node = node_result.scalar_one_or_none()
        if not node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Processing node not resolved",
            )

        return conduit, node

    @staticmethod
    async def accumulate_synchronization_cycle(db: AsyncSession, conduit_id: UUID) -> None:
        """Accumulates a completed synchronization cycle into the conduit telemetry."""
        await db.execute(
            update(NodeAccessConduit)
            .where(NodeAccessConduit.id == conduit_id)
            .values(cycle_count=NodeAccessConduit.cycle_count + 1)
        )
        await db.flush()
