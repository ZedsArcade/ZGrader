"""Where the card's edges are, and who gets to decide.

Two things are being protected here. The first is accuracy: fitted lines
should recover an apex a chipped corner has destroyed, and sub-pixel
refinement should beat the pixel grid it starts from. The second is
provenance: the customer's crop must stop being the geometry, and when the
fit cannot be trusted the output must say so rather than quietly carry on.
"""

import cv2
import numpy as np
import pytest

from zgrader.analysis import assessment, geometry, preprocessing

from tests.fixtures.generate_samples import build_fixture, card_size_mm

POKEMON_MM = (63.0, 88.0)


def _rectify(name: str, **kwargs) -> preprocessing.RectifiedCard:
    width_mm, height_mm = card_size_mm(name)
    return preprocessing.rectify(build_fixture(name), width_mm, height_mm, **kwargs)


def _detect(name: str):
    image = build_fixture(name)
    box, info = preprocessing.detect_boundary(image)
    return image, info["contour"], box


# --- The line fit ----------------------------------------------------------


def test_the_contour_is_dense_enough_to_fit_through():
    """The bug that made the whole module a no-op when first wired up.

    findContours with CHAIN_APPROX_SIMPLE compresses a straight run to its two
    endpoints, and a cleanly cut card is almost entirely straight runs -- so
    the boundary arrived as a handful of points and every fit was declined.
    """
    _image, contour, _box = _detect("pokemon_front")
    assert len(contour) > 4 * geometry.MIN_POINTS_PER_SIDE


def test_ransac_ignores_a_cluster_of_outliers():
    """A least-squares fit would let these tilt the line. That is the whole
    reason for the consensus step: a chipped corner or a thumb at one end of
    an edge must move the fitted line by nothing at all."""
    xs = np.linspace(0, 200, 120)
    points = np.column_stack([xs, np.full_like(xs, 50.0)])
    points[:15, 1] = 90.0  # a fat excursion at one end

    normal, offset, mask = geometry.fit_line_ransac(points)

    # The line should still be y = 50, i.e. horizontal with offset 50.
    assert abs(abs(normal[1]) - 1.0) < 1e-3
    assert abs(abs(offset) - 50.0) < 0.05
    assert mask.sum() == len(points) - 15


def test_the_fit_is_deterministic():
    """RANSAC samples at random, and the drift harness compares numbers across
    runs. A seed that moved would make every fixture report drift that is not
    there, and the first thing anyone would do is stop trusting the alarm."""
    image, contour, box = _detect("pokemon_front")
    first = geometry.fit_card_geometry(image, contour, box)
    second = geometry.fit_card_geometry(image, contour, box)
    assert np.allclose(first.apexes, second.apexes)


def test_total_least_squares_handles_a_vertical_edge():
    """Two of a card's four sides are vertical, where an ordinary
    least-squares fit is undefined in the limit and badly conditioned near
    it."""
    ys = np.linspace(0, 300, 100)
    points = np.column_stack([np.full_like(ys, 17.0), ys])
    normal, offset = geometry._fit_total_least_squares(points)
    assert abs(abs(normal[0]) - 1.0) < 1e-6
    assert abs(abs(offset) - 17.0) < 1e-6


# --- Sub-pixel refinement --------------------------------------------------


def test_refinement_finds_an_edge_the_pixel_grid_cannot_express():
    """A synthetic edge placed at x = 40.5 -- deliberately between two pixel
    centres, which is precisely what a whole-pixel contour cannot represent.

    Built as an anti-aliased ramp because that is what a real boundary looks
    like: a sensor integrates over a pixel, so a straight edge crossing one
    lands as an intermediate value rather than a hard step.
    """
    h, w = 200, 120
    true_x = 40.5
    xs = np.arange(w, dtype=np.float32)
    ramp = np.clip(true_x + 0.5 - xs, 0.0, 1.0)
    image = np.repeat((ramp * 255)[None, :], h, axis=0).astype(np.uint8)
    image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    value = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 2]
    # A coarse fit a pixel off, as a thresholded contour would give.
    normal = np.array([1.0, 0.0])
    offset = 40.0
    result = geometry._refine_side(
        value,
        normal,
        offset,
        np.array([offset, 20.0]),
        np.array([offset, h - 20.0]),
        normal,
    )
    assert result is not None
    refined, _residuals = result
    assert abs(float(np.median(refined[:, 0])) - true_x) < 0.25


def test_refinement_declines_when_the_edge_is_not_visible():
    """A flat grey field has no edge in it. Returning a line fitted to the
    noise floor would be worse than returning nothing, because everything
    downstream would treat it as a located boundary."""
    value = np.full((200, 120), 128, dtype=np.uint8)
    normal = np.array([1.0, 0.0])
    result = geometry._refine_side(
        value, normal, 40.0, np.array([40.0, 20.0]), np.array([40.0, 180.0]), normal
    )
    assert result is None


def test_refinement_engages_on_every_side_of_a_real_fixture():
    """Guards against the fit silently degrading to its coarse fallback --
    which still returns a plausible CardGeometry, just without the precision
    the module exists for."""
    card = _rectify("pokemon_front")
    assert card.geometry["method"] == "ransac"
    assert all(side["refined"] for side in card.geometry["sides"].values())


# --- Apexes ----------------------------------------------------------------


def test_a_clipped_corner_does_not_pull_its_apex_inward():
    """The measurement the old code could not express.

    approxPolyDP puts a corner where the card's material ends, so a chipped
    corner is traced tight and the damage is cropped out of the image before
    anything measures it. Fitted lines know nothing about the corners -- they
    are fitted from the straight parts and extrapolated -- so the apex lands
    where a perfect corner would be and the missing material stays visible.
    """
    intact = _rectify("pokemon_front")
    clipped = _rectify("damage_corner_clipped")

    # Same generator, same card size, so the two rasters should agree closely.
    # If the clipped corner were pulling its apex in, the card would come out
    # measurably smaller on that diagonal.
    assert intact.image.shape == clipped.image.shape
    assert clipped.geometry["method"] == "ransac"


def test_corner_margins_are_excluded_from_the_fit():
    """The margin is what makes the apex extrapolated rather than observed. A
    factory corner radius is about 1.5mm and damage extends further, so points
    near a corner describe the rounding, not the edge."""
    _image, contour, box = _detect("pokemon_front")
    sides = geometry._split_sides(contour, box)

    ordered = geometry._order_quad(box)
    top_left, top_right = ordered[0], ordered[1]
    length = np.linalg.norm(top_right - top_left)
    direction = (top_right - top_left) / length
    positions = (sides["top"] - top_left) @ direction / length

    assert positions.min() >= geometry.CORNER_MARGIN_FRACTION - 0.02
    assert positions.max() <= 1.0 - geometry.CORNER_MARGIN_FRACTION + 0.02


# --- Residuals -------------------------------------------------------------


def test_residuals_separate_a_clean_edge_from_a_ragged_one():
    """Retained, not scored -- edges consumes them in a later phase. Worth a
    test now because they are the only evidence the sub-pixel work produced
    something with signal in it rather than just smaller numbers."""
    clean = _rectify("pokemon_front")
    ragged = _rectify("capture_worst_case")

    clean_worst = max(s["roughness_px"] for s in clean.geometry["sides"].values())
    ragged_worst = max(s["roughness_px"] for s in ragged.geometry["sides"].values())
    assert ragged_worst > 10 * clean_worst


def test_bow_is_not_just_roughness_again():
    """A warped card and a nicked one both have large residuals; the
    difference is that a bow is a low-order trend along the edge. Fitting a
    quadratic and taking its own deviation from its chord isolates it."""
    ts = np.linspace(-1, 1, 100)
    bowed = 4.0 * (1 - ts**2)
    rough = np.tile([-4.0, 4.0], 50)

    assert geometry._bow(bowed) > 3.0
    assert geometry._bow(rough) < 0.5


# --- Canonical raster ------------------------------------------------------


def test_the_raster_has_the_card_s_true_aspect():
    """Previously the output size came from the detected quad's own edge
    lengths, so a slightly wrong crop produced a slightly wrong shape and
    px/mm was an average of two axes that disagreed."""
    card = _rectify("pokemon_front")
    width_mm, height_mm = card_size_mm("pokemon_front")
    h, w = card.image.shape[:2]
    assert abs((w / h) / (width_mm / height_mm) - 1.0) < 0.01


def test_px_per_mm_is_exact_rather_than_inferred():
    """The raster was built at this scale, so the relationship is definitional
    -- not a measurement that can drift from the image it describes."""
    card = _rectify("pokemon_front")
    width_mm, height_mm = card_size_mm("pokemon_front")
    h, w = card.image.shape[:2]
    assert w == pytest.approx(width_mm * card.px_per_mm, abs=1.0)
    assert h == pytest.approx(height_mm * card.px_per_mm, abs=1.0)


def test_perspective_is_removed_rather_than_measured_as_a_defect():
    """The clearest single gain in this change. A tilted photo of a perfectly
    centred card used to report it 61/39 off-centre, because the quad's own
    edge lengths carried the foreshortening straight into the raster."""
    from zgrader.analysis import centering

    tilted = _rectify("capture_tilted")
    result = centering.measure_centering(tilted.image, tilted.px_per_mm)
    assert result["raw_score"] is not None
    assert result["measurements"]["worse_side_pct"] < 52.0


def test_a_sideways_card_is_not_squashed_into_portrait():
    """A landscape capture is still a card. Without the swap the canonical
    raster would force it upright and every millimetre figure would be wrong
    by the aspect ratio -- which the old code did silently."""
    apexes = np.array([[0, 0], [880, 0], [880, 630], [0, 630]], dtype=np.float64)
    out_w, out_h, px_per_mm, deviation, _expected = preprocessing._canonical_size(
        apexes, *POKEMON_MM
    )
    assert out_w > out_h
    assert deviation < 0.01
    assert px_per_mm == pytest.approx(10.0, abs=0.1)


# --- Provenance ------------------------------------------------------------


def test_a_bad_crop_no_longer_decides_where_the_card_is():
    """The headline behaviour of this change.

    Production warped straight to the customer's four dragged handles, so a
    crop placed inside the card removed the damage from the image before
    anything looked at it. The crop is now only a hint about where to search,
    and the detected boundary wins -- so the same card yields the same
    geometry whether the handles were placed well or sloppily.
    """
    image = build_fixture("pokemon_front")
    detected = preprocessing.rectify(image, *POKEMON_MM)

    box, _info = preprocessing.detect_boundary(image)
    ordered = preprocessing._order_points(box)
    # Drag every handle 25px into the card -- about 1mm at this scale, and
    # enough to have cropped a damaged corner clean away before.
    inward = np.array([[25, 25], [-25, 25], [-25, -25], [25, -25]], dtype="float32")
    sloppy = preprocessing.rectify(image, *POKEMON_MM, roi_quad=ordered + inward)

    assert sloppy.geometry["method"] == "ransac"
    assert sloppy.image.shape == detected.image.shape
    assert sloppy.px_per_mm == pytest.approx(detected.px_per_mm, abs=0.05)
    assert not sloppy.limitations


def test_falling_back_to_the_crop_is_never_silent():
    """When the region of interest contains no detectable boundary the crop is
    all there is -- which is legitimate, but every category measuring from it
    has to know."""
    # A featureless field: nothing to threshold, so detection cannot succeed.
    image = np.full((400, 300, 3), 200, dtype=np.uint8)
    quad = np.array([[20, 20], [280, 20], [280, 380], [20, 380]], dtype="float32")

    card = preprocessing.rectify(image, *POKEMON_MM, roi_quad=quad)

    assert card.geometry["method"] == "user_crop"
    assert assessment.GEOMETRY_UNVERIFIED in card.limitations


def test_a_region_that_is_not_card_shaped_is_reported():
    """Usually a crop placed short on one axis. Every millimetre figure
    derived from it is scaled wrong, and saying so beats reporting them to two
    decimal places."""
    image = np.full((400, 300, 3), 200, dtype=np.uint8)
    # Far squarer than 63:88.
    quad = np.array([[20, 20], [280, 20], [280, 240], [20, 240]], dtype="float32")

    card = preprocessing.rectify(image, *POKEMON_MM, roi_quad=quad)

    assert assessment.GEOMETRY_ASPECT_MISMATCH in card.limitations


def test_no_detectable_card_and_no_crop_is_still_an_error():
    """The one case that must stay loud. Nothing to measure and nothing to
    fall back on is an operator-visible failure, not a low score."""
    image = np.full((400, 300, 3), 200, dtype=np.uint8)
    with pytest.raises(ValueError):
        preprocessing.rectify(image, *POKEMON_MM)


# --- How a limitation reaches the customer ---------------------------------


def test_an_external_limitation_devalues_a_reading_without_changing_it():
    block = assessment.measured(8.0, 0.8, ("corners_whitening_only",)).as_dict()
    updated = assessment.with_limitations(block, (assessment.GEOMETRY_UNVERIFIED,), 8.0)

    assert updated["confidence"] < block["confidence"]
    assert updated["score_low"] < block["score_low"]
    assert "corners_whitening_only" in updated["limitations"]
    assert assessment.GEOMETRY_UNVERIFIED in updated["limitations"]


def test_external_limitations_compound():
    block = assessment.measured(8.0, 0.8, ()).as_dict()
    both = assessment.with_limitations(
        block,
        (assessment.GEOMETRY_UNVERIFIED, assessment.GEOMETRY_ASPECT_MISMATCH),
        8.0,
    )
    expected = (
        0.8
        * assessment.CONFIDENCE_UNVERIFIED_GEOMETRY_FACTOR
        * assessment.CONFIDENCE_ASPECT_MISMATCH_FACTOR
    )
    assert both["confidence"] == pytest.approx(expected, abs=0.01)


def test_an_unmeasurable_block_gains_the_reason_but_keeps_no_score():
    """There is no reading to devalue, but the reasons still belong in the
    record -- and an interval would imply a score sits somewhere inside it."""
    block = assessment.unmeasurable((assessment.CAPTURE_TOO_LOW_RESOLUTION,)).as_dict()
    updated = assessment.with_limitations(block, (assessment.GEOMETRY_UNVERIFIED,), None)

    assert updated["state"] == assessment.UNMEASURABLE
    assert updated["confidence"] == 0.0
    assert updated["score_low"] is None and updated["score_high"] is None
    assert assessment.GEOMETRY_UNVERIFIED in updated["limitations"]


def test_the_interval_is_recomputed_from_the_score_not_the_old_midpoint():
    """A score near either end of the scale has a clamped interval, so its
    midpoint is not the score. Rebuilding from the midpoint would drag a 9.8
    downward every time a limitation was attached."""
    block = assessment.measured(9.8, 0.9, ()).as_dict()
    updated = assessment.with_limitations(block, (assessment.GEOMETRY_UNVERIFIED,), 9.8)
    assert updated["score_high"] == 10.0
    assert updated["score_low"] < 9.8


# --- Budget ----------------------------------------------------------------


def test_rectification_stays_well_inside_the_per_card_budget():
    """The brief asks for sub-second per card. Measured here rather than
    assumed, because RANSAC plus a few thousand bilinear samples is the kind
    of thing that quietly becomes the slow step."""
    import time

    image = build_fixture("pokemon_front")
    preprocessing.rectify(image, *POKEMON_MM)  # warm any lazy init

    start = time.perf_counter()
    preprocessing.rectify(image, *POKEMON_MM)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.5, f"rectification took {elapsed * 1000:.0f}ms"


def test_recorded_apexes_are_in_source_coordinates():
    """The fit runs inside the region of interest, so its apexes come back in
    ROI coordinates. The warp adds the crop offset; the recorded copy has to
    as well, or the stored geometry describes a card somewhere else in the
    photograph whenever a crop was supplied.
    """
    image = build_fixture("pokemon_front")
    detected = preprocessing.rectify(image, *POKEMON_MM)

    box, _info = preprocessing.detect_boundary(image)
    ordered = preprocessing._order_points(box)
    hinted = preprocessing.rectify(image, *POKEMON_MM, roi_quad=ordered)

    assert hinted.geometry["method"] == "ransac"
    assert np.allclose(
        np.array(hinted.geometry["apexes"]),
        np.array(detected.geometry["apexes"]),
        atol=1.0,
    )


# --- Foil (phase 7) --------------------------------------------------------


def test_a_foil_card_lowers_every_category_s_confidence():
    """Phase 7, and it is a confidence statement rather than a correction.

    Nothing here knows how to undo what a holographic pattern does to a
    measurement -- it scatters centering's per-position frame fit, moves the
    Lab whitening readings at corners and edges, and is most of what the
    surface scratch filter spends its effort rejecting. What the pipeline can
    honestly do is say the reading is worth less.
    """
    block = assessment.measured(8.0, 0.8, ()).as_dict()
    foiled = assessment.with_limitations(block, (assessment.CARD_IS_FOIL,), 8.0)

    assert foiled["confidence"] == pytest.approx(
        0.8 * assessment.CONFIDENCE_FOIL_FACTOR, abs=0.01
    )
    assert assessment.CARD_IS_FOIL in foiled["limitations"]
    assert foiled["score_low"] < block["score_low"], "a wider range is the visible effect"


def test_foil_compounds_with_a_geometry_limitation():
    """Multiplicative like the rest: a foil card whose boundary also could not
    be verified is worse off than either alone."""
    block = assessment.measured(8.0, 0.8, ()).as_dict()
    both = assessment.with_limitations(
        block, (assessment.CARD_IS_FOIL, assessment.GEOMETRY_UNVERIFIED), 8.0
    )
    expected = (
        0.8
        * assessment.CONFIDENCE_FOIL_FACTOR
        * assessment.CONFIDENCE_UNVERIFIED_GEOMETRY_FACTOR
    )
    assert both["confidence"] == pytest.approx(expected, abs=0.01)
