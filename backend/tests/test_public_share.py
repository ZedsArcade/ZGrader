"""Sharing a report by link, and the things that must never travel with it.

`submission_code` comes from `submission_code_seq`, so codes are sequential and
guessable. A public URL carrying one would let anyone walk the sequence and read
every customer's report -- which is the entire reason a separate share token
exists, and the reason most of the assertions below are about absence rather
than presence.

The load-bearing test here is `test_public_payload_key_allowlist`. The other two
leak tests check for things somebody already thought of; that one fails whenever
a *new* field appears, which is how the public serializer would actually drift.
`raw_score` becoming nullable broke four separate downstream assumptions before
anyone noticed a pattern, all by addition.
"""

import datetime
import json

import pytest
from fastapi.testclient import TestClient

from zgrader.api.main import app
from zgrader.db import SessionLocal
from zgrader.models import (
    AnalysisCategory,
    AnalysisResult,
    AnalysisSide,
    AuditLog,
    GradingCompanyComparison,
    Report,
    ReportStatus,
    Submission,
)
from zgrader.models.grading_comparison import GradingCompany, ToleranceSeverity

from tests.conftest import register_and_verify

client = TestClient(app)

OWNER_EMAIL = "sharer@example.com"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_submission(auth_token: str) -> str:
    resp = client.post(
        "/submissions",
        json={"game": "Pokemon", "card_name": "Charizard", "set_name": "Base", "card_number": "4"},
        headers=_auth(auth_token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["submission_code"]


def _add_analysis(db, submission: Submission) -> None:
    """Enough of a real result to exercise the measurements projection.

    `assessment`, `regions` and the centering widths are the keys the public page
    reads; `internal_debug_blob` is here to be dropped, since a bare pass-through
    of this JSONB column is the likeliest way something private reaches the page.
    """
    db.add(
        AnalysisResult(
            submission_id=submission.id,
            side=AnalysisSide.front,
            category=AnalysisCategory.centering,
            raw_score=8.5,
            measurements={
                "left_px": 30.0,
                "right_px": 34.0,
                "top_px": 28.0,
                "bottom_px": 31.0,
                "card_geometry": {"px_per_mm": 12.0, "apexes": [[0, 0]]},
                "assessment": {
                    "state": "measured",
                    "confidence": 0.8,
                    "score_low": 8.0,
                    "score_high": 9.0,
                    "limitations": ["centering_partial_frame"],
                },
                "regions": [
                    {
                        "id": "frame",
                        "kind": "frame",
                        "severity": "ok",
                        "score": 8.5,
                        "bbox_norm": [0.1, 0.1, 0.9, 0.9],
                        "anchor_norm": [0.5, 0.5],
                        "note": None,
                    }
                ],
                "internal_debug_blob": {"operator_note": "do not publish me"},
            },
            flags={"lower_confidence": False},
        )
    )
    db.add(
        AnalysisResult(
            submission_id=submission.id,
            side=AnalysisSide.combined,
            category=AnalysisCategory.corners,
            # Unmeasurable, so the public page has to render "not measurable"
            # rather than a zero -- the fifth place downstream of raw_score
            # becoming nullable.
            raw_score=None,
            measurements={"assessment": {"state": "unmeasurable", "confidence": 0.0,
                                         "score_low": None, "score_high": None,
                                         "limitations": ["corners_whitening_only"]}},
            flags={"lower_confidence": True, "reason": "Too few pixels."},
        )
    )
    db.add(
        GradingCompanyComparison(
            submission_id=submission.id,
            company=GradingCompany.PSA,
            category="centering",
            severity=ToleranceSeverity.minor,
            contention_note="Slightly off-centre left to right.",
        )
    )


def _publish(db, submission: Submission, status: ReportStatus = ReportStatus.published) -> Report:
    report = Report(
        submission_id=submission.id,
        version=1,
        status=status,
        pdf_path=f"/tmp/{submission.submission_code}.pdf",
        generated_at=datetime.datetime.now(datetime.timezone.utc),
        published_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(report)
    return report


@pytest.fixture()
def shared(db_session):
    """An owner, a published submission with analysis, and a live share token."""
    auth_token = register_and_verify(client, OWNER_EMAIL)
    code = _create_submission(auth_token)
    with SessionLocal() as db:
        submission = db.query(Submission).filter(Submission.submission_code == code).one()
        _add_analysis(db, submission)
        _publish(db, submission)
        db.commit()

    resp = client.post(f"/submissions/{code}/share", headers=_auth(auth_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    share_token = body["url"].rsplit("/", 1)[-1]
    return {"auth": auth_token, "code": code, "token": share_token, "url": body["url"]}


# --- the public route works at all -------------------------------------


def test_unauthenticated_request_with_valid_token_succeeds(shared):
    """The point of the feature: no Authorization header, no cookie, no session."""
    resp = client.get(f"/public/reports/{shared['token']}")

    assert resp.status_code == 200, resp.text
    assert resp.json()["card"]["card_name"] == "Charizard"


def test_share_is_off_by_default(db_session):
    auth_token = register_and_verify(client, "notshared@example.com")
    code = _create_submission(auth_token)

    state = client.get(f"/submissions/{code}/share", headers=_auth(auth_token)).json()

    assert state["enabled"] is False
    assert state["url"] is None
    with SessionLocal() as db:
        row = db.query(Submission).filter(Submission.submission_code == code).one()
        assert row.share_token is None


# --- what must never be on the page ------------------------------------


def _walk(node, keys: set, values: set) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            keys.add(key)
            _walk(value, keys, values)
    elif isinstance(node, list):
        for item in node:
            _walk(item, keys, values)
    elif isinstance(node, str):
        values.add(node)


def test_submission_code_appears_nowhere_in_the_public_response(shared):
    """Keys *and* values. The code could just as easily arrive inside a
    contention note or an image path as under a field named after it."""
    resp = client.get(f"/public/reports/{shared['token']}")
    keys: set = set()
    values: set = set()
    _walk(resp.json(), keys, values)

    assert "submission_code" not in keys
    assert not any(shared["code"] in value for value in values)
    # Belt and braces: the raw body, in case a code reached a numeric field.
    assert shared["code"] not in resp.text


def test_account_scoped_fields_are_absent(shared):
    resp = client.get(f"/public/reports/{shared['token']}")
    body = resp.json()
    keys: set = set()
    _walk(body, keys, set())

    # Nowhere at any depth. `id` is deliberately not in this list: a region
    # carries one ("frame"), and it identifies a rectangle on a card rather than
    # a row in the database. The submission's own id is checked below instead.
    for forbidden in ("user_id", "batch_id", "notes", "auto_publish", "error_message",
                      "email", "quota", "share_token", "submission_code"):
        assert forbidden not in keys, f"{forbidden} reached the public payload"

    # Nothing identifying the submission or its owner as a value, whatever it
    # might be called on the way out.
    with SessionLocal() as db:
        submission = db.query(Submission).filter(
            Submission.submission_code == shared["code"]
        ).one()
        assert str(submission.id) not in resp.text
        assert str(submission.user_id) not in resp.text
    assert OWNER_EMAIL not in resp.text
    # The top level is where a whole-row serialisation would land.
    assert "id" not in body and "status" not in body


def test_measurements_are_projected_not_passed_through(shared):
    """The stored blob carries a key nothing renders. A pass-through serializer
    publishes it; the projection drops it."""
    resp = client.get(f"/public/reports/{shared['token']}")
    keys: set = set()
    _walk(resp.json(), keys, set())

    assert "internal_debug_blob" not in keys
    assert "apexes" not in keys
    # The keys that are meant to survive did.
    assert {"regions", "assessment", "px_per_mm", "left_px"} <= keys


def test_public_payload_key_allowlist(shared):
    """Every key the public payload may contain, as a literal.

    This is the one that catches drift, because it fails on *addition* rather
    than on a list of things somebody already worried about. When it breaks, the
    question to answer is "should a stranger see this?" -- and then to add the
    key here deliberately.
    """
    resp = client.get(f"/public/reports/{shared['token']}")
    keys: set = set()
    _walk(resp.json(), keys, set())

    assert keys == {
        # top level
        "card", "language", "created_at", "client_adjusted", "dismissed_count",
        "sides", "results", "comparisons", "centering_adjustments", "grading_companies",
        # Added deliberately: a hash of what the link-preview image is drawn
        # from, so an adjusted report gets a different og:image URL. Derived
        # from what the page already shows, so it discloses nothing new.
        "og_version",
        # card
        "game", "card_name", "set_name", "card_number", "foil",
        # results
        "category", "side", "raw_score", "flags", "measurements",
        # flags
        "lower_confidence", "reason",
        # measurements
        "regions", "assessment", "original_raw_score", "ai_observations",
        "px_per_mm", "left_px", "right_px", "top_px", "bottom_px",
        # assessment
        "state", "confidence", "score_low", "score_high", "limitations",
        # regions
        "id", "kind", "severity", "score", "bbox_norm", "anchor_norm", "note",
        "area_fraction", "length_mm", "low_confidence", "line_norm",
        # comparisons
        "company", "contention_note",
    }


def test_unmeasurable_category_publishes_a_null_not_a_zero(shared):
    resp = client.get(f"/public/reports/{shared['token']}")
    corners = [r for r in resp.json()["results"] if r["category"] == "corners"][0]

    assert corners["raw_score"] is None


# --- 404, never 403 -----------------------------------------------------


def test_unknown_token_is_404(db_session):
    resp = client.get("/public/reports/nosuchtokenatall")

    assert resp.status_code == 404


def test_revoked_token_is_404(shared):
    """Disabling makes the link stop resolving, and it must read exactly like a
    token that never existed."""
    client.delete(f"/submissions/{shared['code']}/share", headers=_auth(shared["auth"]))

    resp = client.get(f"/public/reports/{shared['token']}")

    assert resp.status_code == 404


def test_rotating_kills_the_old_link_and_issues_a_new_one(shared):
    resp = client.post(f"/submissions/{shared['code']}/share/rotate", headers=_auth(shared["auth"]))
    new_token = resp.json()["url"].rsplit("/", 1)[-1]

    assert new_token != shared["token"]
    assert client.get(f"/public/reports/{shared['token']}").status_code == 404
    assert client.get(f"/public/reports/{new_token}").status_code == 200


def test_unpublishing_takes_a_live_link_down_and_republishing_restores_it(shared):
    """The public route asks whether the report is published *now*, not whether
    it was when sharing was switched on. A re-run that returns a submission to
    draft therefore pulls the page by itself."""
    with SessionLocal() as db:
        report = db.query(Report).join(Submission).filter(
            Submission.submission_code == shared["code"]
        ).one()
        report.status = ReportStatus.draft
        db.commit()

    assert client.get(f"/public/reports/{shared['token']}").status_code == 404

    with SessionLocal() as db:
        report = db.query(Report).join(Submission).filter(
            Submission.submission_code == shared["code"]
        ).one()
        report.status = ReportStatus.published
        db.commit()

    assert client.get(f"/public/reports/{shared['token']}").status_code == 200


# --- the authenticated side --------------------------------------------


def test_enabling_is_refused_until_the_report_is_published(db_session):
    auth_token = register_and_verify(client, "draftowner@example.com")
    code = _create_submission(auth_token)
    with SessionLocal() as db:
        submission = db.query(Submission).filter(Submission.submission_code == code).one()
        _publish(db, submission, status=ReportStatus.draft)
        db.commit()

    resp = client.post(f"/submissions/{code}/share", headers=_auth(auth_token))

    assert resp.status_code == 409


def test_enabling_twice_keeps_the_same_link(shared):
    """A customer pressing share again must not silently kill the link they
    pasted somewhere a minute ago."""
    again = client.post(f"/submissions/{shared['code']}/share", headers=_auth(shared["auth"]))

    assert again.json()["url"] == shared["url"]


def test_another_account_cannot_enable_sharing(shared):
    """403 here, not 404: this is the authenticated surface, where the caller
    has already said who they are."""
    other = register_and_verify(client, "stranger@example.com")

    resp = client.post(f"/submissions/{shared['code']}/share", headers=_auth(other))

    assert resp.status_code == 403


def test_the_token_never_reaches_the_audit_log(shared):
    """The audit log is readable in the admin panel, so a token recorded there
    is the same secret in a second place -- one that outlives the rotation meant
    to kill it."""
    rotate = client.post(f"/submissions/{shared['code']}/share/rotate", headers=_auth(shared["auth"]))
    new_token = rotate.json()["url"].rsplit("/", 1)[-1]

    with SessionLocal() as db:
        details = [json.dumps(row.detail) for row in db.query(AuditLog).all()]
        actions = {row.action for row in db.query(AuditLog).all()}

    assert "share_enabled" in actions and "share_rotated" in actions
    for detail in details:
        assert shared["token"] not in detail
        assert new_token not in detail


# --- images -------------------------------------------------------------


def test_public_image_rejects_a_kind_it_did_not_generate(shared):
    resp = client.get(f"/public/reports/{shared['token']}/images/front_..%2f..%2fsecret.png")

    assert resp.status_code == 404


def test_public_image_rejects_an_unknown_side(shared):
    resp = client.get(f"/public/reports/{shared['token']}/images/sideways_base.png")

    assert resp.status_code == 404


def test_deleting_the_submission_takes_the_link_with_it(shared):
    """A customer who deletes a submission has revoked every link to it, whether
    or not they thought about sharing while doing so. The token lives on the row,
    so this needs nothing of its own -- which is exactly why it is worth pinning."""
    resp = client.delete(f"/submissions/{shared['code']}", headers=_auth(shared["auth"]))

    assert resp.status_code == 204
    assert client.get(f"/public/reports/{shared['token']}").status_code == 404


def test_public_images_stop_resolving_once_revoked(shared):
    client.delete(f"/submissions/{shared['code']}/share", headers=_auth(shared["auth"]))

    assert client.get(f"/public/reports/{shared['token']}/og.png").status_code == 404
    assert (
        client.get(f"/public/reports/{shared['token']}/images/front_base.png").status_code == 404
    )
