import cv2
import numpy as np

from tests.fixtures.generate_samples import make_card_scan
from zgrader.analysis import preprocessing


def _perspective_warp(image: np.ndarray, shift_frac: float = 0.15) -> np.ndarray:
    """Applies a real keystone/perspective distortion (unlike
    make_card_scan's rotation_deg, which is a pure in-plane affine
    rotation) -- simulates a handheld photo shot at an angle, where the top
    edge of the card appears narrower than the bottom."""
    h, w = image.shape[:2]
    src = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype="float32")
    shift = int(w * shift_frac)
    dst = np.array([[shift, 0], [w - shift, 0], [w, h], [0, h]], dtype="float32")
    matrix = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(image, matrix, (w, h))


def test_detect_boundary_finds_quad_for_keystoned_photo():
    scan = make_card_scan(63.0, 88.0)
    skewed = _perspective_warp(scan)

    box, info = preprocessing.detect_boundary(skewed)

    assert box.shape == (4, 2)
    assert info["method"] == "quad"


def test_detect_boundary_falls_back_to_min_area_rect_for_non_quad_contour():
    # A circle's contour can't simplify to exactly 4 points under
    # approxPolyDP -- detect_boundary must fall back to minAreaRect rather
    # than erroring or misdetecting a false quad.
    canvas = np.zeros((400, 400, 3), dtype=np.uint8)
    cv2.circle(canvas, (200, 200), 150, (200, 200, 200), thickness=-1)

    box, info = preprocessing.detect_boundary(canvas)

    assert box.shape == (4, 2)
    assert info["method"] == "min_area_rect"


def test_warp_to_points_corrects_keystone_distortion():
    scan = make_card_scan(63.0, 88.0)
    skewed = _perspective_warp(scan)
    box, _info = preprocessing.detect_boundary(skewed)

    warped = preprocessing.warp_to_points(skewed, box)

    original_aspect = scan.shape[1] / scan.shape[0]
    warped_aspect = warped.shape[1] / warped.shape[0]
    # A minAreaRect-only fix (the old behavior) could not correct real
    # keystone distortion at all -- confirming the recovered aspect ratio
    # lands close to the un-skewed original is the actual regression check.
    assert abs(original_aspect - warped_aspect) < 0.15


def test_locate_and_deskew_still_works_as_a_thin_wrapper():
    scan = make_card_scan(63.0, 88.0, rotation_deg=2.0)

    warped, info = preprocessing.locate_and_deskew(scan)

    assert warped.shape[0] > 0 and warped.shape[1] > 0
    assert "method" in info
