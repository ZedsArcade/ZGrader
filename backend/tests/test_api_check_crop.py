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
from zgrader.models import ScanImage, ScanSide, Submission

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


def _submission_with_front_scan(email: str) -> tuple[str, str]:
    """Register, verify, and upload the standard sample front scan.

    `_submission_with_scan` already does the upload half; this adds
    registration and points it at the same `pokemon_front.png` fixture
    `sample_scan_paths` serves, generating it first if this is the first
    test in the run to need it -- the same guard that fixture itself uses.
    """
    from tests.conftest import FIXTURES_DIR
    from tests.fixtures.generate_samples import write_sample_set

    if not (FIXTURES_DIR / "pokemon_front.png").exists():
        write_sample_set(FIXTURES_DIR)
    token = register_and_verify(client, email)
    code = _submission_with_scan(token, FIXTURES_DIR / "pokemon_front.png")
    return token, code


def _detected_crop(code: str) -> list[list[float]]:
    """The auto-detected crop for the front scan, via `suggest-crop`,
    canonically ordered top-left/top-right/bottom-right/bottom-left.

    `suggest-crop` returns `detect_boundary`'s box in whatever order its
    contour trace happened to start at -- on the `pokemon_front` fixture
    that is bottom-left/top-left/top-right/bottom-right, not the tl/tr/br/bl
    order the rest of the pipeline uses (see `_canonical_size`'s
    `tl, tr, br, bl = apexes`). Reordering with the same `_order_points`
    `preprocessing.py` itself uses is what makes indices 2 and 3 reliably
    "the bottom edge" for a caller pushing one side, rather than two
    corners of whichever side the contour happened to start on.

    Mints its own access token for the submission's owner from the DB
    rather than taking one as a parameter, so a caller holding only `code`
    (as the disagreement test does, once it has moved on from registration)
    can still ask for this.
    """
    import numpy as np

    from zgrader.analysis.preprocessing import _order_points
    from zgrader.auth.security import create_access_token
    from zgrader.db import SessionLocal

    with SessionLocal() as session:
        submission = session.query(Submission).filter(Submission.submission_code == code).one()
        token = create_access_token(str(submission.user_id), submission.user.token_version)
    resp = client.get(f"/submissions/{code}/scans/front/suggest-crop", headers=_auth(token))
    raw_points = np.array(resp.json()["points"], dtype=np.float64)
    return _order_points(raw_points).tolist()


def _px_per_mm(code: str) -> float:
    """The px/mm `preprocessing.rectify` builds the front scan's canonical
    raster at -- the same scale `check-crop` itself uses internally, via a
    standard 63x88mm card (there is no `CardDimensionReference` row for
    "Pokemon" in the test database, so this is the same fallback size the
    endpoint would compute through `scale.dimensions_for`)."""
    from zgrader.analysis import preprocessing
    from zgrader.db import SessionLocal

    with SessionLocal() as session:
        scan = (
            session.query(ScanImage)
            .join(Submission)
            .filter(Submission.submission_code == code, ScanImage.side == ScanSide.front)
            .one()
        )
        file_path = scan.file_path
    image = preprocessing.load_image(file_path)
    rectified = preprocessing.rectify(image, 63.0, 88.0)
    return rectified.px_per_mm


def test_a_crop_whose_edge_is_not_there_names_the_side(db_session):
    """The customer dragged a side out over the backing. The check says so
    before they spend the submission, and names which side rather than the
    generic "could not fit the edges"."""
    token, code = _submission_with_front_scan("crop-disagreement@example.com")
    points = _detected_crop(code)
    # Push the bottom edge 6mm below the card, into featureless backing.
    # `pokemon_front`'s scanner-backing margin (8% of the card's shorter
    # side, ~5mm) is narrower than that, so the raw push would land outside
    # the scan and the endpoint would 400 before ever reaching geometry --
    # clamp to the image edge, which is still comfortably past the 3mm the
    # crop refit's own search band (CROP_REFIT_BAND_MM) reaches back from a
    # crop line, so the true edge stays out of the re-search entirely.
    px_per_mm = _px_per_mm(code)
    scan = (
        db_session.query(ScanImage)
        .join(Submission)
        .filter(Submission.submission_code == code, ScanImage.side == ScanSide.front)
        .one()
    )
    points[2][1] = min(points[2][1] + 6.0 * px_per_mm, float(scan.height_px))
    points[3][1] = min(points[3][1] + 6.0 * px_per_mm, float(scan.height_px))

    resp = client.post(
        f"/submissions/{code}/scans/front/check-crop",
        json={"points": points},
        headers=_auth(token),
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["boundary_found"] is False
    assert "geometry_crop_disagreement" in body["limitations"]


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
