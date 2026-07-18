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


def test_clipped_corner_is_flagged_via_backing_bleed():
    result = corners.measure_corners(_deskewed(clip_top_left_corner=True))
    per_corner = result["measurements"]["per_corner"]
    assert per_corner["top_left"]["backing_bleed_fraction"] > 0.5
    assert per_corner["top_left"]["combined_score"] < 3.0
    assert per_corner["top_right"]["backing_bleed_fraction"] == 0.0
