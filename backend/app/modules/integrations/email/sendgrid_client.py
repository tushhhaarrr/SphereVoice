"""SendGrid email client — sends transactional emails via the SendGrid v3 API.

Uses httpx for async HTTP calls. Requires a SendGrid API key.
Credentials are fetched from the tenant's TenantIntegration record
(provider='sendgrid') or from env vars as fallback.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

SENDGRID_API_BASE = "https://api.sendgrid.com/v3"

# Simple email regex for validation
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class SendGridClient:
    """Async client for the SendGrid v3 Mail Send API."""

    def __init__(self, *, api_key: str, default_from_email: str = "") -> None:
        self._api_key = api_key
        self._default_from_email = default_from_email

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def send_email(
        self,
        *,
        to_email: str,
        subject: str,
        body_text: str = "",
        body_html: str = "",
        from_email: str = "",
        from_name: str = "SphereVoice Agent",
        reply_to: str = "",
    ) -> dict[str, Any]:
        """Send a single email via SendGrid.

        Args:
            to_email: Recipient address.
            subject: Email subject line.
            body_text: Plain text body.
            body_html: HTML body (optional, takes precedence for rich content).
            from_email: Sender address (falls back to default_from_email).
            from_name: Sender display name.
            reply_to: Reply-to address (optional).

        Returns:
            Dict with delivery status and message_id.
        """
        sender = from_email or self._default_from_email
        if not sender:
            raise SendGridError("No from_email provided and no default configured")

        if not _EMAIL_RE.match(to_email):
            raise SendGridError(f"Invalid recipient email: {to_email}")

        if not _EMAIL_RE.match(sender):
            raise SendGridError(f"Invalid sender email: {sender}")

        content: list[dict[str, str]] = []
        if body_text:
            content.append({"type": "text/plain", "value": body_text})
        if body_html:
            content.append({"type": "text/html", "value": body_html})
        if not content:
            # Fall back to a minimal plain text body
            content.append({"type": "text/plain", "value": "(no content)"})

        payload: dict[str, Any] = {
            "personalizations": [
                {"to": [{"email": to_email}]},
            ],
            "from": {"email": sender, "name": from_name},
            "subject": subject,
            "content": content,
        }

        if reply_to and _EMAIL_RE.match(reply_to):
            payload["reply_to"] = {"email": reply_to}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{SENDGRID_API_BASE}/mail/send",
                headers=self._headers(),
                json=payload,
            )

        # SendGrid returns 202 Accepted on success (no body)
        if resp.status_code not in (200, 202):
            logger.error(
                "sendgrid_send_failed",
                status=resp.status_code,
                body=resp.text[:500],
                to=to_email,
            )
            raise SendGridError(
                f"SendGrid API error ({resp.status_code}): {resp.text[:200]}"
            )

        # Extract message ID from X-Message-Id header
        message_id = resp.headers.get("X-Message-Id", "unknown")
        logger.info(
            "sendgrid_email_sent",
            to=to_email,
            subject=subject,
            message_id=message_id,
        )
        return {
            "message_id": message_id,
            "status": "sent",
            "to": to_email,
            "subject": subject,
        }


class SendGridError(Exception):
    """Raised when a SendGrid API call fails."""
