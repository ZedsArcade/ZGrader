import tempfile

import cv2
import pytest

from tests.fixtures.generate_samples import make_card_scan
from zgrader.analysis import centering, preprocessing


def _deskewed(**kwargs):
    scan = make_card_scan(63.0, 88.0, **kwargs)
    fd, path = tempfile.mkstemp(suffix=".png")
    cv2.imwrite(path, scan)
    image = preprocessing.load_image(path)
    card_image, _info = preprocessing.locate_and_deskew(image)
    return card_image


def test_centered_card_scores_near_perfect():
    card_image = _deskewed()
    result = centering.measure_centering(card_image, px_per_mm=600 / 25.4)
    assert result["measurements"]["lr_ratio"][0] == pytest.approx(50.0, abs=1.0)
    assert result["measurements"]["tb_ratio"][0] == pytest.approx(50.0, abs=1.0)
    assert result["raw_score"] >= 9.5


def test_off_center_card_measures_expected_split():
    # lr_offset_frac=0.3 with a symmetric base border produces a
    # left:right ratio of 1.3 : 0.7 -> 65.0 / 35.0
    card_image = _deskewed(lr_offset_frac=0.3)
    result = centering.measure_centering(card_image, px_per_mm=600 / 25.4)
    lr_ratio = result["measurements"]["lr_ratio"]
    assert lr_ratio[0] == pytest.approx(65.0, rel=0.05)
    assert lr_ratio[1] == pytest.approx(35.0, rel=0.05)
    assert result["measurements"]["worse_side_pct"] == pytest.approx(65.0, rel=0.05)


def test_worse_centering_scores_lower_than_better_centering():
    mild = centering.measure_centering(_deskewed(lr_offset_frac=0.1), px_per_mm=600 / 25.4)
    severe = centering.measure_centering(_deskewed(lr_offset_frac=0.4), px_per_mm=600 / 25.4)
    assert severe["raw_score"] < mild["raw_score"]


def test_clean_card_is_measured_with_confidence():
    # A synthetic card has a crisp printed border on every side, so the
    # centering measurement must NOT be flagged lower_confidence.
    result = centering.measure_centering(_deskewed(), px_per_mm=600 / 25.4)
    assert not result["flags"].get("lower_confidence")


def test_borderless_image_is_flagged_lower_confidence():
    import numpy as np

    # Uniform noise with no printed border anywhere -- the argmax edge on
    # each side is just noise, so no side clears the significance bar and
    # the result must be flagged lower_confidence rather than asserting a
    # confident (and meaningless) split.
    rng = np.random.default_rng(0)
    noise = rng.integers(90, 160, size=(800, 600, 3), dtype=np.uint8)
    result = centering.measure_centering(noise, px_per_mm=600 / 25.4)
    assert result["flags"].get("lower_confidence") is True
