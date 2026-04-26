"""Synchronisation Bridge — SignalStream substrate orchestration bridge.

Provides a synchronous-await interface for signal propagation cycles
to initiate outbound synchronisations and wait for state finalization.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.modules.calls.models import SignalSynchronisation as Synchronisation
from app.modules.calls.service import SynchronisationOrchestrator
from app.modules.pipeline.orchestrator import ManifoldGovernor

logger = structlog.get_logger(__name__)

# Terminal synchronisation phases
_TERMINAL_PHASES: frozenset[str] = frozenset(
    {
        "completed",
        "failed",
        "no_answer",
        "busy",
        "voicemail",
        "error",
    }
)

_POLL_INTERVAL_S: float = 2.0
_MAX_POLL_DURATION_S: int = 420  # Increased buffer for complex manifolds


class SynchronisationBridgeOrchestrator:
    """Architectural bridge for outbound signal synchronisations.

    Wraps the ManifoldGovernor to provide a blocking interface 
    required by propagation cycle workers.
    """

    @staticmethod
    async def initiate_outbound_synchronisation(
        db: AsyncSession,
        node_sig: UUID,
        nexus_sig: UUID,
        target_vector: str,
        origin_vector: str,
        dynamic_nodal_vectors: dict[str, Any] | None = None,
        architectural_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Initiate an outbound synchronisation and await final state manifestation."""
        log = logger.bind(
            node_sig=str(node_sig),
            nexus_sig=str(nexus_sig),
            target=target_vector,
        )

        # ── 1. Delegate to the substrate governor ──────────────────────
        governor = ManifoldGovernor(db)

        try:
            init_result = await governor.initiate_outbound_synchronisation(
                node_sig=node_sig,
                to_number=target_vector,
                from_number=origin_vector,
                nexus_sig=nexus_sig,
                dynamic_nodal_vectors=dynamic_nodal_vectors,
                architectural_metadata=architectural_metadata,
            )
        except Exception:
            log.exception("synchronisation_initiation_fault")
            return {
                "sync_sig": None,
                "state": "failed",
                "lexical_chronicle": [],
                "duration_s": 0,
                "termination_vector": "substrate_initialization_fault",
            }

        sync_sig_str = str(init_result["sync_sig"])
        sync_uuid = UUID(sync_sig_str)
        log = log.bind(sync_sig=sync_sig_str)
        log.info("synchronisation_cycle_ignited")

        # ── 2. Poll substrate for terminal state manifestation ──────────
        final_sync = await _poll_synchronisation_terminal_state(
            sync_sig=sync_uuid,
            max_duration=_MAX_POLL_DURATION_S,
            interval=_POLL_INTERVAL_S,
            log=log,
        )

        if final_sync is None:
            log.warning("synchronisation_poll_timeout")
            try:
                await SynchronisationOrchestrator.synchronize_operational_state(
                    session_store=db,
                    sync_sig=sync_uuid,
                    phase="failed",
                    termination_vector="bridge_poll_timeout",
                )
                await db.commit()
            except Exception:
                log.exception("synchronisation_timeout_update_failed")

            return {
                "sync_sig": sync_sig_str,
                "state": "failed",
                "lexical_chronicle": [],
                "duration_s": 0,
                "termination_vector": "bridge_poll_timeout",
            }

        # ── 3. Return structural result for propagation nexus ───────────
        log.info(
            "synchronisation_cycle_quiesced",
            phase=final_sync.phase,
            duration=final_sync.duration_s,
        )

        return {
            "sync_sig": sync_sig_str,
            "state": final_sync.phase,
            "lexical_chronicle": final_sync.lexical_chronicle or [],
            "extracted_data": final_sync.extracted_data or {},
            "duration_s": final_sync.duration_s or 0,
            "termination_vector": final_sync.termination_vector,
        }


async def _poll_synchronisation_terminal_state(
    sync_sig: UUID,
    max_duration: int,
    interval: float,
    log: Any,
) -> Synchronisation | None:
    """Poll the synchronisation registry until terminal state is achieved."""
    elapsed: float = 0.0

    while elapsed < max_duration:
        await asyncio.sleep(interval)
        elapsed += interval

        try:
            async with async_session_factory() as poll_db:
                result = await poll_db.execute(
                    select(Synchronisation).where(Synchronisation.id == sync_sig)
                )
                sync = result.scalar_one_or_none()

                if sync is None:
                    log.error("synchronisation_record_missing")
                    return None

                if sync.phase in _TERMINAL_PHASES:
                    return sync

        except Exception:
            log.exception("synchronisation_poll_fault", elapsed=elapsed)
            continue

    return None
