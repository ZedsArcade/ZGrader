"""Corner analysis: for each of the 4 corners, detect whitening -- the
saturation drop-off from the tip inward, since worn corners fray to the white
cardstock underneath.

WHY ROUNDING IS NO LONGER SCORED
--------------------------------
This module used to derive a second sub-score, `rounding_score`, from how much
scanner backing (near-black) bled into the pixel at crop[0, 0]. That reasoning
only holds when crop[0, 0] is the card's *ideal* sharp-corner apex, which is
true when preprocessing.locate_and_deskew produced the crop -- it warps the
card's tightest bounding rectangle onto the output image's corners, so a
rounded or chipped corner leaves backing visible at the apex.

But that is not the production path. pipeline._load_deskewed_card warps to
ScanImage.crop_points, and for every self-serve upload those points come from
the customer dragging four handles in the crop-adjust UI (see
api/routers/submissions.py's upload_scan and the confirm-crop flow). So the
measurement became a function of where the customer dropped a handle, not of
the card: crop a hair inside the card and every corner reads 10.0 regardless
of damage; crop a hair outside and every corner reads 0.0. It was half of each
corner's score and therefore half of this category's score.

It is kept below as an unscored diagnostic (`backing_bleed_fraction`,
`rounding_score`) because it is still meaningful on the operator flatbed path,
where the watcher auto-confirms crop_points from detect_boundary -- but
nothing on the row records which path produced the crop, so it cannot be
trusted for scoring. Real material-loss measurement (corner area deficit in
mm^2, measured against apexes recovered by RANSAC line fitting) replaces it
properly in a later phase; until then this category deliberately measures
whitening only and says so in its flags.

Heuristic v1: thresholds are starting points to be tuned against real sample
scans, not derived from an official published methodology.
"""

import cv2
import numpy as np

from zgrader.models import AnalysisCategory

CATEGORY = AnalysisCategory.corners

# HSV Value (0-255) below which a pixel is considered scanner backing rather
# than card material -- consistent with the assumption in preprocessing.py
# that backing is near-black. Feeds the unscored backing_bleed_fraction
# diagnostic only (see the module docstring).
_BACKING_VALUE_THRESHOLD = 50.0

CORNERS_LIMITATION_FLAG = {
    "lower_confidence": True,
    "reason": (
        "Corner assessment covers whitening only. Material loss (rounding, "
        "chipping) is not measured in this version, so a corner that is worn "
        "down but not discoloured will not be penalised here. Whitening is "
        "detected as a loss of colour saturation toward the tip, which also "
        "makes it unreliable on white or very pale borders, where there is "
        "little saturation to lose in the first place."
    ),
}


def _analyze_corner(crop: np.ndarray) -> dict:
    """Analyze a corner crop that has been normalized so the card's actual
    tip is at crop[0, 0] (top-left)."""
    size = crop.shape[0]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    tip_radius = max(3, int(size * 0.25))
    tip_sat = float(np.mean(hsv[0:tip_radius, 0:tip_radius, 1]))
    ref_region = hsv[int(size * 0.6) : size, 0 : max(2, int(size * 0.15)), 1]
    ref_sat = float(np.mean(ref_region)) if ref_region.size else tip_sat
    whitening_delta = max(0.0, ref_sat - tip_sat)
    whitening_score = float(np.clip(10.0 - whitening_delta / 8.0, 0.0, 10.0))

    # Unscored diagnostic -- see the module docstring for why this no longer
    # contributes to combined_score. Retained because it is still informative
    # on the operator flatbed path and because the replacement measurement
    # will want something to compare against.
    very_tip_radius = max(2, int(size * 0.08))
    very_tip_value = hsv[0:very_tip_radius, 0:very_tip_radius, 2]
    backing_fraction = float(np.mean(very_tip_value < _BACKING_VALUE_THRESHOLD))
    rounding_score = float(np.clip(10.0 - backing_fraction * 12.0, 0.0, 10.0))

    combined_score = whitening_score
    return {
        "whitening_score": round(whitening_score, 2),
        "combined_score": round(combined_score, 2),
        "tip_saturation": round(tip_sat, 1),
        "reference_saturation": round(ref_sat, 1),
        # Diagnostics below this point are not scored.
        "rounding_score": round(rounding_score, 2),
        "rounding_scored": False,
        "backing_bleed_fraction": round(backing_fraction, 3),
    }


def corner_crops(card_image: np.ndarray, corner_fraction: float = 0.12) -> dict[str, np.ndarray]:
    """Corner crops normalized so the card's tip is always at [0, 0]."""
    h, w = card_image.shape[:2]
    size = max(8, int(min(h, w) * corner_fraction))
    return {
        "top_left": card_image[0:size, 0:size],
        "top_right": np.fliplr(card_image[0:size, w - size : w]),
        "bottom_left": np.flipud(card_image[h - size : h, 0:size]),
        "bottom_right": np.flipud(np.fliplr(card_image[h - size : h, w - size : w])),
    }


def measure_corners(card_image: np.ndarray, corner_fraction: float = 0.12) -> dict:
    crops = corner_crops(card_image, corner_fraction)
    per_corner = {name: _analyze_corner(crop) for name, crop in crops.items()}

    combined_scores = [c["combined_score"] for c in per_corner.values()]
    raw_score = round(float(np.mean(combined_scores)), 2)
    worst_corner = min(per_corner, key=lambda k: per_corner[k]["combined_score"])

    measurements = {"per_corner": per_corner, "worst_corner": worst_corner, "corner_fraction": corner_fraction}
    return {
        "category": CATEGORY,
        "raw_score": raw_score,
        "measurements": measurements,
        "flags": dict(CORNERS_LIMITATION_FLAG),
    }
