"""One place that decides what a share token is and when it resolves.

Both routers need these answers and they must not disagree: the authenticated
one deciding a submission may be shared, and the public one deciding a token
still resolves, are the same question asked at two different times.
"""

import secrets

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from zgrader.config import config
from zgrader.models import Report, ReportStatus, Submission
from zgrader.schemas.public_report import ShareStateOut

#: 128 bits, 22 URL-safe characters. The column is wider so this can be raised
#: without a migration.
_TOKEN_BYTES = 16


def new_token() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


def share_url(token: str) -> str:
    """The link a customer copies. Built from the configured public origin the
    same way the report's methodology footer is (reports/builder.py), so the
    address in a customer's clipboard is the one their browser can reach."""
    return f"{config.site_url.rstrip('/')}/r/{token}"


def latest_report(submission: Submission) -> Report | None:
    reports = sorted(submission.reports, key=lambda r: r.version, reverse=True)
    return reports[0] if reports else None


def is_publicly_visible(submission: Submission) -> bool:
    """Whether this submission is fit to be read by a stranger right now.

    Asked on *every* public request, not just when sharing is switched on. A
    re-run that returns a submission to `draft_ready` therefore takes the live
    link down by itself, and republishing brings the same link back -- no second
    flag to fall out of step with the report's own status, which is the field
    `download_report` already gates on for the same reason.
    """
    report = latest_report(submission)
    return report is not None and report.status == ReportStatus.published


def share_state(submission: Submission) -> ShareStateOut:
    """Authenticated view of the share setting. Carries the token, in the URL,
    to the owner -- who is the one entitled to it."""
    if submission.share_token is None:
        return ShareStateOut(enabled=False)
    return ShareStateOut(
        enabled=True,
        url=share_url(submission.share_token),
        enabled_at=submission.share_enabled_at,
    )


def resolve_shared_submission(token: str, db: Session) -> Submission:
    """A token to its submission, or 404.

    **404 and never 403.** A 403 confirms something is there, which hands
    somebody probing tokens the one bit they were missing. The unpublished case
    is 404 for the same reason, and reads identically from outside to a token
    that never existed.
    """
    submission = db.query(Submission).filter(Submission.share_token == token).first()
    if submission is None or not is_publicly_visible(submission):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return submission
