"""The pre-submission crop check.

Confirming a crop advances the state machine and spends the submission, so
without this endpoint the first a customer hears about an unusable crop is a
finished report with no scores in it. Measured across 30 real photographs: the
fit falls back on 33% of uncropped images against ~7% when the crop is traced
around the card, and 8 of the 10 failures are recovered by re-cropping alone.
The fix is nearly always one the customer can apply in seconds -- if anything
tells them to.
"""

from fastapi.testclient import TestClient

from zgrader.analysis import assessment
from zgrader.api.main import app
from zgrader.models import ScanImage, Submission

from tests.conftest import register_and_verify

client = TestClient(app)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _submission_with_scan(token: str, path) -> str:
    resp = client.post(
        "/submissions",
        json={"game": "Pokemon", "card_name": "Pikachu"},
        headers=_auth(token),
    )
    code = resp.json()["submission_code"]
    with open(path, "rb") as handle:
        client.post(
            f"/submissions/{code}/scans",
            files={"file": ("front.png", handle, "image/png")},
            data={"side": "front"},
            headers=_auth(token),
        )
    return code


def _check(token: str, code: str, points) -> dict:
    return client.post(
        f"/submissions/{code}/scans/front/check-crop",
        json={"points": points},
        headers=_auth(token),
    ).json()


def test_a_crop_around_the_card_reports_the_boundary_was_found(db_session, sample_scan_paths):
    token = register_and_verify(client, "crop-ok@example.com")
    code = _submission_with_scan(token, sample_scan_paths["pokemon_front"])

    suggestion = client.get(
        f"/submissions/{code}/scans/front/suggest-crop", headers=_auth(token)
    ).json()
    body = _check(token, code, suggestion["points"])

    assert body["boundary_found"] is True
    assert assessment.GEOMETRY_UNVERIFIED not in body["limitations"]


def test_a_crop_containing_no_card_reports_the_boundary_was_not_found(
    db_session, sample_scan_paths
):
    """The case the endpoint exists for. A crop with no card edge inside it
    leaves the fit nothing to work with, so it falls back -- and after the
    geometry change that means the whole submission would score nothing."""
    token = register_and_verify(client, "crop-bad@example.com")
    code = _submission_with_scan(token, sample_scan_paths["pokemon_front"])
    scan = (
        db_session.query(ScanImage)
        .join(Submission)
        .filter(Submission.submission_code == code)
        .one()
    )

    # A small square in the very corner of the image: inside the bounds the
    # validator requires, and containing none of the card.
    w, h = scan.width_px, scan.height_px
    corner = [[0, 0], [w * 0.06, 0], [w * 0.06, h * 0.06], [0, h * 0.06]]
    body = _check(token, code, corner)

    assert body["boundary_found"] is False
    assert assessment.GEOMETRY_UNVERIFIED in body["limitations"]


def test_it_persists_nothing(db_session, sample_scan_paths):
    """Safe to call as often as the customer drags a handle. If it wrote the
    crop it would be confirm-crop, and confirm-crop spends the submission."""
    token = register_and_verify(client, "crop-nopersist@example.com")
    code = _submission_with_scan(token, sample_scan_paths["pokemon_front"])
    scan = (
        db_session.query(ScanImage)
        .join(Submission)
        .filter(Submission.submission_code == code)
        .one()
    )
    status_before = scan.submission.status
    assert scan.crop_points is None

    w, h = scan.width_px, scan.height_px
    _check(token, code, [[0, 0], [w, 0], [w, h], [0, h]])

    db_session.refresh(scan)
    assert scan.crop_points is None
    assert scan.submission.status == status_before


def test_it_rejects_a_crop_outside_the_image(db_session, sample_scan_paths):
    token = register_and_verify(client, "crop-oob@example.com")
    code = _submission_with_scan(token, sample_scan_paths["pokemon_front"])
    scan = (
        db_session.query(ScanImage)
        .join(Submission)
        .filter(Submission.submission_code == code)
        .one()
    )
    w, h = scan.width_px, scan.height_px

    resp = client.post(
        f"/submissions/{code}/scans/front/check-crop",
        json={"points": [[-5, 0], [w, 0], [w, h], [0, h]]},
        headers=_auth(token),
    )
    assert resp.status_code == 400


def test_it_rejects_the_wrong_number_of_points(db_session, sample_scan_paths):
    token = register_and_verify(client, "crop-three@example.com")
    code = _submission_with_scan(token, sample_scan_paths["pokemon_front"])

    resp = client.post(
        f"/submissions/{code}/scans/front/check-crop",
        json={"points": [[0, 0], [10, 0], [10, 10]]},
        headers=_auth(token),
    )
    assert resp.status_code == 400


def test_another_customer_cannot_check_your_crop(db_session, sample_scan_paths):
    """It reads someone's uploaded photograph, so it needs the same ownership
    check every other scan endpoint has."""
    owner = register_and_verify(client, "crop-owner@example.com")
    code = _submission_with_scan(owner, sample_scan_paths["pokemon_front"])
    stranger = register_and_verify(client, "crop-stranger@example.com")

    resp = client.post(
        f"/submissions/{code}/scans/front/check-crop",
        json={"points": [[0, 0], [10, 0], [10, 10], [0, 10]]},
        headers=_auth(stranger),
    )
    assert resp.status_code == 403
