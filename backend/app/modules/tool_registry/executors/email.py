"""Email executor — sends an email via SendGrid during live calls."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from app.modules.tool_registry.models import TenantTool

logger = structlog.get_logger(__name__)


class EmailExecutor:
    """Execute an email tool by sending via SendGrid.

    The tool's ``execution_config`` may contain:
    - ``to_field``: argument name for the recipient address (default: ``"to"``)
    - ``subject_field``: argument name for the email subject (default: ``"subject"``)
    - ``body_field``: argument name for the email body (default: ``"body"``)
    - ``from_address``: sender address override

    Credentials are resolved in this order:
    1. TenantIntegration linked via ``tool.integration_id``
    2. Env vars: SENDGRID_API_KEY + SENDGRID_DEFAULT_FROM_EMAIL
    """

    async def execute(
        self,
        tool: "TenantTool",
        arguments: dict[str, Any],
        call_context: dict[str, Any],
    ) -> dict[str, Any]:
        config: dict[str, Any] = tool.execution_config or {}
        to_field: str = config.get("to_field", "to")
        subject_field: str = config.get("subject_field", "subject")
        body_field: str = config.get("body_field", "body")
        from_address: str = config.get("from_address", "")

        recipient: str = arguments.get(to_field, "")
        subject: str = arguments.get(subject_field, "(no subject)")
        body: str = arguments.get(body_field, "")

        if not recipient:
            logger.warning(
                "email_missing_recipient",
                tool_name=tool.name,
                args=list(arguments.keys()),
            )
            return {
                "success": False,
                "error": "recipient address missing",
                "tool": tool.name,
            }

        # Resolve credentials
        api_key, default_from = await self._resolve_credentials(
            tool, call_context
        )
        if not api_key:
            logger.warning(
                "email_no_credentials",
                tool_name=tool.name,
                call_id=call_context.get("call_id"),
            )
            return {
                "success": False,
                "error": "Email integration not configured — no SendGrid API key",
                "tool": tool.name,
            }

        sender = from_address or default_from
        if not sender:
            return {
                "success": False,
                "error": "No sender email configured",
                "tool": tool.name,
            }

        try:
            from app.modules.integrations.email.sendgrid_client import (
                SendGridClient,
            )

            client = SendGridClient(
                api_key=api_key,
                default_from_email=sender,
            )

            result = await client.send_email(
                to_email=recipient,
                subject=subject,
                body_text=body,
                from_email=sender,
            )

            logger.info(
                "email_sent",
                tool_name=tool.name,
                to=recipient,
                subject=subject,
                message_id=result.get("message_id"),
                call_id=call_context.get("call_id"),
            )

            return {
                "success": True,
                "to": recipient,
                "subject": subject,
                "message_id": result.get("message_id"),
                "tool": tool.name,
                "status": "sent",
            }

        except Exception as exc:
            logger.exception(
                "email_send_error",
                tool_name=tool.name,
                to=recipient,
                error=str(exc),
            )
            return {
                "success": False,
                "error": f"Failed to send email: {exc}",
                "tool": tool.name,
            }

    async def _resolve_credentials(
        self,
        tool: "TenantTool",
        call_context: dict[str, Any],
    ) -> tuple[str, str]:
        """Resolve SendGrid credentials from integration or env vars.

        Returns:
            (api_key, default_from_email) tuple. Empty strings if not found.
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
                        api_key = decrypt(integration.access_token_encrypted)
                        config = integration.config or {}
                        from_email = config.get("from_email", "")
                        if api_key:
                            return api_key, from_email
            except Exception:
                logger.debug(
                    "email_integration_lookup_failed",
                    tool_id=str(tool.id),
                    exc_info=True,
                )

        # 2. Fallback to env vars
        from app.core.config import get_settings

        settings = get_settings()
        return settings.SENDGRID_API_KEY, settings.SENDGRID_DEFAULT_FROM_EMAIL
