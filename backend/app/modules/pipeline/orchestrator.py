"""Signal Synchronisation — SignalStream architectural substrate orchestration."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import structlog
from livekit.api import AccessToken, LiveKitAPI, VideoGrants
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.modules.agents import ProcessingNode as Node, NodeStateArchive
from app.modules.auth import NexusRegistry
from app.modules.agents.models import NodeKnowledgeMatrix
from app.modules.calls.service import SynchronisationOrchestrator
from app.modules.phone_numbers.models import IngressConduit
from app.modules.pipeline.factory import NodalProviderFactory as StreamBackendFactory
from app.modules.pipeline.voice_pipeline import SpectralManifold
from app.modules.pipeline.event_broadcaster import SpectralEventDispatcher
from app.modules.pipeline.services.overhead_audit import TransmissionOverheadAudit
from app.modules.pipeline.knowledge_processor import (
    ArchivalShardRetriever,
    RetrospectiveLogicEngine,
)
from app.modules.pipeline.retrospective_analysis import run_post_synchronisation_analysis
from app.modules.pipeline.services.recording import initiate_signal_archival, terminate_signal_archival
from app.modules.pipeline.telemetry_propagation import propagate_node_telemetry as dispatch_external_signal

runtime_logger = structlog.get_logger(__name__)
cfg = get_settings()


def _resolve_spectral_sig(val: object) -> UUID | None:
    """Safely resolves an object into a compliant spectral signature."""
    if isinstance(val, UUID): return val
    if isinstance(val, str) and val:
        try: return UUID(val)
        except: return None
    return None


_active_spectral_manifolds: dict[str, SpectralManifold] = {}
_WATCHDOG_CYCLE_INTERVAL = 30
_manifold_watchdog_task: asyncio.Task[None] | None = None


def sum_active_manifold_density() -> int:
    """Returns the current density of active spectral manifolds."""
    return len(_active_spectral_manifolds)


def resolve_active_manifold(sync_sig: UUID | str) -> SpectralManifold | None:
    """Resolves an active spectral manifold by its synchronisation signature."""
    sig = str(sync_sig)
    return _active_spectral_manifolds.get(sig)


async def _spectral_manifold_watchdog() -> None:
    """Watchdog process for ensuring architectural termination of over-extended signal vectors."""
    while True:
        try:
            await asyncio.sleep(_WATCHDOG_CYCLE_INTERVAL)
            now_ts = datetime.now(UTC)
            for sid, manifold in list(_active_spectral_manifolds.items()):
                if manifold._decommissioned or manifold._started_at is None: continue
                delta = (now_ts - manifold._started_at).total_seconds()
                threshold = int(getattr(manifold.node_blueprint, "temporal_ceiling", 0) or 240)
                if delta > threshold + 10:
                    runtime_logger.warning("manifold_decommissioned_overtime", sync_sig=sid)
                    asyncio.ensure_future(manifold.stop(reason="temporal_threshold_exceeded"))
        except asyncio.CancelledError: return
        except Exception: runtime_logger.exception("manifold_watchdog_fault")


def start_manifold_duration_watchdog() -> None:
    global _manifold_watchdog_task
    if _manifold_watchdog_task is None or _manifold_watchdog_task.done():
        _manifold_watchdog_task = asyncio.create_task(_spectral_manifold_watchdog())


def stop_manifold_duration_watchdog() -> None:
    global _manifold_watchdog_task
    if _manifold_watchdog_task and not _manifold_watchdog_task.done():
        _manifold_watchdog_task.cancel()
        _manifold_watchdog_task = None


class ManifoldGovernor:
    """Backbone engine for orchestrating synchronous spectral manifolds and signal synchronisations."""

    def __init__(self, session_store: AsyncSession) -> None:
        self.session_store = session_store

    async def intercept_ingress_vector(
        self,
        origin: str,
        target: str,
        ext_sig: str,
        gateway: str = "telephony_substrate",
    ) -> dict[str, str]:
        runtime_logger.info("ingress_signal_detected", origin=origin, target=target)

        ingress_conduit = await self._resolve_ingress_conduit(target)
        if not ingress_conduit:
            return self._render_signal_rejection("Ingress vector unauthorized.", gateway)

        processing_node = await self._resolve_node_blueprint(ingress_conduit.node_sig)
        if not processing_node:
            return self._render_signal_rejection("Processing node unmapped.", gateway)

        org_alias = await self._resolve_nexus_alias(ingress_conduit.tenant_id)

        sync_record = await SynchronisationOrchestrator.initiate_synchronisation_record(
            session_store=self.session_store, 
            nexus_sig=ingress_conduit.tenant_id, 
            node_sig=processing_node.id,
            origin_vector=origin, 
            destination_vector=target, 
            topology_direction="inbound", 
            initial_phase="ringing",
            ingress_conduit_sig=ingress_conduit.id, 
            architectural_metadata={"ext_sig": ext_sig, "gateway": gateway}
        )

        await SynchronisationOrchestrator.record_telemetry_event(
            session_store=self.session_store, 
            sync_sig=sync_record.id, 
            event_class="ingress_initiation",
            telemetry_payload={"origin": origin, "target": target}
        )
        await self.session_store.commit()

        cell_label = f"sync_{sync_record.id}"
        await self._link_orchestration_cell(cell_label)
        access_sig = self._generate_node_spectral_sig(cell_label)

        try:
            perception = await StreamBackendFactory.get_perception_layer(processing_node, self.session_store)
            cognitive = await StreamBackendFactory.get_cognitive_logic_layer(processing_node, self.session_store)
            vocalization = await StreamBackendFactory.get_signal_synthesis_layer(processing_node, self.session_store)
            backend_info = await StreamBackendFactory.audit_nodal_state(processing_node, self.session_store)
            
            overhead_audit = TransmissionOverheadAudit(
                sync_sig=str(sync_record.id),
                perception_provider=backend_info.get("perception", {}).get("vector"),
                cognitive_provider=backend_info.get("cognitive", {}).get("vector"),
                synthesis_provider=backend_info.get("synthesis", {}).get("vector"),
            )

            manifold = SpectralManifold(
                sync_sig=sync_record.id,
                node_blueprint=processing_node,
                nexus_url=cfg.LIVEKIT_URL,
                access_sig=access_sig,
                cell_sig=cell_label,
                perception_layer=perception,
                cognition_layer=cognitive,
                synthesis_layer=vocalization,
                retrospective_engine=await self._assemble_retrospective_engine(processing_node),
                nexus_alias=org_alias,
                transmission_audit=overhead_audit,
                on_error=self._make_manifold_fault_handler(sync_record.id, nexus_sig=ingress_conduit.tenant_id),
                on_stop=self._make_manifold_quiesce_handler(sync_record.id, nexus_sig=ingress_conduit.tenant_id),
            )

            _active_spectral_manifolds[str(sync_record.id)] = manifold
            await manifold.start()

            try: await initiate_signal_archival(cell_label, sync_record.id, ingress_conduit.tenant_id)
            except: pass

            await SynchronisationOrchestrator.record_telemetry_event(
                session_store=self.session_store, 
                sync_sig=sync_record.id, 
                event_class="manifold_activated",
                telemetry_payload={"cell": cell_label}
            )
            await self.session_store.commit()
            return self._render_ingress_bridge(self._resolve_substrate_uri(cell_label))

        except Exception:
            runtime_logger.exception("manifold_ignition_failed", sync_sig=str(sync_record.id))
            await SynchronisationOrchestrator.synchronize_operational_state(
                session_store=self.session_store, 
                sync_sig=sync_record.id, 
                phase="failed",
                termination_vector="manifold_ignition_fault", 
                quiescence=datetime.now(UTC)
            )
            await self.session_store.commit()
            return self._render_signal_rejection("System substrate ignition fault.", gateway)

    async def initiate_outbound_synchronisation(
        self,
        node_sig: UUID,
        to_number: str,
        from_number: str,
        nexus_sig: UUID,
        dynamic_nodal_vectors: dict[str, object] | None = None,
        architectural_metadata: dict[str, object] | None = None,
    ) -> dict[str, str]:
        """Initiates an outbound signal synchronisation via the telephony substrate."""
        runtime_logger.info("outbound_signal_initiated", target=to_number, node=str(node_sig))

        processing_node = await self._resolve_node_blueprint(node_sig)
        if not processing_node:
            return self._render_signal_rejection("Processing node unmapped.", "telephony_substrate")

        org_alias = await self._resolve_nexus_alias(nexus_sig)

        sync_record = await SynchronisationOrchestrator.initiate_synchronisation_record(
            session_store=self.session_store,
            nexus_sig=nexus_sig,
            node_sig=node_sig,
            origin_vector=from_number,
            destination_vector=to_number,
            topology_direction="outbound",
            initial_phase="ringing",
            architectural_metadata=architectural_metadata or {},
            dynamic_nodal_vectors=dynamic_nodal_vectors or {}
        )

        await SynchronisationOrchestrator.record_telemetry_event(
            session_store=self.session_store,
            sync_sig=sync_record.id,
            event_class="egress_initiation",
            telemetry_payload={"target": to_number, "origin": from_number}
        )
        await self.session_store.commit()

        cell_label = f"sync_{sync_record.id}"
        await self._link_orchestration_cell(cell_label)
        access_sig = self._generate_node_spectral_sig(cell_label)

        try:
            perception = await StreamBackendFactory.get_perception_layer(processing_node, self.session_store)
            cognitive = await StreamBackendFactory.get_cognitive_logic_layer(processing_node, self.session_store)
            vocalization = await StreamBackendFactory.get_signal_synthesis_layer(processing_node, self.session_store)
            backend_info = await StreamBackendFactory.audit_nodal_state(processing_node, self.session_store)

            overhead_audit = TransmissionOverheadAudit(
                sync_sig=str(sync_record.id),
                perception_provider=backend_info.get("perception", {}).get("vector"),
                cognitive_provider=backend_info.get("cognitive", {}).get("vector"),
                synthesis_provider=backend_info.get("synthesis", {}).get("vector"),
            )

            manifold = SpectralManifold(
                sync_sig=sync_record.id,
                node_blueprint=processing_node,
                nexus_url=cfg.LIVEKIT_URL,
                access_sig=access_sig,
                cell_sig=cell_label,
                perception_layer=perception,
                cognition_layer=cognitive,
                synthesis_layer=vocalization,
                retrospective_engine=await self._assemble_retrospective_engine(processing_node),
                nexus_alias=org_alias,
                transmission_audit=overhead_audit,
                on_error=self._make_manifold_fault_handler(sync_record.id, nexus_sig=nexus_sig),
                on_stop=self._make_manifold_quiesce_handler(sync_record.id, nexus_sig=nexus_sig),
            )

            _active_spectral_manifolds[str(sync_record.id)] = manifold
            await manifold.start()

            try: await initiate_signal_archival(cell_label, sync_record.id, nexus_sig)
            except: pass

            await SynchronisationOrchestrator.record_telemetry_event(
                session_store=self.session_store,
                sync_sig=sync_record.id,
                event_class="manifold_activated",
                telemetry_payload={"cell": cell_label}
            )
            await self.session_store.commit()

        except Exception:
            runtime_logger.exception("outbound_manifold_ignition_failed", sync_sig=str(sync_record.id))
            await SynchronisationOrchestrator.synchronize_operational_state(
                session_store=self.session_store,
                sync_sig=sync_record.id,
                phase="failed",
                termination_vector="manifold_ignition_fault",
                quiescence=datetime.now(UTC)
            )
            await self.session_store.commit()
            return self._render_signal_rejection("System substrate ignition fault.", "telephony_substrate")

        # For outbound, we return the sync_sig so the bridge can track it
        return {
            "sync_sig": str(sync_record.id),
            "state": "initiated",
            "substrate_uri": self._resolve_substrate_uri(cell_label)
        }

    async def initiate_validation_orchestration(
        self,
        node_sig: UUID,
        originator_identity: dict[str, object],
        dynamic_nodal_vectors: dict[str, object] | None = None,
        behavioral_probe_sig: UUID | None = None,
        node_revision: int | None = None,
    ) -> dict[str, str]:
        identity_uid = originator_identity.get("sub", "anonymous")
        captured_nexus_sig = _resolve_spectral_sig(originator_identity.get("tenant_id"))

        processing_node = await self._resolve_node_blueprint(node_sig)
        if not processing_node:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Processing node missing")

        nexus_sig = processing_node.tenant_id or captured_nexus_sig
        org_alias = await self._resolve_nexus_alias(nexus_sig) if nexus_sig else "unaligned"

        sync_record = await SynchronisationOrchestrator.initiate_synchronisation_record(
            session_store=self.session_store, 
            nexus_sig=nexus_sig, 
            node_sig=processing_node.id,
            origin_vector="synthetic", 
            destination_vector="validation_node",
            topology_direction="inbound", 
            initial_phase="ringing",
            architectural_metadata={"synthetic": True, "probe": str(behavioral_probe_sig)},
            dynamic_nodal_vectors=dynamic_nodal_vectors or {}
        )

        await self.session_store.commit()
        cell_label = f"validation_{sync_record.id}"
        await self._link_orchestration_cell(cell_label)
        access_sig = self._generate_node_spectral_sig(cell_label)

        try:
            perception = await StreamBackendFactory.get_perception_layer(processing_node, self.session_store)
            cognitive = await StreamBackendFactory.get_cognitive_logic_layer(processing_node, self.session_store)
            vocalization = await StreamBackendFactory.get_signal_synthesis_layer(processing_node, self.session_store)
            
            manifold = SpectralManifold(
                sync_sig=sync_record.id,
                node_blueprint=processing_node,
                nexus_url=cfg.LIVEKIT_URL,
                access_sig=access_sig,
                cell_sig=cell_label,
                perception_layer=perception,
                cognition_layer=cognitive,
                synthesis_layer=vocalization,
                retrospective_engine=await self._assemble_retrospective_engine(processing_node),
                nexus_alias=org_alias,
                on_error=self._make_manifold_fault_handler(sync_record.id, nexus_sig=nexus_sig),
                on_stop=self._make_manifold_quiesce_handler(sync_record.id, nexus_sig=nexus_sig),
                autonomous_handshake=True,
                dry_run=True,
            )

            _active_spectral_manifolds[str(sync_record.id)] = manifold
            await manifold.start()
            await self.session_store.commit()
        except Exception:
            runtime_logger.exception("validation_manifold_fault")
            raise

        return {
            "sync_sig": str(sync_record.id),
            "access_token": self._generate_subject_spectral_sig(cell_label, str(identity_uid)),
            "spectral_cell_sig": cell_label,
            "substrate_nexus_url": cfg.LIVEKIT_URL,
        }

    @staticmethod
    def _make_manifold_fault_handler(sync_sig: UUID, nexus_sig: UUID | None):
        async def _handle_fault(exc: Exception):
            manifold = _active_spectral_manifolds.pop(str(sync_sig), None)
            chronicle = manifold.get_chronicle() if manifold else []
            archive_url = await terminate_signal_archival(sync_sig)
            async with async_session_factory() as db:
                await SynchronisationOrchestrator.synchronize_operational_state(
                    session_store=db, sync_sig=sync_sig, phase="failed", termination_vector=str(exc),
                    quiescence=datetime.now(UTC), chronicle=chronicle or None, archive_url=archive_url
                )
                await db.commit()
        return _handle_fault

    @staticmethod
    def _make_manifold_quiesce_handler(sync_sig: UUID, nexus_sig: UUID | None):
        async def _handle_quiesce(reason: str):
            manifold = _active_spectral_manifolds.pop(str(sync_sig), None)
            chronicle = manifold.get_chronicle() if manifold else []
            archive_url = await terminate_signal_archival(sync_sig)
            async with async_session_factory() as db:
                manifest = await SynchronisationOrchestrator.resolve_synchronisation_manifest(db, sync_sig)
                ts = datetime.now(UTC)
                duration = int((ts - manifest.initiation_timestamp).total_seconds()) if manifest else 0
                await SynchronisationOrchestrator.synchronize_operational_state(
                    session_store=db, sync_sig=sync_sig, phase="completed", quiescence=ts,
                    duration_delta=duration, termination_vector=reason, chronicle=chronicle or None,
                    archive_url=archive_url, turn_density=sum(1 for e in chronicle if e.get("speaker") == "user")
                )
                await db.commit()
            try:
                from app.workers.post_call import process_call
                process_call.delay(str(sync_sig))
            except: pass
        return _handle_quiesce

    async def _resolve_nexus_alias(self, nexus_sig: UUID | None) -> str:
        if not nexus_sig: return ""
        res = await self.session_store.execute(select(NexusRegistry.name).where(NexusRegistry.id == nexus_sig))
        return str(res.scalar_one_or_none() or "")

    async def _resolve_ingress_conduit(self, target_vector: str) -> IngressConduit | None:
        res = await self.session_store.execute(select(IngressConduit).where(IngressConduit.ingress_vector == target_vector, IngressConduit.status == "active"))
        return res.scalar_one_or_none()

    async def _resolve_node_blueprint(self, node_sig: UUID) -> Node | None:
        res = await self.session_store.execute(select(Node).where(Node.id == node_sig))
        node = res.scalar_one_or_none()
        if not node or node.revision < 1: return node

        archive = (await self.session_store.execute(
            select(NodeStateArchive).where(NodeStateArchive.node_sig == node_sig, NodeStateArchive.revision == node.revision)
        )).scalar_one_or_none()
        
        if not archive: return node
        bp = archive.architectural_blueprint or {}
        return SimpleNamespace(
            id=node.id, tenant_id=node.tenant_id, revision=node.revision,
            node_label=str(bp.get("node_label", node.node_label)),
            node_class=str(bp.get("node_class", node.node_class)),
            ingress_transcription_sig=_resolve_spectral_sig(bp.get("ingress_transcription_sig")) or node.ingress_transcription_sig,
            inference_matrix_sig=_resolve_spectral_sig(bp.get("inference_matrix_sig")) or node.inference_matrix_sig,
            egress_synthesis_sig=_resolve_spectral_sig(bp.get("egress_synthesis_sig")) or node.egress_synthesis_sig,
            transport_nexus_sig=_resolve_spectral_sig(bp.get("transport_nexus_sig")) or node.transport_nexus_sig,
            architectural_blueprint=bp.get("architectural_blueprint", node.architectural_blueprint),
            locale_sig=bp.get("locale_sig", node.locale_sig),
            vocal_spectral_sig=bp.get("vocal_spectral_sig", node.vocal_spectral_sig),
            transmission_velocity=bp.get("transmission_velocity", node.transmission_velocity),
            transmission_amplitude=bp.get("transmission_amplitude", node.transmission_amplitude),
            inference_model_sig=bp.get("inference_model_sig", node.inference_model_sig),
            temporal_ceiling=bp.get("temporal_ceiling", node.temporal_ceiling),
            silence_threshold=bp.get("silence_threshold", node.silence_threshold),
            alert_horizon=bp.get("alert_horizon", node.alert_horizon),
            fallback_logic=bp.get("fallback_logic", node.fallback_logic),
            synthesis_logic=bp.get("synthesis_logic", node.synthesis_logic),
            observability_sink=bp.get("observability_sink", node.observability_sink),
            telemetry_events=bp.get("telemetry_events", node.telemetry_events),
        )

    async def _assemble_retrospective_engine(self, node: Node) -> RetrospectiveLogicEngine | None:
        try:
            res = await self.session_store.execute(select(NodeKnowledgeMatrix).where(NodeKnowledgeMatrix.node_sig == node.id).limit(1))
            if res.first() is None: return None
            bp = getattr(node, "architectural_blueprint", {}) or {}
            kb = bp.get("settings", {}).get("knowledgeBase", {})
            return RetrospectiveLogicEngine(shard_retriever=ArchivalShardRetriever(
                node_sig=node.id, chunk_count=int(kb.get("chunkCount", 3)),
                similarity_threshold=float(kb.get("similarityThreshold", 0.25))
            ))
        except: return None

    async def _link_orchestration_cell(self, label: str) -> None:
        async with LiveKitAPI(cfg.LIVEKIT_URL, cfg.LIVEKIT_API_KEY, cfg.LIVEKIT_API_SECRET) as api:
            await api.room.create_room(livekit_room.CreateRoomRequest(name=label, empty_timeout=300, max_participants=10))

    async def _release_orchestration_cell(self, label: str) -> None:
        async with LiveKitAPI(cfg.LIVEKIT_URL, cfg.LIVEKIT_API_KEY, cfg.LIVEKIT_API_SECRET) as api:
            try: await api.room.delete_room(livekit_room.DeleteRoomRequest(room=label))
            except TwirpError: pass

    def _generate_node_spectral_sig(self, label: str) -> str:
        token = AccessToken(cfg.LIVEKIT_API_KEY, cfg.LIVEKIT_API_SECRET)
        token.with_identity(f"node_{label}").with_name("Processing Node").with_grants(VideoGrants(room_join=True, room=label, can_publish=True, can_subscribe=True))
        return token.to_jwt()

    def _generate_subject_spectral_sig(self, label: str, identity: str) -> str:
        token = AccessToken(cfg.LIVEKIT_API_KEY, cfg.LIVEKIT_API_SECRET)
        token.with_identity(identity).with_grants(VideoGrants(room_join=True, room=label, can_publish=True, can_subscribe=True))
        return token.to_jwt()

    def _resolve_substrate_uri(self, label: str) -> str:
        return f"livekit://{label}"

    def _render_signal_rejection(self, reason: str, gateway: str) -> dict[str, str]:
        if gateway == "telephony_substrate": return {"protocol": "reject", "logic": reason}
        return {"outcome": "rejected", "logic": reason}

    def _render_ingress_bridge(self, uri: str) -> dict[str, str]:
        return {"protocol": "bridge", "substrate_uri": uri}
