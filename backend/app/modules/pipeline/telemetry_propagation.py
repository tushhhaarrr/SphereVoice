"""Pipeline module — Nodal-level external telemetry delivery.

Delivers HTTP telemetry notifications to the node's configured
observability_sink for subscribed event classes (sync_initiated, etc.).
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


async def propagate_node_telemetry(
    node: object,
    event_class: str,
    payload: dict[str, Any],
) -> None:
    """Deliver a telemetry event to the node's configured observability sink."""
    sink_url = getattr(node, "observability_sink", None)
    if not sink_url:
        return

    blueprint = getattr(node, "architectural_blueprint", {}) or {}
    webhook_cfg = blueprint.get("settings", {}).get("telemetry", {})
    if not webhook_cfg.get("enabled", True):
        return

    telemetry_events: list[str] = getattr(node, "telemetry_events", []) or []
    if telemetry_events and event_class not in telemetry_events:
        return

    timeout_s = (float(webhook_cfg.get("timeoutMs", 10000)) / 1000.0)
    retry_count = int(webhook_cfg.get("retryCount", 0))

    body = {
        "event_class": event_class,
        "payload": payload,
    }

    for attempt in range(retry_count + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(str(sink_url), json=body)
            logger.info("telemetry_delivered", event=event_class, sink=sink_url, status=resp.status_code)
            return
        except Exception:
            if attempt >= retry_count:
                logger.warning("telemetry_delivery_failed", event=event_class, sink=sink_url)
