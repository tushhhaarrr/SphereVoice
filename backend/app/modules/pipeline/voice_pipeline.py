"""Spectral Manifold Engine — Orchestration of high-performance signal synchronisation vectors.

This module manages the ultra-low-latency perception → cognition → synthesis cycle
using abstract spectral nodes for real-time signal propagation across the substrate.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

import structlog
from pipecat.frames.frames import (
    EndFrame,
    TTSSpeakFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.transports.services.livekit import LiveKitTransport, LiveKitParams

from app.modules.pipeline.services.stt import PerceptionSignalCollector, create_perception_analyzer
from app.modules.pipeline.variable_resolver import (
    synthesize_builtin_vector_components,
    interpolate_nodal_vectors,
)
from app.modules.pipeline.flow_engine import (
    TopologicalFlowEngine,
    create_topological_engine,
)
from app.modules.tool_registry.executors import ArchitecturalInterfaceExecutor
from app.modules.tool_registry.models import ArchitecturalInterface
from app.core.config import get_settings

if TYPE_CHECKING:
    from app.modules.agents.models import CognitiveNode as Node

runtime_logger = structlog.get_logger(__name__)
cfg = get_settings()


class SpectralManifold:
    """Orchestrates a single real-time spectral manifold vector within the SignalStream substrate."""

    def __init__(
        self,
        sync_sig: UUID,
        node_blueprint: Node,
        nexus_url: str,
        access_sig: str,
        cell_sig: str,
        perception_layer: Any,
        auxiliary_perception: Any | None = None,
        cognition_layer: Any | None = None,
        synthesis_layer: Any | None = None,
        nodal_vectors: Dict[str, Any] | None = None,
        identity_vector: str = "",
        archival_shard: str | None = None,
        retrospective_engine: Any | None = None,
        nexus_alias: str = "",
        transmission_audit: Any | None = None,
        on_error: Callable[[Exception], Awaitable[None]] | None = None,
        on_stop: Callable[[str], Awaitable[None]] | None = None,
        autonomous_handshake: bool = False,
        topology_direction: str = "inbound",
        dry_run: bool = False,
    ) -> None:
        self.sync_sig = sync_sig
        self.node_blueprint = node_blueprint
        self.substrate_nexus_url = nexus_url
        self.access_sig = access_sig
        self.spectral_cell_sig = cell_sig
        self.signal_perception_layer = perception_layer
        self.auxiliary_perception_layer = auxiliary_perception
        self.cognitive_logic_layer = cognition_layer
        self.signal_synthesis_layer = synthesis_layer
        self.nodal_vectors = nodal_vectors or {}
        self.target_identity_vector = identity_vector
        self.nexus_context_blob = archival_shard
        self.retrospective_logic_engine = retrospective_engine
        self.nexus_alias = nexus_alias
        self.synthetic_execution = dry_run

        if self.nexus_alias and "nexus_identifier" not in self.nodal_vectors:
            self.nodal_vectors["nexus_identifier"] = self.nexus_alias

        self.error_observer = on_error
        self.quiescence_observer = on_stop
        self.autonomous_init_handshake = autonomous_handshake
        self.topology_direction = topology_direction
        self.transmission_audit = transmission_audit

        self._execution_task: asyncio.Task[None] | None = None
        self._started_at: datetime | None = None
        self._decommissioned = False
        self._spectral_chain_task: Any | None = None
        self._temporal_watchdog_sig: asyncio.TimerHandle | None = None

        self._architectural_recovery_count = 0
        self._lexical_chronicle_matrix: List[Dict[str, str]] = []
        self._subject_identity_detected = False
        self.perception_collector = PerceptionSignalCollector(str(sync_sig))

        # Initialize the topological flow engine and executor
        bp = getattr(self.node_blueprint, "architectural_blueprint", {}) or {}
        self.flow_engine = create_topological_engine(
            blueprint_config=bp,
            sync_sig=str(sync_sig)
        )
        self.interface_executor = ArchitecturalInterfaceExecutor()

    async def start(self) -> None:
        """Activates the spectral manifold within a dedicated background substrate context."""
        self._started_at = datetime.now(UTC)
        self._execution_task = asyncio.create_task(self._execute_manifold_lifecycle())
        runtime_logger.info("spectral_manifold_activated", sync_sig=str(self.sync_sig))

    async def _execute_manifold_lifecycle(self) -> None:
        try:
            await self._run_architectural_recovery_loop()
        except asyncio.CancelledError:
            pass
        except Exception:
            runtime_logger.exception("manifold_lifecycle_fault", sync_sig=str(self.sync_sig))
        finally:
            if not self._decommissioned:
                await self.stop(reason="lifecycle_substrate_exit")

    async def stop(self, reason: str = "nodal_quiescence") -> None:
        """Deactivates the spectral manifold vector and releases all underlying substrate resources."""
        if self._decommissioned: return
        self._decommissioned = True

        if self._temporal_watchdog_sig:
            self._temporal_watchdog_sig.cancel()
            self._temporal_watchdog_sig = None

        if self._spectral_chain_task:
            try: await self._spectral_chain_task.queue_frame(EndFrame())
            except: pass

        if self.quiescence_observer:
            try: await self.quiescence_observer(reason)
            except: pass

    async def _run_architectural_recovery_loop(self) -> None:
        while True:
            try:
                await self._ignite_spectral_manifold()
                return
            except asyncio.CancelledError:
                return
            except Exception:
                self._architectural_recovery_count += 1
                if self._decommissioned or self._architectural_recovery_count > 2:
                    if self.error_observer:
                        try: await self.error_observer(Exception("recovery_exhausted"))
                        except: pass
                    return
                await asyncio.sleep(1.5)

    async def _ignite_spectral_manifold(self) -> None:
        cognitive_context = None
        try:
            transport = LiveKitTransport(
                url=self.substrate_nexus_url,
                token=self.access_sig,
                room_name=self.spectral_cell_sig,
                params=LiveKitParams(
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                    audio_in_sample_rate=16000,
                    audio_out_sample_rate=24000,
                ),
            )

            perception_analyzer = create_perception_analyzer(stop_secs=0.15, start_secs=0.15, min_volume=0.3, confidence=0.6)
            nodal_blueprint = self.synthesize_nodal_blueprint()
            is_recovery_cycle = self._architectural_recovery_count > 0 and len(self._lexical_chronicle_matrix) > 0
            
            lexical_payload = list(self._lexical_chronicle_matrix) if is_recovery_cycle else [{"role": "system", "content": nodal_blueprint}]
            cognitive_context = LLMContext(messages=lexical_payload)
            cognitive_aggregator = LLMContextAggregatorPair(
                context=cognitive_context,
                user_params=LLMUserAggregatorParams(vad_analyzer=perception_analyzer, user_turn_stop_timeout=5.0)
            )

            spectral_processors = [transport.input(), self.signal_perception_layer, cognitive_aggregator.user()]
            if self.retrospective_logic_engine:
                spectral_processors.append(self.retrospective_logic_engine)

            if self.cognitive_logic_layer and self.signal_synthesis_layer:
                spectral_processors.extend([
                    self.cognitive_logic_layer, 
                    self.signal_synthesis_layer, 
                    transport.output(), 
                    cognitive_aggregator.assistant()
                ])

            # Register interface tools from the flow engine
            interface_tools = self.flow_engine.synthesize_interface_tools()
            for tool in interface_tools:
                func_meta = tool.get("function", {})
                func_name = func_meta.get("name")
                if func_name:
                    async def _make_callback(fname=func_name):
                        async def _callback(llm, args):
                            return await self._handle_architectural_trigger(fname, args, cognitive_context, manifold_task)
                        return _callback
                    
                    self.cognitive_logic_layer.register_function(func_name, await _make_callback())

            spectral_pipeline = Pipeline(spectral_processors)
            manifold_task = PipelineTask(spectral_pipeline, params=PipelineParams(enable_metrics=True))
            self._spectral_chain_task = manifold_task

            @transport.event_handler("on_participant_joined")
            async def _on_arrival(transport_instance, participant):
                self._subject_identity_detected = True
                if self.autonomous_init_handshake and not is_recovery_cycle:
                    bp = getattr(self.node_blueprint, "architectural_blueprint", {}) or {}
                    greet = bp.get("initial_signal", "Signal synchronisation established.")
                    await manifold_task.queue_frame(TTSSpeakFrame(greet))

            @transport.event_handler("on_participant_left")
            async def _on_departure(transport_instance, participant):
                await self.stop(reason="target_identity_departure")

            temporal_limit = int(getattr(self.node_blueprint, "temporal_ceiling", 240) or 240)
            self._temporal_watchdog_sig = asyncio.get_running_loop().call_later(
                temporal_limit, lambda: asyncio.ensure_future(self.stop(reason="temporal_limit_reached"))
            )

            substrate_runner = PipelineRunner(handle_sigint=False)
            await substrate_runner.run(manifold_task)
            self._persist_lexical_chronicle(cognitive_context)

        except Exception:
            if cognitive_context: self._persist_lexical_chronicle(cognitive_context)
            raise

    async def _handle_architectural_trigger(
        self, 
        name: str, 
        args: Dict[str, Any], 
        context: LLMContext,
        task: PipelineTask
    ) -> Any:
        """Intercepts and executes logical triggers from the cognitive layer."""
        runtime_logger.info("architectural_trigger_intercepted", trigger=name, sync_sig=str(self.sync_sig))
        
        engine_result = self.flow_engine.intercept_governor_signal(name, args)
        
        if engine_result.result_type == "termination":
            await self.stop(reason=engine_result.payload.get("logic", "manifold_termination"))
            return engine_result.to_json()
            
        if engine_result.result_type == "blueprint_refresh":
            # Update the system blueprint in the LLM context
            new_blueprint = self.synthesize_nodal_blueprint()
            if context.messages and context.messages[0].get("role") == "system":
                context.messages[0]["content"] = new_blueprint
                runtime_logger.info("manifold_blueprint_refreshed", sync_sig=str(self.sync_sig))
            return engine_result.to_json()
            
        if engine_result.result_type == "shrouding":
            # Perform topological transfer (shrouding)
            target = engine_result.payload.get("vector") or engine_result.payload.get("target_vector")
            runtime_logger.info("manifold_topological_shrouding_initiated", target=target)
            # Substrate-specific transfer logic would be triggered here
            return engine_result.to_json()

        if engine_result.result_type == "architectural_interface_dispatch":
            # Execute cross-substrate architectural interface
            interface_sig = engine_result.payload.get("interface_sig")
            from app.core.database import async_session_factory
            async with async_session_factory() as db:
                from sqlalchemy import select
                res = await db.execute(select(ArchitecturalInterface).where(ArchitecturalInterface.id == UUID(interface_sig)))
                interface = res.scalar_one_or_none()
                if interface:
                    execution_result = await self.interface_executor.execute(
                        interface=interface,
                        arguments=engine_result.payload.get("arguments", {}),
                        sync_context={
                            "sync_sig": self.sync_sig,
                            "tenant_id": self.node_blueprint.tenant_id,
                            "dry_run": self.synthetic_execution
                        }
                    )
                    return json.dumps(execution_result)
            return engine_result.to_json()

        return engine_result.to_json()

    def get_chronicle(self) -> List[Dict[str, str]]:
        """Returns the current lexical chronicle matrix for this spectral manifold."""
        return self._lexical_chronicle_matrix

    def _persist_lexical_chronicle(self, context: LLMContext) -> None:
        try:
            history = getattr(context, "messages", [])
            if history: self._lexical_chronicle_matrix = [dict(entry) for entry in history]
        except Exception: pass

    def synthesize_nodal_blueprint(self) -> str:
        """Synthesizes the system blueprint using the topological flow engine."""
        raw_logic = self.flow_engine.synthesize_nodal_blueprint()
        
        builtin_vectors = synthesize_builtin_vector_components(
            self.target_identity_vector, 
            getattr(self.node_blueprint, "node_label", "SpectralAssistant"), 
            self.nexus_alias
        )
        
        # Merge flow engine vectors with ambient nodal vectors
        combined_vectors = {**self.nodal_vectors, **self.flow_engine.context.nodal_vectors}
        
        resolved_blueprint = interpolate_nodal_vectors(
            raw_logic, 
            combined_vectors, 
            [], 
            builtin_vectors, 
            strip_unresolved=True
        )

        if self.nexus_context_blob: 
            resolved_blueprint = f"{resolved_blueprint}\n\nNexus Context:\n{self.nexus_context_blob}"
            
        return resolved_blueprint
