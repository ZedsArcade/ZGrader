import tempfile

import cv2

from tests.fixtures.generate_samples import make_card_scan
from zgrader.analysis import preprocessing, surface


def _deskewed(**kwargs):
    scan = make_card_scan(63.0, 88.0, **kwargs)
    fd, path = tempfile.mkstemp(suffix=".png")
    cv2.imwrite(path, scan)
    image = preprocessing.load_image(path)
    card_image, _info = preprocessing.locate_and_deskew(image)
    return card_image


def test_clean_surface_scores_high():
    result, mask = surface.measure_surface(_deskewed())
    assert result["raw_score"] >= 9.0
    assert mask.any() == False or mask.mean() < 0.01  # noqa: E712


def test_scratch_is_detected_as_anomaly():
    clean, _ = surface.measure_surface(_deskewed())
    scratched, mask = surface.measure_surface(_deskewed(add_surface_scratch=True))
    assert scratched["measurements"]["anomaly_fraction"] > clean["measurements"]["anomaly_fraction"]
    assert scratched["raw_score"] < clean["raw_score"]
    assert mask.any()


def test_surface_always_flags_lower_confidence():
    result, _mask = surface.measure_surface(_deskewed())
    assert result["flags"]["lower_confidence"] is True
