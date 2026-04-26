"""WhatsApp Cloud API client — sends messages via Meta Business Platform.

Supports text messages and template messages.
Requires a Meta Business access token and phone number ID.

Credentials are fetched from the tenant's TenantIntegration record
(provider='whatsapp') or from env vars as fallback.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


class WhatsAppClient:
    """HTTP client for Meta WhatsApp Cloud API."""

    def __init__(
        self,
        *,
        access_token: str,
        phone_number_id: str,
        api_version: str = "v21.0",
    ) -> None:
        self._access_token = access_token
        self._phone_number_id = phone_number_id
        self._base_url = f"https://graph.facebook.com/{api_version}/{phone_number_id}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    async def send_text_message(
        self,
        to_phone: str,
        text: str,
    ) -> dict[str, Any]:
        """Send a plain text message.

        Args:
            to_phone: Recipient phone number in E.164 format (no + prefix for Meta API).
            text: Message body text.

        Returns:
            Meta API response with message ID and status.
        """
        # Strip the leading '+' if present — Meta expects digits only
        clean_phone = to_phone.lstrip("+")

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "text",
            "text": {"body": text},
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._base_url}/messages",
                headers=self._headers(),
                json=payload,
            )

        if resp.status_code >= 400:
            logger.error(
                "whatsapp_send_failed",
                status=resp.status_code,
                body=resp.text[:500],
                to=clean_phone,
            )
            raise WhatsAppError(
                f"WhatsApp API error ({resp.status_code}): {resp.text[:200]}"
            )

        data = resp.json()
        message_id = (data.get("messages") or [{}])[0].get("id", "unknown")
        logger.info(
            "whatsapp_text_sent",
            to=clean_phone,
            message_id=message_id,
        )
        return {
            "message_id": message_id,
            "status": "sent",
            "to": clean_phone,
        }

    async def send_template_message(
        self,
        to_phone: str,
        template_name: str,
        language_code: str = "en",
        parameters: list[str] | None = None,
    ) -> dict[str, Any]:
        """Send a pre-approved template message.

        Args:
            to_phone: Recipient phone in E.164 format.
            template_name: Name of the approved template in Meta Business Manager.
            language_code: Template language code (default: 'en').
            parameters: List of string values to fill template placeholders.

        Returns:
            Meta API response with message ID.
        """
        clean_phone = to_phone.lstrip("+")

        template_payload: dict[str, Any] = {
            "name": template_name,
            "language": {"code": language_code},
        }

        if parameters:
            template_payload["components"] = [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": p} for p in parameters
                    ],
                }
            ]

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "template",
            "template": template_payload,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._base_url}/messages",
                headers=self._headers(),
                json=payload,
            )

        if resp.status_code >= 400:
            logger.error(
                "whatsapp_template_send_failed",
                status=resp.status_code,
                body=resp.text[:500],
                to=clean_phone,
                template=template_name,
            )
            raise WhatsAppError(
                f"WhatsApp API error ({resp.status_code}): {resp.text[:200]}"
            )

        data = resp.json()
        message_id = (data.get("messages") or [{}])[0].get("id", "unknown")
        logger.info(
            "whatsapp_template_sent",
            to=clean_phone,
            template=template_name,
            message_id=message_id,
        )
        return {
            "message_id": message_id,
            "status": "sent",
            "to": clean_phone,
            "template": template_name,
        }


class WhatsAppError(Exception):
    """Raised when a WhatsApp Cloud API call fails."""
