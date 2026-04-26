"""Async email sending via SMTP.

Sends transactional emails (invite, etc.) through any
standard SMTP provider (Gmail, Mailgun, SendGrid SMTP, etc.).

When ``EMAIL_ENABLED=false`` (the default) the link is only
logged to stdout — useful for local development without a
real SMTP server.
"""

from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


async def send_invite_email(
    *,
    to_email: str,
    to_name: str | None,
    invite_link: str,
    role: str,
) -> bool:
    """Send an invitation email.

    Returns ``True`` if the email was dispatched, ``False`` if email is
    disabled (development mode) or if sending failed.
    """
    from app.core.config import get_settings

    settings = get_settings()

    if not settings.EMAIL_ENABLED:
        logger.info(
            "EMAIL_ENABLED=false — invite link for %s: %s", to_email, invite_link
        )
        return False

    try:
        import aiosmtplib
    except ImportError:
        logger.error(
            "aiosmtplib is not installed; cannot send email. "
            "Add aiosmtplib to requirements.txt and reinstall."
        )
        return False

    app_name = settings.APP_NAME
    role_display = role.replace("_", " ").title()
    greeting = f"Hi {to_name}," if to_name else "Hello,"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 16px;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;padding:40px;box-shadow:0 1px 3px rgba(0,0,0,.08);">
        <tr><td>
          <h1 style="margin:0 0 4px;font-size:22px;font-weight:700;color:#09090b;">
            You're invited to {app_name}
          </h1>
          <p style="margin:0 0 24px;color:#71717a;font-size:14px;">Voice AI Agent Platform</p>
          <p style="margin:0 0 20px;color:#3f3f46;font-size:15px;line-height:1.6;">
            {greeting}<br><br>
            You've been invited to join <strong>{app_name}</strong> with the
            <strong>{role_display}</strong> role. Click the button below to set up
            your account.
          </p>
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr><td align="center" style="padding:8px 0 28px;">
              <a href="{invite_link}"
                 style="display:inline-block;background:#18181b;color:#fff;text-decoration:none;
                        padding:13px 32px;border-radius:8px;font-size:15px;font-weight:600;
                        letter-spacing:.01em;">
                Accept Invitation
              </a>
            </td></tr>
          </table>
          <p style="margin:0;color:#a1a1aa;font-size:13px;text-align:center;">
            This link expires in 72 hours.<br>
            If you didn't expect this invitation, you can safely ignore this email.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    text_body = (
        f"{greeting}\n\n"
        f"You've been invited to join {app_name} as a {role_display}.\n\n"
        f"Accept your invitation:\n{invite_link}\n\n"
        f"This link expires in 72 hours. If you didn't expect this, ignore this email."
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"You're invited to {app_name}"
    from_name = settings.EMAIL_FROM_NAME or app_name
    msg["From"] = f"{from_name} <{settings.EMAIL_FROM_ADDRESS}>"
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME or None,
            password=settings.SMTP_PASSWORD or None,
            use_tls=settings.SMTP_USE_TLS,
            start_tls=settings.SMTP_START_TLS,
            # Suppress the "Connection lost" noise Resend emits after delivery
            timeout=30,
        )
        logger.info("invite_email_sent: to=%s", to_email)
        return True
    except aiosmtplib.SMTPServerDisconnected:
        # Resend closes the connection immediately after accepting the message;
        # delivery succeeded — this exception is just a clean-up artefact.
        logger.info("invite_email_sent (server closed early): to=%s", to_email)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("invite_email_failed: to=%s error=%s", to_email, exc)
        return False
