import tempfile

import cv2

from tests.fixtures.generate_samples import make_card_scan
from zgrader.analysis import corners, preprocessing


def _deskewed(**kwargs):
    scan = make_card_scan(63.0, 88.0, **kwargs)
    fd, path = tempfile.mkstemp(suffix=".png")
    cv2.imwrite(path, scan)
    image = preprocessing.load_image(path)
    card_image, _info = preprocessing.locate_and_deskew(image)
    return card_image


def test_pristine_corners_score_near_perfect():
    result = corners.measure_corners(_deskewed())
    for corner in result["measurements"]["per_corner"].values():
        assert corner["combined_score"] >= 9.0


def test_whitened_corner_is_flagged_and_identified_as_worst():
    result = corners.measure_corners(_deskewed(whiten_top_left_corner=True))
    per_corner = result["measurements"]["per_corner"]
    assert result["measurements"]["worst_corner"] == "top_left"
    assert per_corner["top_left"]["whitening_score"] < per_corner["top_right"]["whitening_score"]
    assert per_corner["top_left"]["combined_score"] < 8.0


def test_backing_bleed_is_still_reported_but_no_longer_scored():
    """Backing bleed remains a diagnostic. It must not reach the score: it is
    only meaningful when the crop came from boundary detection, and on the
    self-serve path the crop comes from the customer's own handle drag."""
    result = corners.measure_corners(_deskewed(clip_top_left_corner=True))
    per_corner = result["measurements"]["per_corner"]

    assert per_corner["top_left"]["backing_bleed_fraction"] > 0.5
    assert per_corner["top_right"]["backing_bleed_fraction"] == 0.0
    # Reported, flagged as unscored, and genuinely absent from the score.
    for corner in per_corner.values():
        assert corner["rounding_scored"] is False
        assert corner["combined_score"] == corner["whitening_score"]


def test_backing_bleed_cannot_influence_the_score_at_any_value():
    """Regression guard for the crop-placement bug.

    rounding_score was half of every corner's score and came from backing
    visible at crop[0, 0], so a customer cropping tight read 10.0 on a wrecked
    corner and a customer cropping loose read 0.0 on a clean one. Asserting the
    invariant directly is stronger than simulating a crop shift: these
    fixtures paint damage within ~3% of the tip, so any trim large enough to
    hide the backing also removes the damage itself, and no pixel-level
    fixture here can separate the two effects. A real loose/tight-crop pair
    belongs in the phase-1 fixture set.
    """
    clean = corners.measure_corners(_deskewed())["measurements"]["per_corner"]
    clipped = corners.measure_corners(_deskewed(clip_top_left_corner=True))["measurements"][
        "per_corner"
    ]

    # Backing bleed spans its full range across these two cards...
    assert clipped["top_left"]["backing_bleed_fraction"] == 1.0
    assert clean["top_left"]["backing_bleed_fraction"] == 0.0
    # ...and in every case the score is exactly the whitening measurement,
    # so no amount of backing can move it in either direction.
    for per_corner in (clean, clipped):
        for corner in per_corner.values():
            assert corner["combined_score"] == corner["whitening_score"]


def test_corners_declares_what_it_does_not_measure():
    result = corners.measure_corners(_deskewed())
    assert result["flags"]["lower_confidence"] is True
    assert "Material loss" in result["flags"]["reason"]
