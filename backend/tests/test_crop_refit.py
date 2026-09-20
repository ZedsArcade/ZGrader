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
    """The card's real corners in a fixture, from the fixture's own geometry
    rather than from a detection that may be the thing under test.

    `make_card_scan` centres the card on an 8% margin, so the corners are a
    fixed fraction of the canvas.
    """
    image = build_fixture(name)
    h, w = image.shape[:2]
    margin_x, margin_y = w * 0.08, h * 0.08
    return np.array(
        [
            [margin_x, margin_y],
            [w - margin_x, margin_y],
            [w - margin_x, h - margin_y],
            [margin_x, h - margin_y],
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
