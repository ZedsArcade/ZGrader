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

import cv2
import numpy as np

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
    """Half a millimetre in is well under the trigger: the crop is a hint, and
    a hint that tight must not pull the measured edge inward."""
    image = build_fixture("pokemon_front")
    fit, px_per_mm = _fitted(image)
    centre = fit.apexes.mean(axis=0)
    crop = centre + (fit.apexes - centre) * (1.0 - (0.5 * px_per_mm) / np.linalg.norm(fit.apexes[0] - centre))

    refit = geometry.refit_geometry_near_crop(image, fit, crop, px_per_mm)

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
