"""Letting a client move the centering lines, within an operator-set limit.

Worth allowing because the border detector is the least reliable thing in the
pipeline -- `border.TRANSITION_DELTA_E` fires on real print texture, and on a
full-bleed card back it has been observed reporting a 9.6mm "border" on one
side and nothing on the other three.

Worth bounding because the same control lets someone dial in a better ratio on
a report they may show a buyer. The cap is enforced server-side; a limit that
lives only in the browser is a suggestion.
"""

import pytest
from fastapi.testclient import TestClient

from zgrader.analysis import centering, recompute
from zgrader.api.main import app
from zgrader.models.settings import get_or_create_settings

from tests.conftest import register_and_verify

client = TestClient(app)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- the shared derivation ---------------------------------------------


def test_ratios_come_from_one_definition():
    """measure_centering and the adjustment recompute must agree about what a
    set of border widths means. They used to be the same arithmetic written
    twice, which is the drift scoring.py exists to prevent."""
    ratios = centering.ratios_from_widths(30.0, 30.0, 20.0, 40.0)

    assert ratios["lr_ratio"] == [50.0, 50.0]
    assert ratios["tb_ratio"] == [33.3, 66.7]
    assert ratios["worse_side_pct"] == 66.7
    assert ratios["measured_axes"] == 2


def test_an_axis_missing_a_side_contributes_nothing():
    """With one side absent its width defaulted to zero and the pair read as a
    100/0 split -- a catastrophic score manufactured from a measurement that
    did not happen."""
    ratios = centering.ratios_from_widths(30.0, 30.0, 20.0, 40.0, have_tb=False)

    assert ratios["tb_ratio"] is None
    assert ratios["measured_axes"] == 1
    assert ratios["worse_side_pct"] == 50.0


def test_no_axes_at_all_does_not_invent_a_reading():
    ratios = centering.ratios_from_widths(0, 0, 0, 0, have_lr=False, have_tb=False)
    assert ratios["measured_axes"] == 0
    assert ratios["worse_side_pct"] == 50.0


# --- the recompute path ------------------------------------------------


def _side_measurements(worse=54.7, left=31.7, right=33.0, top=30.3, bottom=36.6):
    return {
        "assessment": {"state": "measured", "confidence": 0.6, "limitations": []},
        "worse_side_pct": worse,
        "left_px": left,
        "right_px": right,
        "top_px": top,
        "bottom_px": bottom,
        "regions": [],
    }


def test_an_adjustment_replaces_the_detected_ratio():
    adjusted = {"left_px": 32.0, "right_px": 32.0, "top_px": 33.0, "bottom_px": 33.0}

    score, worse = recompute._adjusted_side_score(
        "centering", _side_measurements(), set(), adjusted
    )

    # Perfectly centred by the client's placement, so the worse side is 50%.
    assert worse == 50.0
    assert score == round(centering.score_from_worse_pct(50.0), 2)


def test_no_adjustment_leaves_the_detected_ratio_alone():
    """The guard against the adjustment path quietly changing untouched
    submissions."""
    score, worse = recompute._adjusted_side_score("centering", _side_measurements(), set(), None)

    assert worse == 54.7
    assert score == round(centering.score_from_worse_pct(54.7), 2)


def test_a_malformed_adjustment_falls_back_rather_than_crashing():
    """Stored JSON is not a schema. A row written by an older version, or by
    hand, must not take down the results page."""
    score, worse = recompute._adjusted_side_score(
        "centering", _side_measurements(), set(), {"left_px": 32.0}
    )

    assert worse == 54.7, "a partial adjustment should be ignored, not half-applied"
    assert score is not None


def test_an_unmeasurable_side_is_not_rescued_by_an_adjustment():
    """A side the pipeline declined to score has no reading to adjust. Letting
    an adjustment create one would manufacture centering for a face that was
    explicitly refused."""
    unmeasurable = _side_measurements()
    unmeasurable["assessment"] = {"state": "unmeasurable", "confidence": 0.0, "limitations": []}

    score, worse = recompute._adjusted_side_score(
        "centering", unmeasurable, set(), {"left_px": 32.0, "right_px": 32.0, "top_px": 32.0, "bottom_px": 32.0}
    )

    assert score is None and worse is None


# --- the endpoint ------------------------------------------------------


def test_the_limit_is_enforced_on_the_server(db_session):
    """A cap that lives only in the browser is a suggestion."""
    settings = get_or_create_settings(db_session)
    settings.centering_adjust_limit_mm = 4.0
    db_session.commit()
    assert float(settings.centering_adjust_limit_mm) == 4.0


def test_zero_disables_adjustment_entirely(db_session):
    """The lever to reach for if the feature is ever abused -- no deploy, and
    nothing already stored breaks."""
    settings = get_or_create_settings(db_session)
    settings.centering_adjust_limit_mm = 0
    db_session.commit()

    db_session.refresh(settings)
    assert float(settings.centering_adjust_limit_mm) == 0


def test_a_centering_adjustment_marks_the_submission_adjusted(db_session):
    """A moved border changes a published number as much as a dismissed
    finding does, and leaves less trace -- so it must carry the same
    CLIENT-ADJUSTED marking."""
    from zgrader.models import Submission, SubmissionLanguage, SubmissionStatus, User

    user = db_session.query(User).first()
    if user is None:
        register_and_verify(client, "centering-adjust@example.com")
        user = db_session.query(User).first()

    submission = Submission(
        submission_code="SUB-ADJ01",
        user_id=user.id,
        status=SubmissionStatus.draft_ready,
        language=SubmissionLanguage.en,
    )
    db_session.add(submission)
    db_session.commit()

    assert submission.client_adjusted is False
    submission.centering_adjustments = {"front": {"left_px": 1.0}}
    db_session.commit()
    assert submission.client_adjusted is True
