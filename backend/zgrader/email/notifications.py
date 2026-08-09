"""Builds and sends the two notification emails the plan calls for:
submission-received (a client's submission request was created) and
report-published (their PDF is ready). Both are best-effort -- see
zgrader/email/client.py for why failures never propagate.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from zgrader.config import config
from zgrader.email.client import send_email
from zgrader.email.strings import EMAIL_STRINGS
from zgrader.models import ContactMessage, ContactTopic, Settings, Submission, User

TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "jinja"]),
)


def _business_name(settings: Settings | None) -> str:
    return settings.business_name if settings else "Card Care Center"


def _card_name(submission: Submission) -> str | None:
    return submission.card.card_name if submission.card else None


def send_submission_received(user: User, submission: Submission, settings: Settings | None) -> None:
    business_name = _business_name(settings)
    strings = EMAIL_STRINGS[submission.language.value]
    html = _env.get_template("submission_received.html.jinja").render(
        strings=strings,
        business_name=business_name,
        submission_code=submission.submission_code,
        card_name=_card_name(submission),
    )
    subject = strings["subject_received"].format(submission_code=submission.submission_code)
    send_email(user.email, f"[{business_name}] {subject}", html)


def send_report_published(user: User, submission: Submission, settings: Settings | None) -> None:
    business_name = _business_name(settings)
    strings = EMAIL_STRINGS[submission.language.value]
    html = _env.get_template("report_published.html.jinja").render(
        strings=strings,
        business_name=business_name,
        submission_code=submission.submission_code,
        card_name=_card_name(submission),
    )
    subject = strings["subject_published"].format(submission_code=submission.submission_code)
    send_email(user.email, f"[{business_name}] {subject}", html)


def _send_account_action(
    user: User,
    settings: Settings | None,
    *,
    subject_key: str,
    intro_key: str,
    action_key: str,
    expiry_key: str,
    path: str,
) -> None:
    """Render and send one of the account-lifecycle emails.

    They all share a shape -- explain, offer one button, state the expiry --
    so they share a template. Language: these are account-level rather than
    submission-level, and there's no per-user locale column yet, so they go
    out in English. Worth revisiting when a locale preference exists.
    """
    strings = EMAIL_STRINGS["en"]
    business_name = _business_name(settings)
    html = _env.get_template("account_action.html.jinja").render(
        strings=strings,
        business_name=business_name,
        intro=strings[intro_key],
        action_label=strings[action_key],
        expiry_note=strings[expiry_key],
        action_url=f"{config.site_url.rstrip('/')}{path}",
    )
    send_email(to=user.email, subject=strings[subject_key], html_body=html)


def send_verification_email(user: User, settings: Settings | None) -> None:
    _send_account_action(
        user,
        settings,
        subject_key="subject_verify",
        intro_key="verify_intro",
        action_key="verify_action",
        expiry_key="verify_expiry",
        path=f"/verify/{user.verification_token}",
    )


def send_password_reset_email(user: User, settings: Settings | None) -> None:
    _send_account_action(
        user,
        settings,
        subject_key="subject_reset",
        intro_key="reset_intro",
        action_key="reset_action",
        expiry_key="reset_expiry",
        path=f"/reset-password/{user.password_reset_token}",
    )


def send_already_registered_email(user: User, settings: Settings | None) -> None:
    """Sent when someone tries to register an address that already exists.

    Registration returns the same 201 either way, so this is what stops the
    endpoint being an oracle for which addresses have accounts -- the person
    who owns the inbox finds out, and nobody else does.
    """
    _send_account_action(
        user,
        settings,
        subject_key="subject_already_registered",
        intro_key="already_registered_intro",
        action_key="already_registered_action",
        expiry_key="already_registered_expiry",
        path="/login",
    )


def send_password_changed_email(user: User, settings: Settings | None) -> None:
    """Tells the account owner their password changed -- the notification that
    surfaces a takeover the victim would otherwise not see."""
    _send_account_action(
        user,
        settings,
        subject_key="subject_password_changed",
        intro_key="password_changed_intro",
        action_key="password_changed_action",
        expiry_key="password_changed_expiry",
        path="/forgot-password",
    )


# Topics are stored as an enum but read by a human, so they get a label rather
# than appearing as "lab" in a subject line. Both brand names come from
# Settings, which is why this needs the row rather than a static map.
def _topic_label(topic: ContactTopic, settings: Settings | None) -> str:
    if topic is ContactTopic.lab:
        return _business_name(settings)
    if topic is ContactTopic.care:
        return settings.care_business_name if settings else "Card care"
    return "General enquiry"


def send_contact_message(message: ContactMessage, settings: Settings | None) -> bool:
    """Notify the operator about a contact-form enquiry. Returns delivery.

    Unlike every other notification here the return value matters and is
    stored: the enquiry is already safe in the database by the time this runs,
    so a False means "there is an unread row", not "the customer lost their
    message".

    Sends to the operator's configured contact address. When that is unset
    there is nowhere to send it, which is not an error -- the row still stands
    and the operator reads it in the admin panel.
    """
    to = settings.contact_email if settings else None
    if not to:
        return False

    business_name = _business_name(settings)
    label = _topic_label(message.topic, settings)
    html = _env.get_template("contact_message.html.jinja").render(
        business_name=business_name,
        topic_label=label,
        name=message.name,
        email=message.email,
        subject=message.subject,
        submission_code=message.submission_code,
        language=message.language,
        message=message.message,
        message_id=message.id,
    )
    # The sender's own subject, prefixed so it threads and sorts alongside the
    # other automated mail from the service.
    return send_email(to, f"[{business_name}] {label}: {message.subject}", html)


def send_test_email(to: str, settings: Settings | None) -> bool:
    """Prove the relay works, without registering a throwaway account.

    Exists because every other path through this module swallows failures --
    correctly, since a notification must never break the flow it hangs off --
    which leaves a misconfigured relay indistinguishable from a working one
    from the outside. This is the one place the SMTP result is the answer
    rather than a side effect.

    Deliberately plain: it reports what the app is configured to do, so the
    body is useful when it lands in a spam folder and the operator is trying
    to work out which relay actually sent it.
    """
    business_name = _business_name(settings)
    html = _env.get_template("test_email.html.jinja").render(
        business_name=business_name,
        smtp_host=config.smtp_host,
        smtp_port=config.smtp_port,
        smtp_from=config.smtp_from,
        tls_mode=(
            "implicit TLS"
            if config.smtp_implicit_tls
            else "STARTTLS"
            if config.smtp_use_tls
            else "none"
        ),
    )
    return send_email(to, f"[{business_name}] Test email", html)
