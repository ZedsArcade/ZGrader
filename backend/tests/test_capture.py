"""Capture metrics, and the one gate built on top of them.

Two separate things are tested here, and the split matters:

* the metrics themselves, which are recorded and drift-tracked but decide
  nothing (capture.py's docstring explains why -- measured across the fixture
  set, sharpness and illumination uniformity track what is *printed* on the
  card as strongly as they track the photograph);
* the resolution gate, which is the only capture metric acted on, because it
  is the only one that means the same thing on every card ever printed.
"""

import numpy as np
import pytest

from zgrader.analysis import (
    assessment,
    capture,
    corners,
    edges,
    pipeline,
    preprocessing,
    regions,
    scale,
)
from zgrader.models import AnalysisCategory

from tests.fixtures.generate_samples import build_fixture, card_size_mm

# Comfortably inside each band, so a small retune of the thresholds does not
# silently turn these into tests of nothing.
TOO_LOW = 7.0
MODEST = 18.0
COMFORTABLE = 45.0


def _card(name: str):
    image = build_fixture(name)
    card, _info = preprocessing.locate_and_deskew(image)
    width_mm, height_mm = card_size_mm(name)
    return card, scale.px_per_mm(card.shape[:2], width_mm, height_mm)


# --- The metrics -----------------------------------------------------------


def test_sharpness_separates_a_soft_capture_from_the_same_card_in_focus():
    """Tenengrad's one job. Compared against the *same* card rather than
    against an absolute threshold, because the absolute value is dominated by
    card content -- which is exactly why nothing gates on it."""
    sharp, _ = _card("pokemon_front")
    soft, _ = _card("capture_soft")
    assert capture.tenengrad(_gray(soft)) < capture.tenengrad(_gray(sharp))


def test_clipping_counts_saturated_pixels():
    """Tested on constructed pixels rather than on a fixture, because the
    synthetic glare does not clip -- see the next test."""
    black = np.zeros((10, 10, 3), dtype=np.uint8)
    assert capture.clipping_fraction(black) == 0.0

    half = black.copy()
    half[:5] = 255
    assert capture.clipping_fraction(half) == pytest.approx(0.5)

    # Any single channel at saturation is a clipped pixel -- a blown red
    # highlight loses just as much information as a blown white one.
    red = black.copy()
    red[:, :, 2] = 255
    assert capture.clipping_fraction(red) == 1.0


def test_the_synthetic_glare_does_not_clip():
    """Recorded because it is the opposite of what the fixture's name implies,
    and because the next person to reach for this metric will assume otherwise.

    The generator's glare is an alpha blend that tops out around 246, so at the
    250 threshold it reads 0.0 -- while an ordinary card scores higher, since a
    printed white border genuinely does hit 255. The signal is there one stop
    down (7.4% of the glared card is above 240 against 0.07% of a clean one),
    but 250 is the right definition of clipped for a real sensor and lowering
    it to suit a synthetic would be calibrating against the fixture.

    So: this metric is validated on constructed pixels above, and confirming it
    on real glare needs a real photograph.
    """
    glared, _ = _card("capture_glared")
    assert capture.clipping_fraction(glared) == 0.0


def test_uniformity_is_bounded():
    """It is a 0-1 claim about the lighting, so it must stay one however odd
    the card is."""
    for name in ("pokemon_front", "capture_glared", "full_art_foil"):
        card, _ = _card(name)
        assert 0.0 <= capture.illumination_uniformity(_gray(card)) <= 1.0


def test_measure_capture_reports_every_metric():
    card, px_per_mm = _card("pokemon_front")
    result = capture.measure_capture(card, px_per_mm)
    assert set(result) == {
        "px_per_mm",
        "sharpness",
        "clipping_fraction",
        "illumination_uniformity",
    }


def _gray(card):
    import cv2

    return cv2.cvtColor(card, cv2.COLOR_BGR2GRAY)


# --- The gate --------------------------------------------------------------


@pytest.mark.parametrize(
    "px_per_mm,expected",
    [
        (None, (None, False)),
        (TOO_LOW, (assessment.CAPTURE_TOO_LOW_RESOLUTION, True)),
        (MODEST, (assessment.CAPTURE_MODEST_RESOLUTION, False)),
        (COMFORTABLE, (None, False)),
    ],
)
def test_the_resolution_gate_bands(px_per_mm, expected):
    assert capture.resolution_limitation(px_per_mm) == expected


def test_an_absent_scale_makes_no_claim():
    """A caller that supplies no px_per_mm gets the old behaviour, not a
    guess. Silently assuming the capture was fine would put a confidence
    number on a photograph nothing measured."""
    card, _ = _card("pokemon_front")
    result = corners.measure_corners(card)
    assert result["raw_score"] is not None
    limitations = result["measurements"]["assessment"]["limitations"]
    assert assessment.CAPTURE_MODEST_RESOLUTION not in limitations
    assert assessment.CAPTURE_TOO_LOW_RESOLUTION not in limitations


@pytest.mark.parametrize("module", [corners, edges])
def test_a_capture_too_small_to_measure_is_not_scored(module):
    """The headline behaviour. Corner and edge wear are sub-millimetre
    features; below the floor they do not exist in the image, and a number
    derived from pixels that cannot contain the signal is a fabrication."""
    card, _ = _card("pokemon_front")
    measure = module.measure_corners if module is corners else module.measure_edges

    result = measure(card, px_per_mm=TOO_LOW)

    assert result["raw_score"] is None
    block = result["measurements"]["assessment"]
    assert block["state"] == assessment.UNMEASURABLE
    assert block["limitations"] == [assessment.CAPTURE_TOO_LOW_RESOLUTION]
    # No interval either: an interval implies a score sits somewhere inside it.
    assert block["score_low"] is None and block["score_high"] is None


@pytest.mark.parametrize("module", [corners, edges])
def test_a_modest_capture_still_scores_but_at_lower_confidence(module):
    card, _ = _card("pokemon_front")
    measure = module.measure_corners if module is corners else module.measure_edges

    modest = measure(card, px_per_mm=MODEST)
    comfortable = measure(card, px_per_mm=COMFORTABLE)

    assert modest["raw_score"] == comfortable["raw_score"], (
        "the resolution band must change what the score is worth, not the score"
    )
    modest_block = modest["measurements"]["assessment"]
    comfortable_block = comfortable["measurements"]["assessment"]
    assert modest_block["state"] == assessment.MEASURED
    assert assessment.CAPTURE_MODEST_RESOLUTION in modest_block["limitations"]
    assert assessment.CAPTURE_MODEST_RESOLUTION not in comfortable_block["limitations"]
    assert modest_block["confidence"] < comfortable_block["confidence"]
    # A wider interval is the visible consequence of the lower confidence --
    # without it the reduced confidence would be a number nobody sees.
    assert modest_block["score_low"] < comfortable_block["score_low"]


def test_the_penalty_compounds_with_an_existing_limitation():
    """Multiplicative, not absolute. A pale-bordered card photographed small
    is worse off than either alone, and a fixed low value would flatten the
    two into the same reading."""
    card, _ = _card("white_border_clean")
    pale_only = corners.measure_corners(card, px_per_mm=COMFORTABLE)
    pale_and_small = corners.measure_corners(card, px_per_mm=MODEST)

    assert (
        assessment.CORNERS_PALE_BORDER
        in pale_only["measurements"]["assessment"]["limitations"]
    )
    assert pale_and_small["measurements"]["assessment"]["confidence"] == pytest.approx(
        pale_only["measurements"]["assessment"]["confidence"]
        * assessment.CONFIDENCE_MODEST_RESOLUTION_FACTOR,
        abs=0.01,
    )


def test_the_low_resolution_fixture_is_actually_below_the_floor():
    """Guards the fixture, not the code. The gate above is only exercised by
    the real pipeline if some fixture genuinely lands under the floor."""
    _card_image, px_per_mm = _card("capture_low_resolution")
    assert px_per_mm < capture.RESOLUTION_FLOOR_PX_PER_MM


def test_the_ordinary_fixtures_land_in_the_modest_band():
    """Recorded rather than tuned around. The synthetic cards render at about
    23.6 px/mm, just under the comfortable threshold, so every one of them
    carries a modest-resolution limitation. That is uncomfortable but true --
    and moving the threshold down to 23 to make the test data look better
    would be calibrating against the fixtures instead of against the card.

    Real captures clear it easily: a 1200dpi flatbed is ~47 px/mm and a phone
    photo filling the frame is ~34.
    """
    _card_image, px_per_mm = _card("pokemon_front")
    assert (
        capture.RESOLUTION_FLOOR_PX_PER_MM
        <= px_per_mm
        < capture.RESOLUTION_COMFORTABLE_PX_PER_MM
    )


# --- What the customer actually sees ---------------------------------------


@pytest.mark.parametrize(
    "category,module",
    [(AnalysisCategory.corners, corners), (AnalysisCategory.edges, edges)],
)
def test_an_unscored_category_produces_no_regions(category, module):
    """Every region carries a severity, and both values are claims: "ok"
    asserts that part of the card was checked and found clean. Emitting them
    for a category that declined to measure would put four green corner boxes
    on a photo nothing could read."""
    card, _ = _card("pokemon_front")
    measure = module.measure_corners if module is corners else module.measure_edges
    result = measure(card, px_per_mm=TOO_LOW)

    built = regions.build_regions(
        category, card.shape[:2], TOO_LOW, "en", result, None
    )
    assert built == []


@pytest.mark.parametrize(
    "category,module",
    [(AnalysisCategory.corners, corners), (AnalysisCategory.edges, edges)],
)
def test_an_unscored_category_still_produces_an_image(category, module):
    """The report and the results page both fetch {side}_{category}.png
    unconditionally, so declining to score must not leave a missing file --
    it leaves an unannotated one."""
    card, _ = _card("pokemon_front")
    measure = module.measure_corners if module is corners else module.measure_edges
    result = measure(card, px_per_mm=TOO_LOW)

    image = pipeline._annotate_category(category, card, result, None)
    assert image.size == (card.shape[1], card.shape[0])
    # Unannotated: identical to the plain deskewed card, pixel for pixel.
    assert np.array_equal(np.asarray(image), np.asarray(pipeline.annotate.to_pil(card)))


def test_unmeasurable_centering_no_longer_crashes_the_annotator():
    """A latent KeyError, found while wiring this gate up. annotate_centering
    reads left_px off the top-level measurements, and an unmeasurable
    centering result moves the whole reading under `indicative_estimate` -- so
    a genuine full-art card would have failed the pipeline outright rather
    than reporting that centering could not be measured.
    """
    card, px_per_mm = _card("full_art_centered")
    from zgrader.analysis import centering

    result = centering.measure_centering(card, px_per_mm)
    assert result["raw_score"] is None, "fixture no longer exercises the no-frame path"

    image = pipeline._annotate_category(AnalysisCategory.centering, card, result, None)
    assert image.size == (card.shape[1], card.shape[0])


@pytest.mark.parametrize("code", assessment.ALL_LIMITATION_CODES)
def test_every_limitation_code_has_copy_in_both_languages(code):
    """A code with no words renders as a raw identifier to a customer. The
    coupling is the point -- adding a limitation means writing the sentence."""
    from zgrader.reports.strings import LIMITATION_LABELS

    for language in ("en", "es"):
        assert code in LIMITATION_LABELS[language], (
            f"{code} has no {language} label in reports/strings.py"
        )
