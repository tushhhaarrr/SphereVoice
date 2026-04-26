"""Spectral Manifold Substrate — Archival Shard Retrieval.

Provides two retrospective logic mechanisms for live spectral manifold synchronisations:

1. **ArchivalShardRetriever** — Lightweight helper that retrieves archival shard context
   for a given signal vector. Used by ``RetrospectiveLogicEngine`` and by
   ``synthesize_initial_archival_context`` for structural pre-loading.

2. **RetrospectiveLogicEngine** — A substrate ``FrameProcessor`` that intercepts 
   ``NodalIntelligenceFrame`` signals, extracts the latest signal ingress, 
   runs a vector similarity search across the archival matrix, and injects matching 
   shards as an architectural system signal just before the latest ingress vector 
   so the node logic can respond in real time.

Latency target: <50ms per archival shard lookup.
"""

from __future__ import annotations

import time
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge_base.retriever import KnowledgeRetriever as ArchivalManifestRetriever

runtime_logger = structlog.get_logger(__name__)


class ArchivalShardRetriever:
    """Retrieves architectural shards from the archival matrix for signal interpolation.

    Wraps the ``ArchivalManifestRetriever`` with latency telemetry and a 
    minimum-length filter to optimize embedding cycles.
    """

    def __init__(
        self,
        node_sig: UUID,
        chunk_count: int = 3,
        similarity_threshold: float = 0.25,
    ) -> None:
        self.retriever = ArchivalManifestRetriever(
            agent_id=node_sig,
            chunk_count=chunk_count,
            similarity_threshold=similarity_threshold,
        )
        self.node_sig = node_sig

    async def retrieve_archival_shard(self, signal_vector: str) -> str | None:
        """Retrieves relevant archival shards for a specified signal vector.

        Returns a formatted shard string, or None if no relevant signatures found.
        """
        if not signal_vector or len(signal_vector.strip()) < 3:
            return None

        start_ts = time.monotonic()
        shard_payload = await self.retriever.retrieve_and_format(signal_vector)
        elapsed_ms = (time.monotonic() - start_ts) * 1000

        if shard_payload:
            runtime_logger.info(
                "archival_shard_retrieved",
                node_sig=str(self.node_sig),
                vector_length=len(signal_vector),
                shard_mass=len(shard_payload),
                latency_ms=round(elapsed_ms, 1),
            )
        else:
            runtime_logger.debug(
                "no_relevant_archival_shard",
                node_sig=str(self.node_sig),
                vector_length=len(signal_vector),
                latency_ms=round(elapsed_ms, 1),
            )

        return shard_payload


class RetrospectiveLogicEngine:
    """Substrate FrameProcessor that interpolates archival shards into nodal intelligence.

    Sits between the signal aggregator and the nodal engine. When an 
    ``LLMContextFrame`` arrives (signaling that an ingress signal is ready for 
    architectural inference):

    1. Extract the latest ingress signal from the nodal context.
    2. Execute ``ArchivalShardRetriever.retrieve_archival_shard()``.
    3. If relevant shards are identified, interpolate an architectural system 
       signal containing the ``[Archival Shard Context]`` prior to the latest vector.
    4. Propagate the enriched frame downstream.

    Non-intelligence frames propagate through the substrate unchanged.
    """

    def __init__(
        self,
        shard_retriever: ArchivalShardRetriever,
    ) -> None:
        from pipecat.processors.frame_processor import FrameProcessor

        self._shard_retriever = shard_retriever
        self._logic_processor = self._build_logic_processor()

    def _build_logic_processor(self) -> object:
        """Assembles the internal substrate logic processor."""
        from pipecat.frames.frames import LLMContextFrame
        from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

        retriever = self._shard_retriever

        class _RetrospectiveShardProcessor(FrameProcessor):
            """Internal substrate processor that intercepts intelligence frames for RAG."""

            def __init__(self, sr: ArchivalShardRetriever) -> None:
                super().__init__(name="RetrospectiveLogicEngine")
                self._sr = sr

            async def process_frame(
                self, frame: object, direction: FrameDirection
            ) -> None:
                await super().process_frame(frame, direction)
                if isinstance(frame, LLMContextFrame):
                    await self._interpolate_retrospective_shard(frame)
                await self.push_frame(frame, direction)

            async def _interpolate_retrospective_shard(self, frame: LLMContextFrame) -> None:
                """Extracts the latest ingress signal and interpolates archival shards."""
                manifest_signals = frame.context.messages if frame.context else []
                if not manifest_signals:
                    return

                # Identify the latest ingress signal vector
                latest_ingress_signal = ""
                ingress_vector_index = -1
                for i in range(len(manifest_signals) - 1, -1, -1):
                    vector = manifest_signals[i]
                    if isinstance(vector, dict) and vector.get("role") == "user":
                        payload = vector.get("content", "")
                        if isinstance(payload, str):
                            latest_ingress_signal = payload
                        elif isinstance(payload, list):
                            latest_ingress_signal = " ".join(
                                component.get("text", "")
                                for component in payload
                                if isinstance(component, dict) and component.get("type") == "text"
                            )
                        ingress_vector_index = i
                        break

                if not latest_ingress_signal or ingress_vector_index < 0:
                    return

                try:
                    shard_context = await self._sr.retrieve_archival_shard(latest_ingress_signal)
                except Exception:
                    runtime_logger.exception("retrospective_logic_fault")
                    return

                if not shard_context:
                    return

                # Interpolate the archival shard prior to the ingress vector
                archival_signal = {"role": "system", "content": shard_context}
                manifest_signals.insert(ingress_vector_index, archival_signal)

        return _RetrospectiveShardProcessor(retriever)

    @property
    def processor(self) -> object:
        """Returns the active substrate logic processor instance."""
        return self._logic_processor


async def synthesize_initial_archival_context(
    db_session: AsyncSession,
    node_sig: UUID,
    node_alias: str = "",
) -> str | None:
    """Synthesizes a static archival shard context for the initial node manifest.

    Executed upon manifold initiation. Retrieves primary archival shards 
    using the node alias as the initial signal vector to pre-load 
    architectural background metadata.
    """
    from sqlalchemy import text as sa_text

    # Pre-flight check: verify if any shards are associated with the node signature
    shard_exists = await db_session.execute(
        sa_text(
            "SELECT 1 FROM agent_knowledge_bases WHERE agent_id = :node_sig LIMIT 1"
        ).bindparams(node_sig=node_sig)
    )
    if shard_exists.first() is None:
        runtime_logger.debug("skip_initial_archival_context_void", node_sig=str(node_sig))
        return None

    manifest_retriever = ArchivalManifestRetriever(agent_id=node_sig)

    # Use node alias to synthesize general background context
    initial_vector = f"What is {node_alias}?" if node_alias else "general architectural information"
    archival_shard = await manifest_retriever.retrieve_and_format(initial_vector)
    
    if archival_shard:
        runtime_logger.info(
            "initial_archival_context_synthesized",
            node_sig=str(node_sig),
            shard_mass=len(archival_shard),
        )
    return archival_shard
