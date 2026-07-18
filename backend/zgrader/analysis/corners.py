"""Corner analysis: for each of the 4 corners, detect whitening (saturation
drop-off from the tip inward, since worn corners fray to the white cardstock
underneath) and rounding/clipping.

Rounding detection relies on how preprocessing.locate_and_deskew works: it
warps the scan so the card's tightest bounding rectangle maps exactly onto
the output image's corners. If a corner is physically rounded or chipped,
the *ideal* sharp-corner position (mapped to crop[0, 0]) falls just outside
the actual card material -- so that pixel shows scanner backing (near-black)
rather than card color. A dark patch right at the tip is therefore itself
the rounding signal, not something to be inferred from edge-detector
response (an earlier version used Harris corner response here, but its
per-crop-max normalization was dominated by unrelated edges elsewhere in the
crop -- e.g. the border/interior color transition -- and scored every
corner as heavily rounded regardless of actual condition).

Heuristic v1 (see plan): thresholds are starting points to be tuned against
real sample scans, not derived from an official published methodology.
"""

import cv2
import numpy as np

from zgrader.models import AnalysisCategory

CATEGORY = AnalysisCategory.corners

# HSV Value (0-255) below which a pixel is considered scanner backing rather
# than card material -- consistent with the assumption in preprocessing.py
# that backing is near-black.
_BACKING_VALUE_THRESHOLD = 50.0


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

    very_tip_radius = max(2, int(size * 0.08))
    very_tip_value = hsv[0:very_tip_radius, 0:very_tip_radius, 2]
    backing_fraction = float(np.mean(very_tip_value < _BACKING_VALUE_THRESHOLD))
    rounding_score = float(np.clip(10.0 - backing_fraction * 12.0, 0.0, 10.0))

    combined_score = float(np.mean([whitening_score, rounding_score]))
    return {
        "whitening_score": round(whitening_score, 2),
        "rounding_score": round(rounding_score, 2),
        "combined_score": round(combined_score, 2),
        "tip_saturation": round(tip_sat, 1),
        "reference_saturation": round(ref_sat, 1),
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
    return {"category": CATEGORY, "raw_score": raw_score, "measurements": measurements, "flags": {}}
