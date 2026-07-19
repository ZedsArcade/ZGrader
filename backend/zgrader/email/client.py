"""SMTP sending, deliberately resilient: a notification failure (SMTP
unreachable, bad credentials, etc.) must never break the submission-creation
or report-publish flow it's attached to, so failures are logged and
swallowed here rather than propagated.
"""

import logging
import smtplib
from email.message import EmailMessage

from zgrader.config import config

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html_body: str) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.smtp_from
    message["To"] = to
    message.set_content("This email requires an HTML-capable client to view.")
    message.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10) as smtp:
            if config.smtp_use_tls:
                smtp.starttls()
            if config.smtp_user and config.smtp_password:
                smtp.login(config.smtp_user, config.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        logger.warning("Failed to send email to %s (%s): %s", to, subject, exc)
