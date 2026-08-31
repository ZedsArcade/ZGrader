"""Contact enquiries expire, because nothing else would ever remove them.

`contact_messages` is deliberately not FK'd to `users` -- the sender need not
have an account, and the submission code is typed by hand -- so closing an
account cannot reach it. That makes this table the one place where a name, an
address, a message body and an IP accumulate indefinitely, and the privacy
policy now quotes the window that bounds it.
"""

import datetime

from zgrader.config import config
from zgrader.models import ContactMessage, ContactTopic
from zgrader.worker.main import purge_expired_contact_messages


def _message(db_session, subject: str, age_days: int) -> ContactMessage:
    """A stored enquiry, backdated by writing created_at directly.

    TimestampMixin defaults it on insert, so the age has to be set explicitly
    rather than waited for.
    """
    message = ContactMessage(
        name="Someone",
        email="someone@example.com",
        topic=ContactTopic.other,
        subject=subject,
        message="Is this card worth grading?",
        client_ip="203.0.113.7",
    )
    db_session.add(message)
    db_session.flush()
    message.created_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=age_days
    )
    db_session.commit()
    return message


def test_an_enquiry_past_the_window_is_deleted(db_session):
    _message(db_session, "old", age_days=config.contact_message_retention_days + 1)

    assert purge_expired_contact_messages(db_session) == 1
    assert db_session.query(ContactMessage).count() == 0


def test_an_enquiry_inside_the_window_is_kept(db_session):
    _message(db_session, "recent", age_days=config.contact_message_retention_days - 1)

    assert purge_expired_contact_messages(db_session) == 0
    assert db_session.query(ContactMessage).count() == 1


def test_the_purge_takes_only_what_has_expired(db_session):
    _message(db_session, "old", age_days=config.contact_message_retention_days + 30)
    _message(db_session, "recent", age_days=1)

    assert purge_expired_contact_messages(db_session) == 1
    remaining = db_session.query(ContactMessage).all()
    assert [m.subject for m in remaining] == ["recent"]


def test_zero_disables_the_purge(monkeypatch, db_session):
    """The escape hatch for an operator who would rather keep the history --
    and a guard against a misread config silently deleting everything, since a
    cutoff of `now` would match every row rather than none."""
    monkeypatch.setattr(config, "contact_message_retention_days", 0)
    _message(db_session, "ancient", age_days=5000)

    assert purge_expired_contact_messages(db_session) == 0
    assert db_session.query(ContactMessage).count() == 1
