"""Locate the physical card in a flatbed scan and deskew/crop to its exact
boundary, so downstream analysis (centering/corners/edges/surface) operates
on a straightened, edge-to-edge image of just the card.
"""

from pathlib import Path

import cv2
import numpy as np


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


def _warp_to_rect(image: np.ndarray, box: np.ndarray) -> np.ndarray:
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


def locate_and_deskew(
    image: np.ndarray, min_area_fraction: float = 0.15, max_area_fraction: float = 0.95
) -> tuple[np.ndarray, dict]:
    """Find the card's outer boundary and return a deskewed, cropped image
    plus info about the detected contour, for annotation/debugging.

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
    rect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(rect)
    warped = _warp_to_rect(image, box)

    info = {
        "rect_center": rect[0],
        "rect_size": rect[1],
        "rect_angle": rect[2],
        "box_points": box.tolist(),
        "contour_area_px": float(cv2.contourArea(contour)),
    }
    return warped, info
