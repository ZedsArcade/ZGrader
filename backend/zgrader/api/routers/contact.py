"""The public contact form.

Unauthenticated and therefore the most exposed write endpoint in the app, so
it carries three separate defences rather than one: a per-IP rate limit, a
honeypot field, and hard length caps in the schema.

The ordering of the two things it does matters. The enquiry is committed
*before* the notification email is attempted, so a message can never be
accepted, reported as sent, and then lost because SMTP was unreachable -- which
is the state the deployment is actually in today (see the known-open list in
AGENTS.md). The email is a convenience layered on top of a durable row.
"""

import logging

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from zgrader.api.ratelimit import client_ip, rate_limit
from zgrader.db import get_db
from zgrader.email.notifications import send_contact_message
from zgrader.models import ContactMessage
from zgrader.models.settings import get_or_create_settings
from zgrader.schemas.contact import ContactMessageRequest, ContactMessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contact", tags=["contact"])

# Looser than the password-reset limits next door, because a person with a
# genuine question may well send two -- and tighter than registration, because
# unlike registration there is no confirmation step to absorb a mistake.
contact_rate_limit = rate_limit("contact", limit=5, window_seconds=3600)


@router.post(
    "/messages",
    response_model=ContactMessageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(contact_rate_limit)],
)
def create_contact_message(
    payload: ContactMessageRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ContactMessageResponse:
    if payload.website:
        # Honeypot tripped. Returns the same 201 a real submission gets and
        # stores nothing: telling a bot it was detected only teaches whoever
        # wrote it which field to leave alone next time. Logged so a sudden
        # flood is visible rather than silent.
        logger.info("Contact form honeypot tripped from %s", client_ip(request))
        return ContactMessageResponse()

    message = ContactMessage(
        name=payload.name,
        email=str(payload.email).lower(),
        topic=payload.topic,
        subject=payload.subject,
        message=payload.message,
        language=payload.language if payload.language in ("en", "es") else "en",
        submission_code=payload.submission_code,
        client_ip=client_ip(request),
    )
    db.add(message)
    # Committed before the email is attempted, and separately from the
    # `notified` update below: if the SMTP attempt hangs until the worker is
    # killed, the enquiry is already durable.
    db.commit()
    db.refresh(message)

    settings = get_or_create_settings(db)
    if send_contact_message(message, settings):
        message.notified = True
        db.commit()

    return ContactMessageResponse()
