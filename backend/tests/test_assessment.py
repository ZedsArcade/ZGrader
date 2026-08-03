"""Confidence, intervals and limitation codes.

The scores themselves are covered by the per-category tests and the drift
harness. What matters here is the honesty layer: whether the pipeline admits
what it could not see well, on the cards where that is actually true.
"""

import tempfile

import cv2
import pytest

from tests.fixtures.generate_samples import build_fixture, card_size_mm, make_card_scan
from zgrader.analysis import assessment, centering, corners, edges, preprocessing, scale, surface


def _analyse(name: str) -> dict:
    """Every category's assessment block for one catalogue fixture."""
    image = build_fixture(name)
    card, _info = preprocessing.locate_and_deskew(image)
    px_per_mm = scale.px_per_mm(card.shape[:2], *card_size_mm(name))
    surface_result, _mask = surface.measure_surface(card)
    return {
        "centering": centering.measure_centering(card, px_per_mm)["measurements"]["assessment"],
        "corners": corners.measure_corners(card)["measurements"]["assessment"],
        "edges": edges.measure_edges(card)["measurements"]["assessment"],
        "surface": surface_result["measurements"]["assessment"],
    }


@pytest.mark.parametrize("category", ["centering", "corners", "edges", "surface"])
def test_every_category_reports_an_assessment(category):
    block = _analyse("pokemon_back")[category]
    assert block["state"] == assessment.MEASURED
    assert 0.0 <= block["confidence"] <= 1.0
    assert block["score_low"] <= block["score_high"]


@pytest.mark.parametrize("category", ["centering", "corners", "edges", "surface"])
def test_limitation_codes_are_all_known(category):
    """A code with no copy behind it would render as a raw identifier to a
    customer, so the set is closed deliberately."""
    for code in _analyse("pokemon_back")[category]["limitations"]:
        assert code in assessment.ALL_LIMITATION_CODES


def test_surface_always_admits_the_lighting_limitation():
    """Diffuse light is a property of how the card is captured, not of the
    card, so this is not conditional on anything."""
    block = _analyse("pokemon_back")["surface"]
    assert assessment.SURFACE_DIFFUSE_LIGHT in block["limitations"]
    assert block["confidence"] == assessment.CONFIDENCE_SURFACE


def test_corners_always_admit_that_material_loss_is_not_measured():
    block = _analyse("pokemon_back")["corners"]
    assert assessment.CORNERS_WHITENING_ONLY in block["limitations"]


def test_a_white_border_lowers_corner_confidence():
    """The documented blind spot, now measured per card.

    Corner whitening is detected as a loss of saturation; a white border has
    almost none to lose. Reporting the same confidence here as on a
    saturated border would be the pipeline claiming a reading it cannot make.
    """
    white = _analyse("white_border_clean")["corners"]
    coloured = _analyse("pokemon_back")["corners"]

    assert assessment.CORNERS_PALE_BORDER in white["limitations"]
    assert assessment.CORNERS_PALE_BORDER not in coloured["limitations"]
    assert white["confidence"] < coloured["confidence"]


def test_full_art_lowers_centering_confidence_and_widens_the_interval():
    """No printed frame means the border measurement is a reading of noise.

    Until raw_score can be null this still emits a number, so the interval is
    what carries the doubt -- and it should be wide enough that nobody mistakes
    it for a measurement.
    """
    full_art = _analyse("full_art_centered")["centering"]
    bordered = _analyse("pokemon_back")["centering"]

    assert assessment.CENTERING_NO_FRAME in full_art["limitations"]
    assert full_art["confidence"] < bordered["confidence"]

    full_art_width = full_art["score_high"] - full_art["score_low"]
    bordered_width = bordered["score_high"] - bordered["score_low"]
    assert full_art_width > bordered_width


def test_interval_widens_as_confidence_falls():
    assert assessment.interval_for(5.0, 1.0) == (5.0, 5.0)
    low_lo, low_hi = assessment.interval_for(5.0, 0.2)
    high_lo, high_hi = assessment.interval_for(5.0, 0.9)
    assert (low_hi - low_lo) > (high_hi - high_lo)


def test_interval_never_leaves_the_scale():
    """A wide interval around an extreme score must not promise -1.5 or 12.3."""
    assert assessment.interval_for(0.0, 0.0)[0] == 0.0
    assert assessment.interval_for(10.0, 0.0)[1] == 10.0


def test_unmeasurable_offers_no_interval():
    """An interval implies a score exists somewhere inside it, which is
    precisely the claim being declined."""
    block = assessment.unmeasurable((assessment.CENTERING_NO_FRAME,)).as_dict()
    assert block["state"] == assessment.UNMEASURABLE
    assert block["confidence"] == 0.0
    assert block["score_low"] is None and block["score_high"] is None


def test_partially_measured_edges_lower_confidence():
    card = make_card_scan(63.0, 88.0)
    fd, path = tempfile.mkstemp(suffix=".png")
    cv2.imwrite(path, card)
    deskewed, _info = preprocessing.locate_and_deskew(preprocessing.load_image(path))

    full = edges.measure_edges(deskewed)["measurements"]["assessment"]
    assert assessment.EDGES_PARTIAL not in full["limitations"]
    assert full["confidence"] == assessment.CONFIDENCE_EDGES
