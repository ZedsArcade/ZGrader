"""Locate the physical card in a flatbed scan and deskew/crop to its exact
boundary, so downstream analysis (centering/corners/edges/surface) operates
on a straightened, edge-to-edge image of just the card.
"""

from pathlib import Path

import cv2
import numpy as np

# See detect_boundary's docstring for why this specific ratio distinguishes
# genuine keystone perspective from local corner damage/noise.
_QUAD_AREA_RATIO_THRESHOLD = 0.95


def load_image(path: str | Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read image: {path}")
    return image


def _largest_contour(binary: np.ndarray) -> np.ndarray | None:
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    return max(contours, key=cv2.contourArea)


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def warp_to_points(image: np.ndarray, box: np.ndarray) -> np.ndarray:
    """Perspective-warp `image` so the quadrilateral `box` (4 points, any
    order) becomes an axis-aligned rectangle. Point-agnostic: used both for
    an auto-detected box (detect_boundary) and for a user-confirmed crop
    (ScanImage.crop_points from the manual crop-adjust UI) -- the same
    homography corrects in-plane rotation and true keystone/perspective
    distortion together, so a separate "deskew"/"tilt" step is unnecessary
    once real corner points are known.
    """
    rect = _order_points(box)
    (tl, tr, br, bl) = rect
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = max(int(width_a), int(width_b))
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = max(int(height_a), int(height_b))
    if max_width < 2 or max_height < 2:
        raise ValueError("Detected card region is too small to be a real card")
    dst = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, matrix, (max_width, max_height))


def detect_boundary(
    image: np.ndarray, min_area_fraction: float = 0.15, max_area_fraction: float = 0.95
) -> tuple[np.ndarray, dict]:
    """Find the card's outer boundary and return its 4 corner points (any
    order) plus info about the detected contour, for annotation/debugging
    and as the starting suggestion for the manual crop-adjust UI.

    Tries both light-on-dark and dark-on-light thresholding since scanner
    backing (scanner lid open/closed, black backing sheet, etc.) varies. A
    contour spanning nearly the whole canvas is rejected -- that's the
    background winning under the wrong polarity, not the card (a real card
    scan always has some backing margin visible around it).

    Thresholds on the HSV Value channel (max of B/G/R) rather than
    luminance-weighted grayscale: a card's own border/interior regions can
    have very different luma (e.g. a blue-heavy border is "dark" under the
    standard luma formula, which heavily weights green) even though neither
    is remotely as dark as true black scanner backing on every channel. Value
    keeps the whole card in one bright cluster against a near-zero backing.

    Corner extraction tries cv2.approxPolyDP first, which can capture a
    contour's true 4-point quadrilateral (including real perspective/keystone
    distortion from a handheld photo, not just in-plane rotation); if the
    contour doesn't simplify to exactly 4 points (noisy edges, rounded
    corners), falls back to cv2.minAreaRect's best-fit rotated rectangle.
    """
    value_channel = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 2]
    blurred = cv2.GaussianBlur(value_channel, (5, 5), 0)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    image_area = image.shape[0] * image.shape[1]
    candidates: list[tuple[float, np.ndarray]] = []
    for candidate_binary in (binary, cv2.bitwise_not(binary)):
        contour = _largest_contour(candidate_binary)
        if contour is not None:
            area = cv2.contourArea(contour)
            if image_area * min_area_fraction <= area <= image_area * max_area_fraction:
                candidates.append((area, contour))

    if not candidates:
        raise ValueError(
            "Could not locate a card-sized region in the scan -- check scanner "
            "backing contrast and that the card is fully within the scan bed."
        )

    _, contour = max(candidates, key=lambda c: c[0])

    rect_center, rect_size, rect_angle = cv2.minAreaRect(contour)
    rect_area = rect_size[0] * rect_size[1]

    perimeter = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
    # Only trust the quad if it's a real trapezoid, not just minAreaRect's
    # own rectangle with one corner nudged by local damage/noise. Genuine
    # keystone perspective shrinks the quad's area well below its enclosing
    # minAreaRect box (a photographed rectangle viewed at an angle is
    # visibly smaller than the upright rectangle that bounds it); pure
    # in-plane rotation, whitening, or even a small chipped/rounded corner
    # all keep quad_area/rect_area close to 1.0 -- verified empirically
    # against synthetic fixtures (rotation-only and whitened-corner cases
    # land at ~0.997, a hard-clipped corner at ~0.986, a true keystoned
    # photo at ~0.86). Falling back to minAreaRect in the near-1.0 cases
    # preserves corner-damage detection (which relies on the deskewed crop
    # still including the ideal corner tip, not one already traced tight
    # around missing material).
    quad_area = cv2.contourArea(approx) if len(approx) == 4 else 0.0
    if len(approx) == 4 and rect_area > 0 and quad_area / rect_area < _QUAD_AREA_RATIO_THRESHOLD:
        box = approx.reshape(4, 2).astype("float32")
        method = "quad"
    else:
        box = cv2.boxPoints((rect_center, rect_size, rect_angle))
        method = "min_area_rect"

    info = {
        "method": method,
        "rect_center": rect_center,
        "rect_size": rect_size,
        "rect_angle": rect_angle,
        "box_points": box.tolist(),
        "contour_area_px": float(cv2.contourArea(contour)),
    }
    return box, info


def locate_and_deskew(
    image: np.ndarray, min_area_fraction: float = 0.15, max_area_fraction: float = 0.95
) -> tuple[np.ndarray, dict]:
    """Convenience wrapper: detect the boundary and warp to it in one call.
    Used by the migration backfill and the operator flatbed-drop path
    (zgrader.worker.watcher._register_new_scans), which auto-confirm a
    scan's crop_points at registration time rather than routing through the
    manual crop-adjust UI."""
    box, info = detect_boundary(image, min_area_fraction, max_area_fraction)
    return warp_to_points(image, box), info
