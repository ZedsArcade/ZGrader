"""Builds and sends the two notification emails the plan calls for:
submission-received (a client's submission request was created) and
report-published (their PDF is ready). Both are best-effort -- see
zgrader/email/client.py for why failures never propagate.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from zgrader.email.client import send_email
from zgrader.models import Settings, Submission, User

TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "jinja"]),
)


def _business_name(settings: Settings | None) -> str:
    return settings.business_name if settings else "ZGrader"


def _card_name(submission: Submission) -> str | None:
    return submission.card.card_name if submission.card else None


def send_submission_received(user: User, submission: Submission, settings: Settings | None) -> None:
    business_name = _business_name(settings)
    html = _env.get_template("submission_received.html.jinja").render(
        business_name=business_name,
        submission_code=submission.submission_code,
        card_name=_card_name(submission),
    )
    send_email(user.email, f"[{business_name}] Submission {submission.submission_code} received", html)


def send_report_published(user: User, submission: Submission, settings: Settings | None) -> None:
    business_name = _business_name(settings)
    html = _env.get_template("report_published.html.jinja").render(
        business_name=business_name,
        submission_code=submission.submission_code,
        card_name=_card_name(submission),
    )
    send_email(
        user.email, f"[{business_name}] Your report for {submission.submission_code} is ready", html
    )
