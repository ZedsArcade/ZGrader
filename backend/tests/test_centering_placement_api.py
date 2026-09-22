"""The centering-adjust endpoint: place mode, its bounds, and the draft-only gate.

The bounds are enforced here, not only in the page: a limit that lives in the
browser is a suggestion. And adjusting is refused once a report leaves review,
because the public share page renders from the database -- an adjustment after
publication would change what a stranger sees with no operator review.
"""

import pytest
from fastapi.testclient import TestClient

from zgrader.analysis import assessment, scoring
from zgrader.api.main import app
from zgrader.db import SessionLocal
from zgrader.models import AuditLog, Submission, SubmissionStatus
from zgrader.models.settings import get_or_create_settings

from tests.centering_rows import PX_PER_MM, add_centering_rows, declined_side, scored_side
from tests.conftest import register_and_verify

client = TestClient(app)

PLACED = {"left_px": 30.0, "right_px": 30.0, "top_px": 25.0, "bottom_px": 35.0}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _owned_submission(email, front, back=None, status=SubmissionStatus.draft_ready) -> tuple[str, str]:
    token = register_and_verify(client, email)
    resp = client.post("/submissions", json={"game": "Pokemon", "card_name": "Snorlax"}, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    code = resp.json()["submission_code"]
    with SessionLocal() as db:
        submission = db.query(Submission).filter(Submission.submission_code == code).one()
        submission.status = status
        add_centering_rows(db, submission, front, back)
        db.commit()
    return token, code


def _post(token, code, side="front", widths=PLACED):
    return client.post(
        f"/submissions/{code}/centering-adjust", json={"side": side, **widths}, headers=_auth(token)
    )


def _delete(token, code, side="front"):
    return client.delete(f"/submissions/{code}/centering-adjust/{side}", headers=_auth(token))


def _combined_centering(body: dict) -> dict:
    return next(
        r for r in body["analysis_results"] if r["category"] == "centering" and r["side"] == "combined"
    )


def test_a_declined_side_accepts_a_placement(db_session):
    token, code = _owned_submission("place-ok@example.com", declined_side())

    resp = _post(token, code)

    assert resp.status_code == 200, resp.text
    combined = _combined_centering(resp.json())
    assert combined["raw_score"] is not None
    assert assessment.CENTERING_CLIENT_PLACED in combined["measurements"]["assessment"]["limitations"]
    assert resp.json()["centering_adjustments"]["front"] == PLACED


def test_a_line_further_than_the_bound_is_refused(db_session):
    token, code = _owned_submission("place-far@example.com", declined_side())
    too_far = {**PLACED, "top_px": (scoring.CENTERING_PLACEMENT_MAX_MM + 0.5) * PX_PER_MM}

    assert _post(token, code, widths=too_far).status_code == 400


def test_a_placement_with_no_axis_inside_the_card_is_refused(db_session):
    token, code = _owned_submission("place-zero@example.com", declined_side())
    zeros = {"left_px": 0.0, "right_px": 0.0, "top_px": 0.0, "bottom_px": 0.0}

    assert _post(token, code, widths=zeros).status_code == 400


def test_a_side_whose_edges_were_not_found_is_refused(db_session):
    token, code = _owned_submission(
        "place-unverified@example.com", declined_side(assessment.GEOMETRY_UNVERIFIED)
    )

    assert _post(token, code).status_code == 409


def test_the_kill_switch_disables_placement_too(db_session):
    token, code = _owned_submission("place-off@example.com", declined_side())
    with SessionLocal() as db:
        get_or_create_settings(db).centering_adjust_limit_mm = 0
        db.commit()

    assert _post(token, code).status_code == 403


@pytest.mark.parametrize("status", [SubmissionStatus.published, SubmissionStatus.awaiting_scans])
def test_adjusting_is_refused_outside_draft_review(db_session, status):
    token, code = _owned_submission(f"place-{status.value}@example.com", declined_side(), status=status)

    assert _post(token, code).status_code == 409
    assert _delete(token, code).status_code == 409


def test_nudging_is_refused_after_publication_too(db_session):
    token, code = _owned_submission(
        "nudge-published@example.com", scored_side(), status=SubmissionStatus.published
    )
    nudged = {"left_px": 31.0, "right_px": 34.0, "top_px": 30.0, "bottom_px": 30.0}

    assert _post(token, code, widths=nudged).status_code == 409


def test_nudging_a_scored_side_still_works(db_session):
    token, code = _owned_submission("nudge-ok@example.com", scored_side())
    nudged = {"left_px": 31.0, "right_px": 34.0, "top_px": 30.0, "bottom_px": 30.0}

    resp = _post(token, code, widths=nudged)

    assert resp.status_code == 200, resp.text
    assert resp.json()["centering_adjustments"]["front"] == nudged


def test_delete_clears_a_placement_and_records_both_actions(db_session):
    token, code = _owned_submission("place-clear@example.com", declined_side())
    assert _post(token, code).status_code == 200

    resp = _delete(token, code)

    assert resp.status_code == 200, resp.text
    assert _combined_centering(resp.json())["raw_score"] is None
    assert not resp.json()["centering_adjustments"]
    with SessionLocal() as db:
        submission = db.query(Submission).filter(Submission.submission_code == code).one()
        actions = {a.action for a in db.query(AuditLog).filter(AuditLog.submission_id == submission.id)}
    assert {"centering_placed", "centering_placement_cleared"} <= actions


def test_deleting_with_nothing_stored_is_a_no_op(db_session):
    token, code = _owned_submission("place-noop@example.com", declined_side())

    resp = _delete(token, code)

    assert resp.status_code == 200, resp.text
    assert _combined_centering(resp.json())["raw_score"] is None
