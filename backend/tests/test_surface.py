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


def test_an_image_with_no_fine_detail_is_declined_not_scored():
    """The capture gate, and the reason a flat synthetic exercises it.

    A bare generated card is flat fill: its interior has a raw anomaly
    fraction of exactly 0.0, because there is nothing in it at any scale. Every
    real card has micro-texture -- paper fibre, print rosettes -- and a
    photograph of one flags 2.4-3.3%, so a reading of zero does not mean "this
    card is flawless", it means the image has nothing in it to find.

    It used to score a flat 10.0, which is absence of evidence as perfection --
    the pattern the resolution gate removed from corners and edges while
    surface had no capture gate at all. Blur and blown-out glare produce the
    same reading on a real photograph: the deliberately soft fixture measures
    0.0000 and the glared one 0.0003.
    """
    result, _mask = surface.measure_surface(_deskewed())

    assert result["measurements"]["raw_anomaly_fraction"] == 0.0
    assert result["raw_score"] is None
    assert result["measurements"]["assessment"]["state"] == "unmeasurable"
    assert "surface_no_detail" in result["measurements"]["assessment"]["limitations"]


def test_a_card_with_detail_is_scored_and_a_scratch_lowers_it():
    """Once there is anything to see, the category behaves as before."""
    clean, _ = surface.measure_surface(_deskewed(add_surface_scratch=True))

    assert clean["raw_score"] is not None
    assert clean["raw_score"] >= 9.0
    assert clean["measurements"]["raw_anomaly_fraction"] > 0.0


def test_scratch_is_detected_as_anomaly():
    scratched, mask = surface.measure_surface(_deskewed(add_surface_scratch=True))
    assert scratched["measurements"]["anomaly_fraction"] > 0.0
    assert mask.any()


def test_surface_always_flags_lower_confidence():
    """True either way -- the wording differs, the flag does not."""
    scored, _ = surface.measure_surface(_deskewed(add_surface_scratch=True))
    declined, _ = surface.measure_surface(_deskewed())
    assert scored["flags"]["lower_confidence"] is True
    assert declined["flags"]["lower_confidence"] is True
