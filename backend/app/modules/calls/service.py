"""Voice Engine — SignalStream architectural substrate service layer."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError as RegistryMissing
from app.modules.calls.models import VoiceEngine, SynchronisationTelemetry


class VoiceEngineService:
    """Orchestrates persistence operations for calls (Voice Engine)."""

    @staticmethod
    async def get_call(
        session_store: AsyncSession,
        call_id: UUID,
    ) -> VoiceEngine:
        """Retrieves a specific call record."""
        fetch_op = await session_store.execute(
            select(VoiceEngine).where(VoiceEngine.id == call_id)
        )
        manifest = fetch_op.scalar_one_or_none()
        if manifest is None:
            raise RegistryMissing("VoiceEngine", str(call_id))
        return manifest

    @staticmethod
    async def create_call(
        session_store: AsyncSession,
        tenant_id: UUID,
        agent_id: UUID,
        from_number: str,
        to_number: str,
        direction: str,
        status: str = "ringing",
        phone_number_id: UUID | None = None,
        metadata: dict[str, object] | None = None,
        dynamic_variables: dict[str, object] | None = None,
    ) -> VoiceEngine:
        """Provisions a new call record."""
        record = VoiceEngine(
            tenant_id=tenant_id,
            agent_id=agent_id,
            phone_number_id=phone_number_id,
            origin=from_number,
            destination=to_number,
            direction=direction,
            status=status,
            initiation_timestamp=datetime.now(UTC),
            metadata=metadata or {},
            dynamic_nodal_vectors=dynamic_variables or {},
        )
        session_store.add(record)
        await session_store.flush()
        await session_store.refresh(record)
        return record

    @staticmethod
    async def create_telemetry_event(
        session_store: AsyncSession,
        call_id: UUID,
        event_type: str,
        payload: dict[str, object],
        ts: datetime | None = None,
    ) -> SynchronisationTelemetry:
        """Records a specific telemetry event for a call."""
        telemetry_entry = SynchronisationTelemetry(
            voice_engine_id=call_id,
            event_type=event_type,
            payload=payload,
        )
        if ts:
            telemetry_entry.timestamp = ts
        session_store.add(telemetry_entry)
        await session_store.flush()
        await session_store.refresh(telemetry_entry)
        return telemetry_entry

    @staticmethod
    async def list_calls(
        session_store: AsyncSession,
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
        status: str | None = None,
        direction: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        search_query: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[VoiceEngine], int]:
        """Queries and aggregates historical call records."""
        base_op = select(VoiceEngine)

        if tenant_id: base_op = base_op.where(VoiceEngine.tenant_id == tenant_id)
        if agent_id: base_op = base_op.where(VoiceEngine.agent_id == agent_id)
        if status: base_op = base_op.where(VoiceEngine.status == status)
        if direction: base_op = base_op.where(VoiceEngine.direction == direction)
        if started_after: base_op = base_op.where(VoiceEngine.initiation_timestamp >= started_after)
        if started_before: base_op = base_op.where(VoiceEngine.initiation_timestamp <= started_before)
        if search_query and search_query.strip():
            wildcard = f"%{search_query.strip()}%"
            base_op = base_op.where(
                VoiceEngine.origin.ilike(wildcard) | 
                VoiceEngine.destination.ilike(wildcard)
            )

        count_op = select(func.count()).select_from(base_op.subquery())
        total_clusters = (await session_store.execute(count_op)).scalar_one()

        cursor = (page - 1) * limit
        results = await session_store.execute(
            base_op.order_by(VoiceEngine.initiation_timestamp.desc()).offset(cursor).limit(limit)
        )
        return list(results.scalars().all()), total_clusters

    @staticmethod
    async def update_call(
        session_store: AsyncSession,
        call_id: UUID,
        **adjustments: object,
    ) -> VoiceEngine:
        """Applies state adjustments to a call record."""
        manifest = await VoiceEngineService.get_call(session_store, call_id)
        
        # Mapping clean keys to refactor Python attribute names
        # Support both new and legacy keys for compatibility
        persistence_map = {
            "status": "status",
            "phase": "status",  # legacy
            "ended_at": "termination_timestamp",
            "quiescence": "termination_timestamp",  # legacy
            "duration": "duration",
            "duration_delta": "duration",  # legacy
            "disposition": "disposition",
            "termination_vector": "disposition",  # legacy
            "recording_url": "archival_url",
            "archive_url": "archival_url",  # legacy
            "transcript": "transcript",
            "chronicle": "transcript",  # legacy
            "turns_count": "vector_cycle_count",
            "turn_density": "vector_cycle_count",  # legacy
            "summary": "summary",
            "telemetry_blob": "summary",  # legacy
            "summary_finalized_at": "summary_finalized_at",
            "reconciliation_ts": "summary_finalized_at",  # legacy
            "avg_latency_ms": "avg_transmission_delay",
            "usage_metrics": "utilization_matrix",
            "metadata": "metadata",
            "metadata_": "metadata",  # legacy
            "dynamic_variables": "dynamic_nodal_vectors",
        }

        for attr, val in adjustments.items():
            persistence_attr = persistence_map.get(attr, attr)
            if hasattr(manifest, persistence_attr):
                setattr(manifest, persistence_attr, val)

        await session_store.flush()
        await session_store.refresh(manifest)
        return manifest

    @staticmethod
    async def get_telemetry_stream(
        session_store: AsyncSession,
        call_id: UUID,
    ) -> list[SynchronisationTelemetry]:
        """Fetches the complete telemetry stream for a given call."""
        fetch_op = await session_store.execute(
            select(SynchronisationTelemetry).where(SynchronisationTelemetry.voice_engine_id == call_id).order_by(SynchronisationTelemetry.timestamp.asc())
        )
        return list(fetch_op.scalars().all())
