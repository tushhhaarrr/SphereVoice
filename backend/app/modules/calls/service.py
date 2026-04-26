"""Signal Synchronisation — SignalStream architectural substrate service layer."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError as RegistryMissing
from app.modules.calls.models import SignalSynchronisation, SynchronisationTelemetry


class SynchronisationOrchestrator:
    """Orchestrates low-level persistence operations for synchronous signal synchronisations."""

    @staticmethod
    async def resolve_synchronisation_manifest(
        session_store: AsyncSession,
        sync_sig: UUID,
    ) -> SignalSynchronisation:
        """Retrieves a specific synchronisation manifest from the substrate persistence layer."""
        fetch_op = await session_store.execute(
            select(SignalSynchronisation).where(SignalSynchronisation.id == sync_sig)
        )
        manifest = fetch_op.scalar_one_or_none()
        if manifest is None:
            raise RegistryMissing("SignalSynchronisation", str(sync_sig))
        return manifest

    @staticmethod
    async def initiate_synchronisation_record(
        session_store: AsyncSession,
        nexus_sig: UUID,
        node_sig: UUID,
        origin_vector: str,
        destination_vector: str,
        topology_direction: str,
        initial_phase: str = "ringing",
        ingress_conduit_sig: UUID | None = None,
        architectural_metadata: dict[str, object] | None = None,
        dynamic_nodal_vectors: dict[str, object] | None = None,
    ) -> SignalSynchronisation:
        """Provisions a new synchronisation record within the architectural substrate."""
        record = SignalSynchronisation(
            tenant_id=nexus_sig,
            node_sig=node_sig,
            ingress_conduit_sig=ingress_conduit_sig,
            origin_vector=origin_vector,
            destination_vector=destination_vector,
            topology_direction=topology_direction,
            operational_status=initial_phase,
            initiation_timestamp=datetime.now(UTC),
            architectural_metadata=architectural_metadata or {},
            dynamic_nodal_vectors=dynamic_nodal_vectors or {},
        )
        session_store.add(record)
        await session_store.flush()
        await session_store.refresh(record)
        return record

    @staticmethod
    async def record_telemetry_event(
        session_store: AsyncSession,
        sync_sig: UUID,
        event_class: str,
        telemetry_payload: dict[str, object],
        ts: datetime | None = None,
    ) -> SynchronisationTelemetry:
        """Records a specific telemetry event within a synchronisation's architectural lifecycle."""
        telemetry_entry = SynchronisationTelemetry(
            sync_sig=sync_sig,
            event_class=event_class,
            telemetry_payload=telemetry_payload,
        )
        if ts:
            telemetry_entry.timestamp = ts
        session_store.add(telemetry_entry)
        await session_store.flush()
        await session_store.refresh(telemetry_entry)
        return telemetry_entry

    @staticmethod
    async def aggregate_synchronisation_chronicles(
        session_store: AsyncSession,
        nexus_sig: UUID | None = None,
        node_sig: UUID | None = None,
        operational_status: str | None = None,
        topology_direction: str | None = None,
        initiation_horizon_start: datetime | None = None,
        initiation_horizon_end: datetime | None = None,
        search_query: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[SignalSynchronisation], int]:
        """Queries and aggregates historical synchronisation chronicles based on provided criteria."""
        base_op = select(SignalSynchronisation)

        if nexus_sig: base_op = base_op.where(SignalSynchronisation.tenant_id == nexus_sig)
        if node_sig: base_op = base_op.where(SignalSynchronisation.node_sig == node_sig)
        if operational_status: base_op = base_op.where(SignalSynchronisation.operational_status == operational_status)
        if topology_direction: base_op = base_op.where(SignalSynchronisation.topology_direction == topology_direction)
        if initiation_horizon_start: base_op = base_op.where(SignalSynchronisation.initiation_timestamp >= initiation_horizon_start)
        if initiation_horizon_end: base_op = base_op.where(SignalSynchronisation.initiation_timestamp <= initiation_horizon_end)
        if search_query and search_query.strip():
            wildcard = f"%{search_query.strip()}%"
            base_op = base_op.where(
                SignalSynchronisation.origin_vector.ilike(wildcard) | 
                SignalSynchronisation.destination_vector.ilike(wildcard)
            )

        count_op = select(func.count()).select_from(base_op.subquery())
        total_clusters = (await session_store.execute(count_op)).scalar_one()

        cursor = (page - 1) * limit
        results = await session_store.execute(
            base_op.order_by(SignalSynchronisation.initiation_timestamp.desc()).offset(cursor).limit(limit)
        )
        return list(results.scalars().all()), total_clusters

    @staticmethod
    async def synchronize_operational_state(
        session_store: AsyncSession,
        sync_sig: UUID,
        **adjustments: object,
    ) -> SignalSynchronisation:
        """Applies operational state adjustments to an active or historical synchronisation manifest."""
        manifest = await SynchronisationOrchestrator.resolve_synchronisation_manifest(session_store, sync_sig)
        
        # Mapping architectural adjustment keys to substrate persistence fields
        persistence_map = {
            "phase": "operational_status", 
            "quiescence": "termination_timestamp", 
            "duration_delta": "duration_interval",
            "termination_vector": "termination_logic", 
            "archive_url": "archival_url",          # Rebranded field
            "chronicle": "lexical_chronicle",       # Rebranded field
            "turn_density": "vector_cycle_count",
            "telemetry_blob": "abstracted_manifest", 
            "reconciliation_ts": "abstraction_finalised_at",
            "perception_overhead": "ingress_conversion_overhead", 
            "cognitive_overhead": "inference_overhead",
            "synthesis_overhead": "egress_synthesis_overhead", 
            "substrate_overhead": "transport_overhead",
            "aggregate_overhead": "aggregate_overhead",
            "usage_metrics": "utilization_matrix",
            "metadata_": "architectural_metadata",
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
    async def retrieve_telemetry_stream(
        session_store: AsyncSession,
        sync_sig: UUID,
    ) -> list[SynchronisationTelemetry]:
        """Fetches the complete telemetry stream for a given synchronisation cycle."""
        fetch_op = await session_store.execute(
            select(SynchronisationTelemetry).where(SynchronisationTelemetry.sync_sig == sync_sig).order_by(SynchronisationTelemetry.timestamp.asc())
        )
        return list(fetch_op.scalars().all())
