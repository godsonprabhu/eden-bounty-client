"""Minimal transactional email sender for invitation and password-reset links.

Uses the SMTP settings from ``app.core.config`` (implicit TLS on port 465 by default). The
configuration guard forces ``SMTP_ENABLED`` off outside verified production, so development and
tests never send mail. Message bodies contain one-time links and are therefore never logged.
"""

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def email_delivery_available() -> bool:
    return bool(settings.SMTP_ENABLED and settings.SMTP_USER and settings.SMTP_PASSWORD)


def _send_blocking(message: EmailMessage) -> None:
    context = ssl.create_default_context()
    if settings.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context, timeout=20) as client:
            client.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            client.send_message(message)
    else:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as client:
            client.starttls(context=context)
            client.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            client.send_message(message)


async def send_email(to: str, subject: str, body: str) -> bool:
    """Sends a plain-text email. Returns False (and logs without content) on failure."""
    if not email_delivery_available():
        return False
    message = EmailMessage()
    message["From"] = settings.SMTP_USER
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        await asyncio.to_thread(_send_blocking, message)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        logger.error("Transactional email could not be sent (%s)", type(exc).__name__)
        return False
