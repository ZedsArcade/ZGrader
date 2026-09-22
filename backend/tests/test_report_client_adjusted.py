"""A centering-only adjustment must mark the PDF as client-adjusted.

`Submission.client_adjusted` counts dismissed findings *or* centering
adjustments, and says why both must. The report builder recomputed the flag
from dismissed findings alone, so a report whose only change was a moved
centering line published without the watermark, the title tag or the
`_client_adjusted` filename suffix.
"""

from zgrader.auth.security import hash_password
from zgrader.models import Submission, SubmissionStatus, User
from zgrader.models.settings import get_or_create_settings
from zgrader.reports.builder import build_report_context


def _submission(db_session, code: str) -> Submission:
    user = User(
        email=f"{code.lower()}@example.com",
        hashed_password=hash_password("hunter2pass"),
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    submission = Submission(submission_code=code, user_id=user.id, status=SubmissionStatus.draft_ready)
    db_session.add(submission)
    db_session.commit()
    return submission


def test_a_centering_only_adjustment_marks_the_report_adjusted(db_session):
    submission = _submission(db_session, "SUB-WMK01")
    submission.centering_adjustments = {
        "front": {"left_px": 30.0, "right_px": 34.0, "top_px": 28.0, "bottom_px": 31.0}
    }
    db_session.commit()

    context = build_report_context(submission, get_or_create_settings(db_session))

    assert context["dismissed_count"] == 0
    assert context["client_adjusted"] is True


def test_an_untouched_report_is_not_marked_adjusted(db_session):
    submission = _submission(db_session, "SUB-WMK02")

    context = build_report_context(submission, get_or_create_settings(db_session))

    assert context["client_adjusted"] is False
