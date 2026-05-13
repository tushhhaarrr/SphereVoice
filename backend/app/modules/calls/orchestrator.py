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
from app.modules.calls.models import VoiceEngine
from app.modules.calls.service import VoiceEngineService
from app.modules.pipeline.orchestrator import ManifoldGovernor

logger = structlog.get_logger(__name__)

# Terminal call statuses
_TERMINAL_STATUSES: frozenset[str] = frozenset(
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


class CallBridgeOrchestrator:
    """Architectural bridge for outbound calls.

    Wraps the ManifoldGovernor to provide a blocking interface 
    required by campaign workers.
    """

    @staticmethod
    async def initiate_outbound_call(
        db: AsyncSession,
        agent_id: UUID,
        tenant_id: UUID,
        to_number: str,
        from_number: str,
        dynamic_variables: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Initiate an outbound call and await final state."""
        log = logger.bind(
            agent_id=str(agent_id),
            tenant_id=str(tenant_id),
            to_number=to_number,
        )

        # ── 1. Delegate to the substrate governor ──────────────────────
        governor = ManifoldGovernor(db)

        try:
            init_result = await governor.initiate_outbound_synchronisation(
                node_sig=agent_id,
                to_number=to_number,
                from_number=from_number,
                nexus_sig=tenant_id,
                dynamic_nodal_vectors=dynamic_variables,
                architectural_metadata=metadata,
            )
        except Exception:
            log.exception("call_initiation_fault")
            return {
                "call_id": None,
                "status": "failed",
                "transcript": [],
                "duration": 0,
                "disposition": "substrate_initialization_fault",
            }

        call_id_str = str(init_result["sync_sig"])
        call_uuid = UUID(call_id_str)
        log = log.bind(call_id=call_id_str)
        log.info("call_cycle_ignited")

        # ── 2. Poll substrate for terminal state manifestation ──────────
        final_call = await _poll_call_terminal_state(
            call_id=call_uuid,
            max_duration=_MAX_POLL_DURATION_S,
            interval=_POLL_INTERVAL_S,
            log=log,
        )

        if final_call is None:
            log.warning("call_poll_timeout")
            try:
                await VoiceEngineService.update_call(
                    session_store=db,
                    call_id=call_uuid,
                    status="failed",
                    disposition="bridge_poll_timeout",
                )
                await db.commit()
            except Exception:
                log.exception("call_timeout_update_failed")

            return {
                "call_id": call_id_str,
                "status": "failed",
                "transcript": [],
                "duration": 0,
                "disposition": "bridge_poll_timeout",
            }

        # ── 3. Return structural result for campaign worker ───────────
        log.info(
            "call_cycle_quiesced",
            status=final_call.status,
            duration=final_call.duration,
        )

        return {
            "call_id": call_id_str,
            "status": final_call.status,
            "transcript": final_call.transcript or [],
            "extracted_data": final_call.summary or {},
            "duration": final_call.duration or 0,
            "disposition": final_call.disposition,
        }


async def _poll_call_terminal_state(
    call_id: UUID,
    max_duration: int,
    interval: float,
    log: Any,
) -> VoiceEngine | None:
    """Poll the call registry until terminal state is achieved."""
    elapsed: float = 0.0

    while elapsed < max_duration:
        await asyncio.sleep(interval)
        elapsed += interval

        try:
            async with async_session_factory() as poll_db:
                result = await poll_db.execute(
                    select(VoiceEngine).where(VoiceEngine.id == call_id)
                )
                call = result.scalar_one_or_none()

                if call is None:
                    log.error("call_record_missing")
                    return None

                if call.status in _TERMINAL_STATUSES:
                    return call

        except Exception:
            log.exception("call_poll_fault", elapsed=elapsed)
            continue

    return None
