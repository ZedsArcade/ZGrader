"""Corner analysis: for each of the 4 corners, detect whitening -- the
saturation drop-off from the tip inward, since worn corners fray to the white
cardstock underneath.

WHY ROUNDING IS STILL NOT SCORED
--------------------------------
This module used to derive a second sub-score, `rounding_score`, from how much
scanner backing (near-black) bled into the pixel at crop[0, 0]. That reasoning
only holds when crop[0, 0] is the card's *ideal* sharp-corner apex, so that a
rounded or chipped corner leaves backing visible there.

It was removed because that premise was false in production: the pipeline
warped to ScanImage.crop_points, and for every self-serve upload those points
were four handles the customer dragged. The measurement was a function of
where someone dropped a handle, not of the card -- crop a hair inside and
every corner read 10.0 regardless of damage; a hair outside and every corner
read 0.0 -- and it was half of this category's score.

**The premise now holds again.** preprocessing.rectify warps to apexes that
geometry.py obtains by intersecting lines fitted to the four sides, with a
margin excluded at each end, so the apex is where the corner *would* be if it
were perfect and a chipped corner genuinely does leave backing at crop[0, 0].
The customer's crop is only a region-of-interest hint.

It stays unscored anyway, and deliberately. `10 - 12 * backing_fraction` is an
uncalibrated guess at what a given amount of missing material is worth, and
the whole point of restoring the apexes is to measure that loss properly --
corner area deficit in mm^2 against the known apex, which is the next phase.
Re-enabling the old heuristic in the meantime would put a number back in front
of customers on the strength of a constant nobody derived. So this category
still measures whitening only and still says so in its flags;
`backing_bleed_fraction` remains a diagnostic, now a trustworthy one.

Heuristic v1: thresholds are starting points to be tuned against real sample
scans, not derived from an official published methodology.
"""

import cv2
import numpy as np

from zgrader.analysis import assessment, capture, scoring
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
    whitening_score = scoring.corner_whitening_score(whitening_delta)

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


def measure_corners(
    card_image: np.ndarray,
    corner_fraction: float = 0.12,
    px_per_mm: float | None = None,
) -> dict:
    """px_per_mm is optional so callers that only want the per-corner
    diagnostics (the annotator, the older tests) need not supply it. Omitting
    it means no resolution claim is made either way -- see
    capture.resolution_limitation.
    """
    crops = corner_crops(card_image, corner_fraction)
    per_corner = {name: _analyze_corner(crop) for name, crop in crops.items()}

    combined_scores = [c["combined_score"] for c in per_corner.values()]
    raw_score = round(float(np.mean(combined_scores)), 2)
    worst_corner = min(per_corner, key=lambda k: per_corner[k]["combined_score"])

    # A pale border has almost no saturation to lose, so the whitening signal
    # this category depends on is weak or absent -- the white-bordered blind
    # spot, now measured per card rather than asserted in a footnote.
    mean_reference_saturation = float(
        np.mean([c["reference_saturation"] for c in per_corner.values()])
    )
    pale = mean_reference_saturation < assessment.PALE_BORDER_SATURATION

    capture_code, too_low_resolution = capture.resolution_limitation(px_per_mm)

    measurements = {
        "per_corner": per_corner,
        "worst_corner": worst_corner,
        "corner_fraction": corner_fraction,
        "mean_reference_saturation": round(mean_reference_saturation, 1),
    }

    if too_low_resolution:
        # Corner wear is a sub-millimetre feature; below the floor it does not
        # exist in the image to be found. The per-corner numbers above stay as
        # diagnostics because they are what a later retune gets compared
        # against, but the category declines to score and nothing downstream
        # treats them as findings -- regions.build_regions returns nothing for
        # an unscored category and the annotator draws no boxes.
        #
        # The whitening-only and pale-border caveats are dropped here on
        # purpose: they explain the shape of a reading, and there is no
        # reading. Listing them beside "nothing was measurable" reads as
        # hedging rather than as the one thing that actually stopped us.
        measurements["assessment"] = assessment.unmeasurable((capture_code,)).as_dict()
        return {
            "category": CATEGORY,
            "raw_score": None,
            "measurements": measurements,
            "flags": {
                "lower_confidence": True,
                "reason": (
                    "The card occupies too few pixels in this photo for corner "
                    "wear to be visible at all, so corners were not scored. A "
                    "closer or higher-resolution photo would let this be "
                    "measured."
                ),
            },
        }

    limitations = [assessment.CORNERS_WHITENING_ONLY]
    if pale:
        limitations.append(assessment.CORNERS_PALE_BORDER)
    confidence = (
        assessment.CONFIDENCE_CORNERS_PALE_BORDER if pale else assessment.CONFIDENCE_CORNERS
    )
    if capture_code is not None:
        # Enough resolution to see gross damage, not enough to grade it. The
        # score stands; what it is worth does not.
        limitations.append(capture_code)
        confidence *= assessment.CONFIDENCE_MODEST_RESOLUTION_FACTOR

    measurements["assessment"] = assessment.measured(
        raw_score, confidence, tuple(limitations)
    ).as_dict()
    return {
        "category": CATEGORY,
        "raw_score": raw_score,
        "measurements": measurements,
        "flags": dict(CORNERS_LIMITATION_FLAG),
    }
