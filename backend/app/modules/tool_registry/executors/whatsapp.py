"""WhatsApp executor — sends a WhatsApp message via the Meta Cloud API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from app.modules.tool_registry.models import TenantTool

logger = structlog.get_logger(__name__)


class WhatsAppExecutor:
    """Execute a messaging tool by sending a WhatsApp message.

    The tool's ``execution_config`` may contain:
    - ``to_field``: name of the argument that holds the recipient number
                    (default: ``"to"``)
    - ``message_field``: name of the argument that holds the message body
                         (default: ``"message"``)

    Credentials are resolved in this order:
    1. TenantIntegration linked via ``tool.integration_id``
    2. Env vars: WHATSAPP_ACCESS_TOKEN + WHATSAPP_PHONE_NUMBER_ID
    """

    async def execute(
        self,
        tool: "TenantTool",
        arguments: dict[str, Any],
        call_context: dict[str, Any],
    ) -> dict[str, Any]:
        config: dict[str, Any] = tool.execution_config or {}
        to_field: str = config.get("to_field", "to")
        message_field: str = config.get("message_field", "message")

        recipient: str = arguments.get(to_field, "")
        message_body: str = arguments.get(message_field, "")

        if not recipient or not message_body:
            logger.warning(
                "whatsapp_missing_args",
                tool_name=tool.name,
                args=list(arguments.keys()),
            )
            return {
                "success": False,
                "error": "recipient or message body missing",
                "tool": tool.name,
            }

        # Resolve credentials
        access_token, phone_number_id = await self._resolve_credentials(
            tool, call_context
        )
        if not access_token or not phone_number_id:
            logger.warning(
                "whatsapp_no_credentials",
                tool_name=tool.name,
                call_id=call_context.get("call_id"),
            )
            return {
                "success": False,
                "error": "WhatsApp integration not configured — no credentials found",
                "tool": tool.name,
            }

        try:
            from app.modules.integrations.messaging.whatsapp_client import (
                WhatsAppClient,
            )

            client = WhatsAppClient(
                access_token=access_token,
                phone_number_id=phone_number_id,
            )

            result = await client.send_text_message(
                to_phone=recipient,
                text=message_body,
            )

            logger.info(
                "whatsapp_message_sent",
                tool_name=tool.name,
                to=recipient,
                message_id=result.get("message_id"),
                call_id=call_context.get("call_id"),
            )

            return {
                "success": True,
                "to": recipient,
                "message_id": result.get("message_id"),
                "tool": tool.name,
                "status": "sent",
            }

        except Exception as exc:
            logger.exception(
                "whatsapp_send_error",
                tool_name=tool.name,
                to=recipient,
                error=str(exc),
            )
            return {
                "success": False,
                "error": f"Failed to send WhatsApp message: {exc}",
                "tool": tool.name,
            }

    async def _resolve_credentials(
        self,
        tool: "TenantTool",
        call_context: dict[str, Any],
    ) -> tuple[str, str]:
        """Resolve WhatsApp credentials from integration or env vars.

        Returns:
            (access_token, phone_number_id) tuple. Empty strings if not found.
        """
        # 1. Try integration linked to the tool
        if tool.integration_id:
            try:
                from sqlalchemy import select

                from app.core.database import async_session_factory
                from app.core.encryption import decrypt
                from app.modules.integrations.models import TenantIntegration

                tenant_id = call_context.get("tenant_id")
                async with async_session_factory() as db:
                    query = select(TenantIntegration).where(
                        TenantIntegration.id == tool.integration_id,
                    )
                    if tenant_id:
                        query = query.where(
                            TenantIntegration.tenant_id == tenant_id
                        )
                    result = await db.execute(query)
                    integration = result.scalar_one_or_none()

                    if integration and integration.access_token_encrypted:
                        token = decrypt(integration.access_token_encrypted)
                        config = integration.config or {}
                        phone_id = config.get("phone_number_id", "")
                        if token and phone_id:
                            return token, phone_id
            except Exception:
                logger.debug(
                    "whatsapp_integration_lookup_failed",
                    tool_id=str(tool.id),
                    exc_info=True,
                )

        # 2. Fallback to env vars
        from app.core.config import get_settings

        settings = get_settings()
        return settings.WHATSAPP_ACCESS_TOKEN, settings.WHATSAPP_PHONE_NUMBER_ID
