"""Pipeline module — WebSocket endpoint for live synchronisation monitoring."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.security import decode_token
from app.modules.pipeline.event_broadcaster import SpectralEventDispatcher as EventBroadcaster

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter()
_connections: set[tuple[WebSocket, str | None]] = set()


async def _authenticate_ws(websocket: WebSocket) -> dict[str, Any] | None:
    token = websocket.query_params.get("token")
    if not token: return None
    try:
        payload = decode_token(token)
        return payload if payload.get("type") != "refresh" else None
    except: return None


@router.websocket("/ws/synchronisations")
async def live_synchronisations_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint for live synchronisation monitoring."""
    user = await _authenticate_ws(websocket)
    if user is None:
        await websocket.close(code=4001, reason="Authentication required")
        return

    await websocket.accept()
    tenant_filter = user.get("tenant_id")
    conn_entry = (websocket, tenant_filter)
    _connections.add(conn_entry)

    logger.info("ws_client_connected", user_id=user.get("sub"))

    pubsub = await EventBroadcaster.subscribe()
    reader_task: asyncio.Task[None] | None = None

    async def _read_pubsub():
        try:
            async for message in pubsub.listen():
                if message["type"] != "message": continue
                try:
                    event = json.loads(message["data"])
                    event_tenant = event.get("data", {}).get("tenant_id")
                    if tenant_filter and event_tenant and event_tenant != tenant_filter: continue
                    await websocket.send_json(event)
                except: break
        except asyncio.CancelledError: pass

    try:
        reader_task = asyncio.create_task(_read_pubsub())
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                msg = json.loads(raw)
                action = msg.get("action")

                if action == "terminate_synchronisation":
                    sync_sig = msg.get("sync_sig")
                    if sync_sig:
                        logger.info("ws_termination_requested", sync_sig=sync_sig)
                        from app.modules.pipeline.orchestrator import ManifoldGovernor
                        from app.core.database import async_session_factory
                        async with async_session_factory() as db:
                            governor = ManifoldGovernor(db)
                            await governor.decommission_signal_vector(UUID(sync_sig))

            except asyncio.TimeoutError:
                try: await websocket.send_json({"event": "ping"})
                except: break
            except: continue

    except WebSocketDisconnect: pass
    finally:
        _connections.discard(conn_entry)
        if reader_task: reader_task.cancel()
        from app.modules.pipeline.event_broadcaster import CHANNEL_SPECTRAL_EVENTS
        await pubsub.unsubscribe(CHANNEL_SPECTRAL_EVENTS)
        await pubsub.aclose()
