"""Corners now measure two different things, and this file is mostly about
keeping them honest about which one fired.

The previous version of this file tested a category that measured
discolouration only, and its central assertion was that the backing-bleed
diagnostic could *not* influence the score -- a guard against the
crop-placement bug, where a corner's score depended on where the customer
dragged a handle. That guard has been deliberately reversed rather than
deleted: material loss at the apex is now the primary measurement, and it is
sound because the apex comes from intersected fitted lines instead of from
wherever the card's material happened to end. The test that replaces it
asserts the property that makes the reversal safe.
"""

import numpy as np
import pytest

from tests.fixtures.generate_samples import build_fixture, card_size_mm, make_card_scan
from zgrader.analysis import assessment, corners, preprocessing, regions, scoring
from zgrader.models import AnalysisCategory


def _rectified(**kwargs):
    """A card through the shipped path, so material loss is measurable."""
    scan = make_card_scan(63.0, 88.0, **kwargs)
    return preprocessing.rectify(scan, 63.0, 88.0)


def _measure(**kwargs) -> dict:
    card = _rectified(**kwargs)
    return corners.measure_corners(card.image, px_per_mm=card.px_per_mm, mask=card.mask)


# --- Material loss ---------------------------------------------------------


def test_a_clipped_corner_is_now_penalised():
    """The headline change. A corner with a bite out of it used to score
    exactly as well as a clean one, because only discolouration counted."""
    clean = _measure()["measurements"]["per_corner"]
    clipped = _measure(clip_top_left_corner=True)["measurements"]["per_corner"]

    assert clipped["top_left"]["excess_area_mm2"] > clean["top_left"]["excess_area_mm2"]
    assert clipped["top_left"]["combined_score"] < clean["top_left"]["combined_score"]
    assert _measure(clip_top_left_corner=True)["measurements"]["worst_corner"] == "top_left"


def test_a_mint_corner_is_barely_penalised_for_its_factory_radius():
    """A card is cut to a ~1.5mm corner radius, so a perfect corner is already
    missing area relative to the ideal rectangle it is rectified to. Almost all
    of that is forgiven; a little is not, and the bound matters.

    What is left is pixel quantisation. The mask is binary, so its boundary
    sits a whole number of pixels inside the ideal edge, and the calibration
    that removes that can only remove whole pixels too. One pixel at 23.6 px/mm
    over a 5mm window is 0.21mm^2, which is exactly the spread seen between a
    card's left and right corners. On a real, slightly rotated card the edge
    crosses pixel rows at an angle and the effect largely averages out; on an
    axis-aligned synthetic it cannot.

    So this asserts a ceiling rather than zero. Left unbounded it would be a
    systematic sag on every mint card, which is worse than noise because it
    compounds with the uncalibrated constants around it.
    """
    per_corner = _measure()["measurements"]["per_corner"]
    for name, corner in per_corner.items():
        assert corner["missing_area_mm2"] > 0.0, f"{name}: no factory rounding seen at all"
        assert corner["excess_area_mm2"] < 0.25, (
            f"{name}: {corner['excess_area_mm2']}mm2 read as damage on a mint corner -- "
            "more than pixel quantisation explains"
        )
        assert corner["combined_score"] >= 9.4


def test_a_known_corner_radius_is_recovered_from_the_image():
    """End-to-end check of the measurement chain against a known ground truth.

    The fixtures are die-cut at a known radius, so measuring the geometric
    prediction back off them exercises mask, rectification, inset calibration
    and area arithmetic together. Worth being precise about what it proves:
    the fixture radius comes from the same assumption the constant does, so
    this confirms the *measurement*, not that 1.5mm is right for a real
    Pokemon card. Only calipers settle that.
    """
    nominal = scoring.nominal_corner_deficit_mm2()
    measured = [
        c["missing_area_mm2"]
        for name in ("yugioh_front", "centering_perfect")
        for c in corners.measure_corners(
            *_fixture_args(name)
        )["measurements"]["per_corner"].values()
    ]
    assert min(measured) < nominal < max(measured), (
        f"clean corners measure {min(measured):.2f}-{max(measured):.2f}mm2 against a "
        f"geometric prediction of {nominal:.2f}mm2 -- they should straddle it"
    )


def test_the_deficit_does_not_depend_on_the_window_it_was_measured_in():
    """The bug this caught was subtle and looked plausible.

    The mask comes from a threshold and sits about a pixel inside the sub-pixel
    line fit the raster was built from, so every window accumulated a sliver of
    "missing" material along its two straight sides. A mint corner's deficit
    grew with the window -- 0.61mm2 at 2.5mm, 0.82 at 5mm, 1.24 at 10mm --
    which is not a property of any corner. Once the boundary offset is
    calibrated off the straight edges, the number is a constant.
    """
    card = preprocessing.rectify(
        build_fixture("centering_perfect"), *card_size_mm("centering_perfect")
    )
    areas = []
    for window_mm in (3.5, 5.0, 7.0, 10.0):
        size = int(round(window_mm * card.px_per_mm))
        areas.append(
            corners._material_loss(card.mask[0:size, 0:size], card.px_per_mm)[
                "missing_area_mm2"
            ]
        )
    assert max(areas) - min(areas) < 0.05, f"deficit still tracks the window: {areas}"


def _fixture_args(name: str):
    card = preprocessing.rectify(build_fixture(name), *card_size_mm(name))
    return card.image, None, card.px_per_mm, card.mask


def test_apex_offset_separates_a_bite_from_even_rounding():
    """Area alone cannot tell a corner evenly worn from one with a single deep
    chip. How far the tip itself has been pushed back can."""
    clean = _measure()["measurements"]["per_corner"]["top_left"]
    clipped = _measure(clip_top_left_corner=True)["measurements"]["per_corner"]["top_left"]
    assert clipped["apex_offset_mm"] > clean["apex_offset_mm"]


def test_the_measured_area_matches_the_damage_that_was_drawn():
    """Ground truth, not just discrimination.

    The fixture removes a square of 2.5% of the card's short side, which at
    63mm across is about 1.58mm on a side, so 2.5mm^2 of card is gone. That
    square fully contains the factory rounding, so the whole of it should come
    back as missing material. If this drifts, the millimetre figures printed on
    a customer's report have drifted with it -- and unlike a 0-10 score, those
    are checkable against the card in their hand.
    """
    card = _rectified(clip_top_left_corner=True)
    # The generator cuts 2.5% of the card's short side, which is 63mm.
    clip_side_mm = 0.025 * 63.0
    expected_mm2 = clip_side_mm**2

    corner = corners.measure_corners(
        card.image, px_per_mm=card.px_per_mm, mask=card.mask
    )["measurements"]["per_corner"]["top_left"]

    assert corner["missing_area_mm2"] == pytest.approx(expected_mm2, rel=0.2), (
        f"measured {corner['missing_area_mm2']}mm2 against {expected_mm2:.2f}mm2 drawn"
    )
    # The tip is pushed back by roughly the diagonal of that square.
    assert corner["apex_offset_mm"] == pytest.approx(clip_side_mm * 1.41, rel=0.35)


# --- Whitening -------------------------------------------------------------


def test_a_whitened_corner_reads_as_lighter_and_less_colourful():
    """Both Lab channels, because that is what whitening physically is. HSV
    saturation collapsed the two and could not distinguish a dark border from
    a bleached one."""
    result = _measure(whiten_top_left_corner=True)
    per_corner = result["measurements"]["per_corner"]

    assert result["measurements"]["worst_corner"] == "top_left"
    assert per_corner["top_left"]["lightness_rise"] > per_corner["top_right"]["lightness_rise"]
    assert per_corner["top_left"]["chroma_loss"] > per_corner["top_right"]["chroma_loss"]
    assert per_corner["top_left"]["combined_score"] < 8.0


def test_backing_is_excluded_from_the_tip_colour_sample():
    """Without the mask, a chipped corner's exposed backing lands in the very
    region being sampled for whitening -- and dark backing reads as the
    opposite of whitening, so the worst corners would look the cleanest.
    """
    card = _rectified(clip_top_left_corner=True)
    size = corners._window_px(card.image, card.px_per_mm)
    crop = corners.corner_crops(card.image, size=size)["top_left"]
    mask_crop = corners.corner_crops(card.mask, size=size)["top_left"]

    with_mask = corners._whitening(crop, mask_crop, card.px_per_mm)["lightness_rise"]
    without = corners._whitening(crop, None, card.px_per_mm)["lightness_rise"]
    assert with_mask > without, (
        "excluding the backing should stop it dragging the tip's lightness down"
    )


# --- Whether a corner's mask can be believed --------------------------------
#
# Hand-built masks rather than fixtures: each one isolates exactly one way a
# mask can disagree with the card's fitted lines. 20 px/mm over a 5mm window.

_PPM = 20.0
_SIZE = 100


def _rounded_corner(radius_mm: float = 1.5) -> np.ndarray:
    """A clean factory corner, oriented like every corner crop (apex at [0, 0])."""
    mask = np.full((_SIZE, _SIZE), 255, np.uint8)
    r = int(round(radius_mm * _PPM))
    yy, xx = np.mgrid[0:r, 0:r]
    mask[:r, :r][np.hypot(r - yy, r - xx) > r] = 0
    return mask


def test_a_clean_rounded_corner_is_readable():
    assert corners._corner_readable(_rounded_corner(), _PPM, 0.0) is None
    # Loss that is visible from the cut is what real wear looks like.
    assert corners._corner_readable(_rounded_corner(), _PPM, 0.5) is None


def test_a_bite_along_the_straight_edge_is_not_believed():
    """The failure behind 13_FrontSideAngle: the contour cut into an intact,
    cleanly rounded corner along its edge, and 7.72mm2 of "loss" zeroed it. A
    median of the edge inset cannot see a bite covering under half the section,
    which is why the fraction of deviating lines is checked separately."""
    mask = _rounded_corner()
    mask[70:82, :12] = 0  # 30% of the straight section, 0.6mm deep
    assert corners._corner_readable(mask, _PPM, 1.0) == "straight"


def test_a_line_with_no_material_counts_as_deviating():
    """_edge_inset_px drops a line with no material, which is right for a
    calibration and wrong here: an empty line is the most extreme deviation
    there is, not one to ignore."""
    mask = _rounded_corner()
    mask[70:76, :] = 0  # 15% of the straight section, no material at all
    assert corners._corner_readable(mask, _PPM, 1.0) == "straight"


def test_a_mask_sitting_inside_the_fitted_lines_is_not_believed():
    mask = _rounded_corner()
    mask[:, :10] = 0
    mask[:10, :] = 0  # 0.5mm inside both lines
    assert corners._corner_readable(mask, _PPM, 1.0) == "inset"


def test_loss_that_cannot_see_the_cut_is_not_believed_when_it_is_scored():
    """Real corner loss is reachable from the cut along a row or a column;
    misclassified speckle inside the card is not. Checked only when there is
    excess to score -- speckle that costs nothing need not decline anything."""
    mask = _rounded_corner()
    mask[40:51, 40:51] = 0
    assert corners._corner_readable(mask, _PPM, 0.5) == "visibility"
    assert corners._corner_readable(mask, _PPM, 0.0) is None


def test_one_unreadable_corner_declines_the_whole_category():
    """Corners are scored worst-anchored, so a score from three corners cannot
    know it skipped the worst one. The bite here runs along the bottom edge of
    the bottom-left corner, clear of the factory rounding -- the shape of the
    contour failure seen on real photographs."""
    card = _rectified()
    ppm = card.px_per_mm
    mask = card.mask.copy()
    h = mask.shape[0]
    mask[h - int(round(0.8 * ppm)) :, int(round(3.2 * ppm)) : int(round(3.8 * ppm))] = 0

    result = corners.measure_corners(card.image, px_per_mm=ppm, mask=mask)

    assert result["raw_score"] is None
    assert result["measurements"]["unreadable_corners"] == ["bottom_left"]
    assert result["measurements"]["per_corner"]["bottom_left"]["boundary_check"] == "straight"
    assert (
        assessment.CORNERS_BOUNDARY_UNREADABLE
        in result["measurements"]["assessment"]["limitations"]
    )
    assert "bottom left" in result["flags"]["reason"]
    assert regions.build_regions(
        AnalysisCategory.corners, card.image.shape[:2], ppm, "en", result, None
    ) == []


def test_real_damage_is_measured_not_gated_away():
    """The check exists to refuse a mask that is wrong, never to refuse damage.
    A clipped corner is exactly the loss corners exists to report."""
    card = _rectified(clip_top_left_corner=True)
    result = corners.measure_corners(card.image, px_per_mm=card.px_per_mm, mask=card.mask)

    top_left = result["measurements"]["per_corner"]["top_left"]
    assert top_left["boundary_check"] is None
    assert top_left["excess_area_mm2"] == pytest.approx(1.59, abs=0.3)
    assert result["raw_score"] is not None
    assert result["measurements"]["unreadable_corners"] == []


# --- Aggregation -----------------------------------------------------------


def test_one_destroyed_corner_is_not_diluted_by_three_clean_ones():
    """A plain mean let one wrecked corner cost a quarter of the category.
    Corners are graded on the worst one."""
    assert scoring.corners_category_score([10.0, 10.0, 10.0, 0.0]) == pytest.approx(3.75)
    # ...and a card that is uniformly good is unaffected by the change.
    assert scoring.corners_category_score([10.0, 10.0, 10.0, 10.0]) == pytest.approx(10.0)


def test_the_category_score_tracks_its_worst_corner():
    clipped = _measure(clip_top_left_corner=True)
    per_corner = clipped["measurements"]["per_corner"]
    worst = min(c["combined_score"] for c in per_corner.values())
    assert clipped["raw_score"] < sum(c["combined_score"] for c in per_corner.values()) / 4
    assert clipped["raw_score"] > worst


# --- Degrading honestly ----------------------------------------------------


def test_without_a_mask_the_category_declines():
    """There is no scored whitening-only path any more. Whitening sampled with
    no mask measures whatever sits behind the rounded corner -- on a real
    photograph, the desk -- and real photographs read lightness "rises" of -40
    to -150 there, which clip to zero and score a clean corner. A reading with
    nothing behind it declines instead."""
    card = _rectified()
    result = corners.measure_corners(card.image, px_per_mm=card.px_per_mm, mask=None)

    assert result["raw_score"] is None
    block = result["measurements"]["assessment"]
    assert block["state"] == assessment.UNMEASURABLE
    assert assessment.CORNERS_BOUNDARY_UNREADABLE in block["limitations"]
    assert assessment.CORNERS_WHITENING_ONLY not in block["limitations"]
    assert result["flags"]["lower_confidence"] is True


def test_with_a_mask_the_whitening_only_caveat_is_gone():
    """It would be a lie: material loss is exactly what was measured."""
    result = _measure()

    assert result["measurements"]["material_measured"] is True
    limitations = result["measurements"]["assessment"]["limitations"]
    assert assessment.CORNERS_WHITENING_ONLY not in limitations
    assert result["flags"] == {}


def test_a_pale_border_lowers_confidence_but_material_is_still_measured():
    """A pale border disables the colour half of the corner reading, not the
    material half, so it costs confidence without costing the measurement."""
    pale = preprocessing.rectify(build_fixture("white_border_clean"), *card_size_mm("white_border_clean"))
    plain = preprocessing.rectify(build_fixture("centering_perfect"), *card_size_mm("centering_perfect"))
    pale_result = corners.measure_corners(pale.image, px_per_mm=pale.px_per_mm, mask=pale.mask)
    plain_result = corners.measure_corners(plain.image, px_per_mm=plain.px_per_mm, mask=plain.mask)

    pale_block = pale_result["measurements"]["assessment"]
    assert assessment.CORNERS_PALE_BORDER in pale_block["limitations"]
    assert pale_result["measurements"]["material_measured"] is True
    assert pale_block["confidence"] < plain_result["measurements"]["assessment"]["confidence"]


def test_a_capture_too_small_to_measure_still_declines_to_score():
    """The resolution gate outranks everything here: below the floor there is
    nothing to measure with either channel."""
    card = _rectified()
    result = corners.measure_corners(card.image, px_per_mm=7.0, mask=card.mask)
    assert result["raw_score"] is None
    assert result["measurements"]["assessment"]["state"] == assessment.UNMEASURABLE


def test_a_shadowed_corner_is_declined_not_scored_as_damage():
    """The regression the drift baseline could not otherwise hold -- every
    other synthetic fixture fits its mask cleanly.

    A soft shadow darkens an intact bottom-left corner until its border falls
    below the threshold separating card from backing: the mechanism behind
    13_FrontSideAngle, where a border indistinguishable from the backdrop let
    the contour bite 7.72mm2 out of a corner that was not damaged. The old
    whole-raster gate passed this card and scored the bite as lost material.
    """
    name = "capture_shadowed_corner"
    card = preprocessing.rectify(build_fixture(name), *card_size_mm(name))
    assert float(np.mean(card.mask == 0)) < 0.01, "fixture no longer passes the old global gate"

    result = corners.measure_corners(card.image, px_per_mm=card.px_per_mm, mask=card.mask)
    bottom_left = result["measurements"]["per_corner"]["bottom_left"]

    assert bottom_left["excess_area_mm2"] > 1.0, "fixture no longer invents loss at the corner"
    assert bottom_left["boundary_check"] is not None
    assert result["raw_score"] is None
