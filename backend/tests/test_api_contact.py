"""The public contact form.

The behaviour worth pinning down is not "a valid message is accepted" -- it is
that a message survives an SMTP failure, because that is the state the
deployment is actually in. An email-only contact form would return 201 and
lose the enquiry, and nothing about the response would say so.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from zgrader.api.main import app
from zgrader.models import ContactMessage, ContactTopic
from zgrader.models.settings import get_or_create_settings

client = TestClient(app)

VALID = {
    "name": "Ada Lovelace",
    "email": "Ada@Example.COM",
    "topic": "care",
    "subject": "Is this card safe to clean?",
    "message": "It has a light smudge on the front. Should I leave it alone?",
    "language": "en",
}


def test_message_is_stored_even_when_the_email_fails(db_session):
    """The whole reason the table exists.

    send_email swallows SMTP errors and returns False, which is exactly what
    happens on the live deployment today. The row must still be there.

    The operator address has to be configured for this to test anything:
    without it send_contact_message returns False before it ever reaches SMTP,
    and the assertion below would pass without the failure path running.
    """
    settings = get_or_create_settings(db_session)
    settings.contact_email = "operator@example.com"
    db_session.commit()

    with patch("zgrader.email.client.smtplib.SMTP", side_effect=OSError("no smtp")):
        resp = client.post("/contact/messages", json=VALID)

    assert resp.status_code == 201
    assert resp.json() == {"received": True}

    stored = db_session.query(ContactMessage).one()
    assert stored.subject == "Is this card safe to clean?"
    assert stored.topic is ContactTopic.care
    # Lowercased on the way in, like every other address in the system.
    assert stored.email == "ada@example.com"
    # The operator was never told, and the row says so rather than implying
    # a message that was read.
    assert stored.notified is False


def test_successful_delivery_is_recorded(db_session):
    settings = get_or_create_settings(db_session)
    settings.contact_email = "operator@example.com"
    db_session.commit()

    with patch("zgrader.email.notifications.send_email", return_value=True) as send:
        resp = client.post("/contact/messages", json=VALID)

    assert resp.status_code == 201
    assert send.call_count == 1
    assert send.call_args.args[0] == "operator@example.com"
    assert db_session.query(ContactMessage).one().notified is True


def test_no_contact_address_configured_still_stores_the_message(db_session):
    """No operator address is not an error -- there is simply nowhere to send
    a notification, and the row is read in the admin panel instead."""
    resp = client.post("/contact/messages", json=VALID)

    assert resp.status_code == 201
    stored = db_session.query(ContactMessage).one()
    assert stored.notified is False


def test_honeypot_is_accepted_and_discarded(db_session):
    """Returns the same 201 a real message gets.

    Rejecting it with an error would tell whoever wrote the bot which field to
    leave alone next time, so the response must be indistinguishable.
    """
    resp = client.post("/contact/messages", json={**VALID, "website": "http://spam.example"})

    assert resp.status_code == 201
    assert resp.json() == {"received": True}
    assert db_session.query(ContactMessage).count() == 0


def test_whitespace_only_fields_are_rejected(db_session):
    """min_length counts characters, so a subject of five spaces passes it and
    then renders as an empty line in the operator's inbox."""
    resp = client.post("/contact/messages", json={**VALID, "subject": "     "})

    assert resp.status_code == 422
    assert db_session.query(ContactMessage).count() == 0


def test_blank_submission_code_is_stored_as_null(db_session):
    """An untouched optional field arrives as "", which is not a code."""
    resp = client.post("/contact/messages", json={**VALID, "submission_code": "   "})

    assert resp.status_code == 201
    assert db_session.query(ContactMessage).one().submission_code is None


def test_unknown_language_falls_back_rather_than_rejecting(db_session):
    resp = client.post("/contact/messages", json={**VALID, "language": "zz"})

    assert resp.status_code == 201
    assert db_session.query(ContactMessage).one().language == "en"


def test_message_must_have_some_substance(db_session):
    resp = client.post("/contact/messages", json={**VALID, "message": "hi"})

    assert resp.status_code == 422
    assert db_session.query(ContactMessage).count() == 0


def test_rate_limited_per_address(db_session):
    """Unauthenticated write endpoint, so the limit is the only thing between
    it and a script. Sixth request in the window is refused."""
    for _ in range(5):
        assert client.post("/contact/messages", json=VALID).status_code == 201

    resp = client.post("/contact/messages", json=VALID)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert db_session.query(ContactMessage).count() == 5
