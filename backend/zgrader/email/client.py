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


def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an email. Returns whether it actually went out.

    The return value is new and most callers still ignore it, which is correct
    for the notification emails -- there is nothing useful to do when a
    "your report is ready" message fails. The contact form is the exception:
    it records delivery against the stored enquiry, so the operator can tell
    which messages they were emailed about and which are sitting unread in the
    table because SMTP was down.
    """
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.smtp_from
    message["To"] = to
    message.set_content("This email requires an HTML-capable client to view.")
    message.add_alternative(html_body, subtype="html")

    # SMTP_SSL wraps the socket in TLS before the first byte; SMTP starts in
    # the clear and optionally upgrades. Port 465 only ever speaks the former,
    # 587 the latter -- which is why these are alternatives rather than two
    # flags that stack. config._warn_about_unusable_smtp says so at boot when
    # the pair is set to a combination that cannot work.
    #
    # `timeout` matters more than it looks: without it a filtered port (an ISP
    # dropping outbound 25 is the usual cause) leaves the connection hanging
    # with no error, and every caller of this blocks behind it.
    try:
        if config.smtp_implicit_tls:
            connection = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=10)
        else:
            connection = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10)
        with connection as smtp:
            if config.smtp_use_tls and not config.smtp_implicit_tls:
                smtp.starttls()
            if config.smtp_user and config.smtp_password:
                smtp.login(config.smtp_user, config.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        logger.warning("Failed to send email to %s (%s): %s", to, subject, exc)
        return False
    return True
