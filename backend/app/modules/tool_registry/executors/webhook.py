"""Webhook executor — HTTP POST to a caller-configured URL."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx
import structlog

if TYPE_CHECKING:
    from app.modules.tool_registry.models import TenantTool

logger = structlog.get_logger(__name__)

_DEFAULT_TIMEOUT = 10.0  # seconds


class WebhookExecutor:
    """Execute a tool by POSTing to a webhook URL."""

    async def call(
        self,
        tool: "TenantTool",
        arguments: dict[str, Any],
        call_context: dict[str, Any],
    ) -> dict[str, Any]:
        """POST arguments + call_context to the configured webhook URL.

        Returns the parsed JSON response body, or a ``{"error": ...}`` dict on
        network / HTTP errors so the LLM can handle gracefully.
        """
        config: dict[str, Any] = tool.execution_config or {}
        url: str = config.get("url", "")
        headers: dict[str, str] = config.get("headers", {})
        timeout: float = float(config.get("timeout_seconds", _DEFAULT_TIMEOUT))

        if not url:
            logger.warning(
                "webhook_missing_url",
                tool_id=str(tool.id),
                tool_name=tool.name,
            )
            return {"error": "webhook URL not configured", "tool": tool.name}

        payload: dict[str, Any] = {
            "tool": tool.name,
            "arguments": arguments,
            "context": call_context,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json", **headers},
                )
                response.raise_for_status()
                try:
                    result: dict[str, Any] = response.json()
                except Exception:
                    result = {"raw": response.text}
                logger.info(
                    "webhook_executed",
                    tool_name=tool.name,
                    status=response.status_code,
                )
                return result
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "webhook_http_error",
                tool_name=tool.name,
                status=exc.response.status_code,
                body=exc.response.text[:200],
            )
            return {
                "error": f"HTTP {exc.response.status_code}",
                "tool": tool.name,
            }
        except httpx.RequestError as exc:
            logger.warning(
                "webhook_request_error",
                tool_name=tool.name,
                error=str(exc),
            )
            return {"error": str(exc), "tool": tool.name}
