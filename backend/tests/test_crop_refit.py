"""A crop that disagrees with the fit, and what the pipeline does about it.

On a real photograph (`real_scans/shadowed_photo.jpg`) a shadow across the
lower half of the card puts that part of it on the background side of the
detector's threshold, so the outline stops about 5mm short of the cut. The
customer's crop said where the edge was and the pipeline threw it away: with a
crop traced on the true edges, the fitted apexes came back identical to the
pixel.

The photograph is not committable (the repo is public), so this fixture is the
committed form of the same failure.
"""

import json

import cv2
import numpy as np
import pytest

from tests.fixtures.generate_samples import build_fixture, card_size_mm
from zgrader.analysis import preprocessing

POKEMON_MM = card_size_mm("pokemon_front")


def true_card_quad(name: str) -> np.ndarray:
    """The card's real corners in a fixture, from the generator's own layout
    rather than from a detection that may be the thing under test.

    `make_card_scan` centres the card on a uniform margin of
    `int(min(card_w, card_h) * 0.08)` -- 8% of the *shorter card* dimension on
    every side, not 8% of each canvas axis. Computing it per axis puts the
    bottom edge ~2.8mm high on a portrait card, which is a ground truth that
    would quietly flatter every "within 0.5mm" assertion built on it.
    """
    from tests.fixtures.generate_samples import _mm_to_px

    width_mm, height_mm = card_size_mm(name)
    card_w, card_h = _mm_to_px(width_mm), _mm_to_px(height_mm)
    margin = int(min(card_w, card_h) * 0.08)
    return np.array(
        [
            [margin, margin],
            [margin + card_w, margin],
            [margin + card_w, margin + card_h],
            [margin, margin + card_h],
        ],
        dtype=np.float64,
    )


def test_the_shadowed_fixture_reproduces_the_photographs_failure():
    """Without help, the outline stops short of the card's bottom edge -- the
    same shape of failure the real photograph shows."""
    image = build_fixture("capture_shadowed_bottom")
    truth = true_card_quad("capture_shadowed_bottom")

    box, _info = preprocessing.detect_boundary(image, expected_aspect=63.0 / 88.0)

    detected_bottom = float(np.max(np.array(box, dtype=np.float64)[:, 1]))
    true_bottom = float(truth[2][1])
    px_per_mm = (truth[2][1] - truth[0][1]) / 88.0
    short_by_mm = (true_bottom - detected_bottom) / px_per_mm
    assert short_by_mm > 3.0, f"the shadow only hides {short_by_mm:.1f}mm of the card"
    assert short_by_mm < 12.0, "the fixture hides so much card that it is a different failure"


def test_the_shadowed_fixture_still_looks_like_a_card_to_the_fit():
    """The fit must succeed on the wrong outline -- a fixture that merely
    declines would exercise the fallback, not the silent mis-fit."""
    image = build_fixture("capture_shadowed_bottom")

    rectified = preprocessing.rectify(image, *POKEMON_MM)

    assert rectified.geometry["method"] == "ransac"
    assert "geometry_unverified" not in rectified.limitations


from zgrader.analysis import geometry


def _fitted(image, quad=None):
    """The pipeline's own fit for an image, plus the px/mm its raster is built
    at -- the two inputs the refit takes."""
    box, info = preprocessing.detect_boundary(image, expected_aspect=63.0 / 88.0)
    fit = geometry.fit_card_geometry(image, info["contour"], box)
    assert fit is not None, "this fixture is meant to fit, just in the wrong place"
    px_per_mm = preprocessing._canonical_size(fit.apexes, *POKEMON_MM)[2]
    return fit, px_per_mm


def _bottom_offset_mm(fit, truth, px_per_mm) -> float:
    """How far the fitted bottom line sits from the card's true bottom edge."""
    midpoint = (truth[2] + truth[3]) / 2
    return float(abs(fit.sides["bottom"].signed_distance(midpoint[None])[0])) / px_per_mm


def _crop_inset_from_sides(fit, inset_mm: float, px_per_mm: float) -> np.ndarray:
    """A crop built by moving each of `fit`'s own fitted sides inward by
    `inset_mm`, along that side's own inward normal, then re-intersecting for
    the corners -- the same shape of construction `fixture_drift.sloppy_crop`
    uses. Every side really does move by the stated amount this way; scaling
    the whole quad about its centre instead attenuates the displacement by the
    diagonal's cosine, which is the bug this replaces.

    `side.normal` already points into the card (`fit_card_geometry`), so
    adding to `offset` moves the line in the direction of `normal` -- inward.
    """
    inset_px = inset_mm * px_per_mm
    side_corners = {
        "top_left": ("top", "left"),
        "top_right": ("top", "right"),
        "bottom_right": ("bottom", "right"),
        "bottom_left": ("bottom", "left"),
    }
    lines = {name: (side.normal, side.offset + inset_px) for name, side in fit.sides.items()}
    points = []
    for a, b in side_corners.values():
        na, oa = lines[a]
        nb, ob = lines[b]
        points.append(np.linalg.solve(np.stack([na, nb]), np.array([oa, ob])))
    return geometry._order_quad(np.array(points, dtype=np.float64))


def _quad_size_mm(apexes: np.ndarray, px_per_mm: float) -> tuple[float, float]:
    width = (np.linalg.norm(apexes[1] - apexes[0]) + np.linalg.norm(apexes[2] - apexes[3])) / 2
    height = (np.linalg.norm(apexes[3] - apexes[0]) + np.linalg.norm(apexes[2] - apexes[1])) / 2
    return width / px_per_mm, height / px_per_mm


def test_a_side_the_crop_agrees_with_is_left_alone():
    """The common case: an untouched crop is the detected box, so every side is
    already where the crop says. Nothing may move -- this is the guard that a
    crop half a millimetre inside the card still cannot trim damage away."""
    image = build_fixture("pokemon_front")
    fit, px_per_mm = _fitted(image)
    crop = np.array(fit.apexes, dtype=np.float64)

    refit = geometry.refit_geometry_near_crop(image, fit, crop, px_per_mm)

    assert refit.moved == {}
    assert refit.unresolved == ()
    assert np.allclose(refit.geometry.apexes, fit.apexes)


def test_a_crop_just_inside_the_card_does_not_move_the_fit():
    """Half a millimetre in, on every side, is well under the trigger: the
    crop is a hint, and a hint that tight must not pull the measured edge
    inward. Built with `_crop_inset_from_sides` rather than scaling the quad
    about its centre, which insets a corner far less than a side and would
    prove the gate at the wrong magnitude."""
    image = build_fixture("pokemon_front")
    fit, px_per_mm = _fitted(image)
    crop = _crop_inset_from_sides(fit, 0.5, px_per_mm)

    refit = geometry.refit_geometry_near_crop(image, fit, crop, px_per_mm)

    assert refit.moved == {}
    assert refit.unresolved == ()
    assert np.allclose(refit.geometry.apexes, fit.apexes)


def test_a_crop_inset_a_real_4mm_on_every_side_does_not_pull_the_fit_inward():
    """The invariant, not just the gate: 4mm is five times over the trigger by
    distance alone, but the disagreement is inward on every side -- the crop
    claiming *less* card than the fit found -- and an inward disagreement is
    never grounds to re-search. Before the direction check, this dragged every
    side onto printed structure and shrank a 63x88mm card to roughly
    63x77mm."""
    image = build_fixture("pokemon_front")
    fit, px_per_mm = _fitted(image)
    crop = _crop_inset_from_sides(fit, 4.0, px_per_mm)

    refit = geometry.refit_geometry_near_crop(image, fit, crop, px_per_mm)

    assert refit.moved == {}
    assert refit.unresolved == ()
    assert np.allclose(refit.geometry.apexes, fit.apexes)

    width_mm, height_mm = _quad_size_mm(refit.geometry.apexes, px_per_mm)
    assert abs(width_mm - 63.0) < 0.5
    assert abs(height_mm - 88.0) < 0.5


def _textured_backing(name: str, sigma: float = 18.0) -> np.ndarray:
    """A fixture with seeded noise added to its backing only.

    Every committed fixture sits on a flat fill whose gradient is exactly zero,
    so `MIN_GRADIENT_RESPONSE` rejects the whole background and a search that
    strays into it merely finds nothing. A desk, a cutting mat or a sleeve does
    not behave like that: it clears that floor along the entire band, and the
    re-search's "outermost peak above the floor" then found the outer limit of
    its own search rather than a card edge. This is the shape of card the flat
    fills cannot express, built in the test rather than by changing a fixture
    every other baseline depends on.

    sigma=18 puts the backdrop's own gradient at a median of 5.0 and a 90th
    percentile of 16.5, sampled the way `_fit_side_near_line` samples it --
    comfortably over the 4.0 floor, which
    `test_the_textured_backing_really_does_clear_the_response_floor` pins so
    this cannot quietly become a test of a flat fill again.
    """
    image = build_fixture(name).copy()
    card = np.zeros(image.shape[:2], dtype=np.uint8)
    cv2.fillPoly(card, [true_card_quad(name).round().astype(np.int32)], 255)
    rng = np.random.default_rng(20260920)
    noisy = image.astype(np.float64) + np.where(
        card[:, :, None] == 0, rng.normal(0.0, sigma, image.shape), 0.0
    )
    return np.clip(noisy, 0, 255).astype(np.uint8)


def _backing_gradient(image: np.ndarray, name: str) -> np.ndarray:
    """The gradient the re-search would see walking down the backing, above the
    card's top edge, in the same channel and at the same step it uses."""
    truth = true_card_quad(name)
    value = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 2]
    ys = np.arange(5.0, float(truth[0][1]) - 20.0, geometry.SUBPIXEL_STEP_PX)
    xs = np.full_like(ys, float(truth[0][0]) + 200.0)
    return np.abs(np.gradient(geometry._sample_bilinear(value, xs, ys)))


def _side_move_mm(before, after, px_per_mm: float) -> dict[str, float]:
    """Per side, how far outward the line moved, in millimetres, measured at
    the side's own midpoint. `normal` points into the card, so a line that
    moved outward has a lower `signed_distance` at a fixed point."""
    moves = {}
    for corners, name in (
        ((0, 1), "top"), ((1, 2), "right"), ((3, 2), "bottom"), ((0, 3), "left")
    ):
        i, j = corners
        midpoint = ((before.apexes[i] + before.apexes[j]) / 2)[None]
        was = float(before.sides[name].signed_distance(midpoint)[0])
        now = float(after.sides[name].signed_distance(midpoint)[0])
        moves[name] = (was - now) / px_per_mm
    return moves


def test_the_textured_backing_really_does_clear_the_response_floor():
    """Without this the texture tests below would pass for the wrong reason --
    a flat fill declines every peak, so a rule that never fires looks like a
    rule that fires correctly."""
    gradient = _backing_gradient(_textured_backing("pokemon_front"), "pokemon_front")
    assert float(np.median(gradient)) >= geometry.MIN_GRADIENT_RESPONSE, (
        f"the backing's median gradient is {np.median(gradient):.2f}, under the "
        f"{geometry.MIN_GRADIENT_RESPONSE} floor -- this is a flat fill again"
    )
    plain = _backing_gradient(build_fixture("pokemon_front"), "pokemon_front")
    assert float(np.max(plain)) < geometry.MIN_GRADIENT_RESPONSE, (
        "the committed fixture's backing is no longer flat, so this test no "
        "longer says anything about the difference"
    )


@pytest.mark.parametrize("proud_mm", [2.5, 3.0])
def test_a_proud_crop_on_a_textured_backing_cannot_grow_the_card(proud_mm):
    """The escalated finding, in committed form.

    A crop a couple of millimetres proud of the card on every side is ordinary
    slop from a crop traced by finger. On a textured backing the re-search used
    to answer it by taking the outermost gradient peak above the absolute
    floor, which on a desk is simply the outermost *tap*: measured on real
    photographs, all four sides moved out together by roughly
    `band - proud`, growing the card by 17% in px/mm with `limitations` empty,
    and uniform outward growth preserves aspect so `MAX_ASPECT_DEVIATION` could
    not see it either. Here the same rule grows a 63x88mm card to 72.9x97.9mm.

    A peak now has to stand at `CROP_REFIT_PEAK_FRACTION` of the strongest step
    along its own normal, which backdrop texture does not.
    """
    image = _textured_backing("pokemon_front")
    fit, px_per_mm = _fitted(image)
    crop = _crop_inset_from_sides(fit, -proud_mm, px_per_mm)

    refit = geometry.refit_geometry_near_crop(image, fit, crop, px_per_mm)

    assert refit.unresolved == (), "a side with a findable edge must not decline"
    width_mm, height_mm = _quad_size_mm(refit.geometry.apexes, px_per_mm)
    assert abs(width_mm - 63.0) < 0.5, f"card grew to {width_mm:.2f}mm wide"
    assert abs(height_mm - 88.0) < 0.5, f"card grew to {height_mm:.2f}mm tall"
    moves = _side_move_mm(fit, refit.geometry, px_per_mm)
    assert max(moves.values()) < 0.5, f"a side moved outward: {moves}"


def test_the_search_band_stays_inside_the_region_of_interest():
    """`rectify` hands the re-search only the pixels inside the expanded crop,
    so a band wider than that expansion searches off the end of its own image
    and reads clipped edge pixels as a profile. The margin is a fraction of the
    crop, so the tightest real case is the smallest card dimension."""
    smallest_card_mm = 63.0
    margin_mm = smallest_card_mm * preprocessing.ROI_MARGIN_FRACTION
    assert geometry.CROP_REFIT_BAND_MM < margin_mm, (
        f"a {geometry.CROP_REFIT_BAND_MM}mm band does not fit inside the "
        f"{margin_mm:.1f}mm the region of interest is expanded by"
    )


def test_the_two_ways_of_finding_nothing_are_told_apart():
    """`_fit_side_near_line` reports *why* it came back empty, and the two
    reasons are different facts about the image -- flat background against a
    busy one. Collapsing them is what made an ordinary sloppy crop throw away
    a perfectly good fit."""
    # `value` is the single-channel V plane `refit_geometry_near_crop` builds.
    flat = np.full((400, 400), 40, dtype=np.uint8)
    start, end = np.array([50.0, 200.0]), np.array([350.0, 200.0])
    centre = np.array([200.0, 320.0])

    _fit, reason = geometry._fit_side_near_line(flat, start, end, centre, 40.0)
    assert reason == geometry._NO_EDGE

    rng = np.random.default_rng(7)
    noisy = rng.integers(0, 255, (400, 400), dtype=np.uint8)
    _fit, reason = geometry._fit_side_near_line(noisy, start, end, centre, 40.0)
    assert reason == geometry._NO_CONSENSUS


def test_a_side_the_search_cannot_place_keeps_its_fitted_line(monkeypatch):
    """Peaks near the crop line that do not lie on a line say nothing about
    the fit: the re-search has produced nothing better than the edge already
    measured from the image, so that edge stands and the card is not thrown
    away. Declining here instead cost 22 of 37 real photographs on a crop
    2.5-3.0mm proud -- ordinary slop -- which is the whole reason the reason
    codes exist."""
    image = build_fixture("capture_shadowed_bottom")
    truth = true_card_quad("capture_shadowed_bottom")
    fit, px_per_mm = _fitted(image)
    monkeypatch.setattr(
        geometry, "_fit_side_near_line", lambda *a, **k: (None, geometry._NO_CONSENSUS)
    )

    refit = geometry.refit_geometry_near_crop(image, fit, truth, px_per_mm)

    assert refit.unresolved == ()
    assert refit.moved == {}
    assert np.allclose(refit.geometry.apexes, fit.apexes)


def test_a_crop_on_the_true_edge_recovers_a_side_the_shadow_hid():
    """The whole point. The fit stops inside the card; the crop says where the
    edge is; the re-search finds it there rather than taking the crop's word."""
    image = build_fixture("capture_shadowed_bottom")
    truth = true_card_quad("capture_shadowed_bottom")
    fit, px_per_mm = _fitted(image)
    assert _bottom_offset_mm(fit, truth, px_per_mm) > 3.0, "fixture no longer hides the edge"

    refit = geometry.refit_geometry_near_crop(image, fit, truth, px_per_mm)

    assert "bottom" in refit.moved
    assert refit.unresolved == ()
    assert _bottom_offset_mm(refit.geometry, truth, px_per_mm) < 0.5
    assert refit.moved["bottom"]["disagreement_mm"] > 3.0
    assert refit.moved["bottom"]["moved_mm"] > 3.0


def test_sides_the_crop_agrees_with_stay_put_when_another_is_refit():
    image = build_fixture("capture_shadowed_bottom")
    truth = true_card_quad("capture_shadowed_bottom")
    fit, px_per_mm = _fitted(image)

    refit = geometry.refit_geometry_near_crop(image, fit, truth, px_per_mm)

    for name in ("left", "right", "top"):
        assert name not in refit.moved
        assert refit.geometry.sides[name].offset == fit.sides[name].offset


def test_a_side_with_no_edge_near_the_crop_is_unresolved():
    """A crop line over featureless background has nothing to find. Saying so
    is the honest answer; inventing a line from the crop is not."""
    image = build_fixture("pokemon_front")
    fit, px_per_mm = _fitted(image)
    crop = np.array(fit.apexes, dtype=np.float64)
    # Push the bottom line far out into the flat backing, past any edge.
    crop[2][1] += 6.0 * px_per_mm
    crop[3][1] += 6.0 * px_per_mm

    refit = geometry.refit_geometry_near_crop(image, fit, crop, px_per_mm)

    assert refit.unresolved == ("bottom",)
    assert "bottom" not in refit.moved


def test_the_refit_is_deterministic():
    image = build_fixture("capture_shadowed_bottom")
    truth = true_card_quad("capture_shadowed_bottom")
    fit, px_per_mm = _fitted(image)

    first = geometry.refit_geometry_near_crop(image, fit, truth, px_per_mm)
    second = geometry.refit_geometry_near_crop(image, fit, truth, px_per_mm)

    assert np.array_equal(first.geometry.apexes, second.geometry.apexes)


from zgrader.analysis import assessment


def test_rectify_recovers_the_hidden_edge_when_the_crop_says_where_it_is():
    image = build_fixture("capture_shadowed_bottom")
    truth = true_card_quad("capture_shadowed_bottom")

    uncropped = preprocessing.rectify(image, *POKEMON_MM)
    guided = preprocessing.rectify(image, *POKEMON_MM, roi_quad=truth)

    px_per_mm = guided.px_per_mm
    bottom_before = float(np.mean(np.array(uncropped.geometry["apexes"])[2:4, 1]))
    bottom_after = float(np.mean(np.array(guided.geometry["apexes"])[2:4, 1]))
    true_bottom = float(truth[2][1])

    assert (true_bottom - bottom_before) / px_per_mm > 3.0, "fixture no longer hides the edge"
    assert abs(true_bottom - bottom_after) / px_per_mm < 0.5
    assert guided.geometry["method"] == "ransac"
    assert "bottom" in guided.geometry["refit_sides"]
    assert assessment.GEOMETRY_UNVERIFIED not in guided.limitations
    assert assessment.GEOMETRY_CROP_DISAGREEMENT not in guided.limitations

    # `refit.moved`'s values are numpy.float64; this block is persisted as
    # JSONB, and the stdlib encoder rejects a NumPy scalar outright. A test
    # that only reads the dict in memory would not catch that -- exercise the
    # actual serialisation the persistence path performs.
    json.dumps(guided.geometry)


def test_an_untouched_crop_changes_nothing_at_all():
    """The path every production submission takes today: the crop is the
    detected box. The refit must be invisible there, byte for byte."""
    image = build_fixture("pokemon_front")
    uncropped = preprocessing.rectify(image, *POKEMON_MM)
    crop = np.array(uncropped.geometry["apexes"], dtype=np.float64)

    cropped = preprocessing.rectify(image, *POKEMON_MM, roi_quad=crop)

    assert cropped.geometry["apexes"] == uncropped.geometry["apexes"]
    assert "refit_sides" not in cropped.geometry
    assert list(cropped.limitations) == list(uncropped.limitations)


def test_a_crop_over_background_declines_rather_than_taking_the_crop_s_word():
    image = build_fixture("pokemon_front")
    uncropped = preprocessing.rectify(image, *POKEMON_MM)
    crop = np.array(uncropped.geometry["apexes"], dtype=np.float64)
    crop[2][1] += 6.0 * uncropped.px_per_mm
    crop[3][1] += 6.0 * uncropped.px_per_mm

    guided = preprocessing.rectify(image, *POKEMON_MM, roi_quad=crop)

    assert guided.geometry["method"] == "user_crop"
    assert assessment.GEOMETRY_UNVERIFIED in guided.limitations
    assert assessment.GEOMETRY_CROP_DISAGREEMENT in guided.limitations
    assert guided.geometry["crop_disagreement_sides"] == ["bottom"]
    json.dumps(guided.geometry)


def test_the_refit_survives_a_crop_away_from_the_image_origin():
    """The fit runs in the region of interest's coordinates and the crop
    arrives in the image's, so the offset has to be taken off before they are
    compared. That offset has been applied with the wrong sign here before, and
    no fixture can show it without padding: an unpadded fixture's ROI origin
    clips to (0, 0), where both signs agree.
    """
    padded = cv2.copyMakeBorder(
        build_fixture("capture_shadowed_bottom"), 400, 0, 300, 0, cv2.BORDER_CONSTANT, value=(0, 0, 0)
    )
    truth = true_card_quad("capture_shadowed_bottom") + np.array([300.0, 400.0])

    guided = preprocessing.rectify(padded, *POKEMON_MM, roi_quad=truth)

    bottom = float(np.mean(np.array(guided.geometry["apexes"])[2:4, 1]))
    assert abs(float(truth[2][1]) - bottom) / guided.px_per_mm < 0.5
    assert "bottom" in guided.geometry["refit_sides"]

    unpadded = preprocessing.rectify(
        build_fixture("capture_shadowed_bottom"), *POKEMON_MM, roi_quad=true_card_quad("capture_shadowed_bottom")
    )
    missing = float(np.mean(guided.mask == 0))
    unpadded_missing = float(np.mean(unpadded.mask == 0))
    # The recovered strip is outside the material mask by design (the mask is
    # still the shadow-truncated contour -- spec 3.4), so what matters here is
    # that padding the canvas changes nothing: a crop offset applied with the
    # wrong sign displaced the mask by twice the region-of-interest origin and
    # left 7-100% of the raster missing.
    assert missing == pytest.approx(unpadded_missing, abs=0.02)
    assert missing < 0.15, f"{missing:.1%} of the raster reads as missing card"
