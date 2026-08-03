"""Centering analysis: measure the printed-border width on all 4 sides of a
deskewed card image and express it as an L/R and T/B split, e.g. 58/42.

Approach: from each side, scan multiple lines inward from the physical cut
edge and locate the first strong luminance-gradient edge -- the boundary
between the printed border/frame and the card's cut edge. This is a
heuristic v1 (see plan) intended to be validated and tuned against real
sample scans, not a from-first-principles-exact measurement.
"""

import cv2
import numpy as np

from zgrader.analysis import assessment, scoring
from zgrader.models import AnalysisCategory

CATEGORY = AnalysisCategory.centering

# A real printed border sits at nearly the same depth on every sample line
# down a side, so the spread (std) of the per-line edge positions is tiny
# relative to the search window. Holo/full-art surfaces with no clean
# border scatter the argmax edge at random depths, giving a large spread.
# If any side's spread exceeds this fraction of its search depth, the
# centering result is marked lower_confidence.
_MAX_BORDER_SPREAD_FRACTION = 0.15

# A single scattered side is not a borderless card -- it is one noisy edge on a
# card that visibly has a frame, and declining on it withholds a measurement we
# can actually make. Measured across the fixture set: cards with a real printed
# border sit at 0.00-0.15 on every side with at most one marginal outlier,
# while genuinely unmeasurable ones (full-art foil, a bordered foil whose holo
# scatters the edge, the worst-case capture) scatter on *all four* at 0.22-0.35.
#
# So two independent ways to conclude there is no frame worth measuring:
_MIN_SCATTERED_SIDES = 2
# ...or one side so scattered that its reading is meaningless regardless of the
# others. The synthetic full-art fixture lands at 0.42 on the side crossing its
# artwork while the uniform sides read a consistent but meaningless depth --
# without this it would be scored on the strength of three sides that found
# nothing at all.
_SEVERE_BORDER_SPREAD_FRACTION = 0.35

CENTERING_LOW_CONFIDENCE_FLAG = {
    "lower_confidence": True,
    "reason": (
        "No clear printed border was found on one or more sides -- common on "
        "full-art / holo cards where the artwork bleeds to the edge and the "
        "whole surface is high-contrast. The centering split is a best-effort "
        "estimate here and may not be reliable."
    ),
}


def _first_strong_edge(strip: np.ndarray, skip_px: int = 3) -> float:
    """Index of the strongest gradient point in `strip`, skipping the first
    `skip_px` samples (the physical cut edge itself, not the printed
    border)."""
    if len(strip) <= skip_px + 1:
        return float(len(strip))
    usable = strip[skip_px:]
    kernel = np.ones(3) / 3
    smoothed = np.convolve(usable, kernel, mode="same")
    idx = int(np.argmax(smoothed))
    return float(idx + skip_px)


def _measure_border(
    edge_map: np.ndarray,
    side: str,
    search_fraction: float = 0.15,
    corner_margin_fraction: float = 0.1,
    num_samples: int = 20,
) -> tuple[float, float]:
    """Returns (median_border_width_px, spread_fraction) for one side, where
    spread_fraction is the std of the per-line edge positions divided by the
    search depth -- small means a consistent real border, large means the
    edge was scattered noise (see _MAX_BORDER_SPREAD_FRACTION)."""
    h, w = edge_map.shape
    widths: list[float] = []
    if side in ("left", "right"):
        search_depth = max(4, int(w * search_fraction))
        margin = max(1, int(h * corner_margin_fraction))
        samples = np.linspace(margin, max(margin, h - margin - 1), num_samples).astype(int)
        for r in samples:
            strip = (
                edge_map[r, 0:search_depth]
                if side == "left"
                else edge_map[r, w - search_depth : w][::-1]
            )
            widths.append(_first_strong_edge(strip))
    else:
        search_depth = max(4, int(h * search_fraction))
        margin = max(1, int(w * corner_margin_fraction))
        samples = np.linspace(margin, max(margin, w - margin - 1), num_samples).astype(int)
        for c in samples:
            strip = (
                edge_map[0:search_depth, c]
                if side == "top"
                else edge_map[h - search_depth : h, c][::-1]
            )
            widths.append(_first_strong_edge(strip))

    spread_fraction = float(np.std(widths) / max(1, search_depth))
    return float(np.median(widths)), spread_fraction


def score_from_worse_pct(worse_pct: float) -> float:
    """Thin delegate to the scoring layer.

    The mapping itself lives in analysis/scoring.py: measuring a border and
    deciding what a given asymmetry is worth are separate jobs, and only the
    first belongs here. Kept as a name because recompute.py and the tests call
    it, and re-deriving the same score in two places is how they drift apart.
    """
    return scoring.centering_score(worse_pct)


# Backwards-compatible alias for the pre-existing private name.
_score_from_worse_pct = score_from_worse_pct


def measure_centering(card_image: np.ndarray, px_per_mm: float) -> dict:
    gray = cv2.cvtColor(card_image, cv2.COLOR_BGR2GRAY)
    edge_map = np.abs(cv2.Laplacian(gray, cv2.CV_64F))

    left, left_spread = _measure_border(edge_map, "left")
    right, right_spread = _measure_border(edge_map, "right")
    top, top_spread = _measure_border(edge_map, "top")
    bottom, bottom_spread = _measure_border(edge_map, "bottom")

    lr_total = left + right
    tb_total = top + bottom
    lr_split = (
        [round(100 * left / lr_total, 1), round(100 * right / lr_total, 1)]
        if lr_total
        else [50.0, 50.0]
    )
    tb_split = (
        [round(100 * top / tb_total, 1), round(100 * bottom / tb_total, 1)]
        if tb_total
        else [50.0, 50.0]
    )
    worse_side_pct = max(max(lr_split), max(tb_split))

    reading = {
        "left_px": round(left, 1),
        "right_px": round(right, 1),
        "top_px": round(top, 1),
        "bottom_px": round(bottom, 1),
        "left_mm": round(left / px_per_mm, 2),
        "right_mm": round(right / px_per_mm, 2),
        "top_mm": round(top / px_per_mm, 2),
        "bottom_mm": round(bottom / px_per_mm, 2),
        "lr_ratio": lr_split,
        "tb_ratio": tb_split,
        "worse_side_pct": round(worse_side_pct, 1),
    }
    spreads = (left_spread, right_spread, top_spread, bottom_spread)
    scattered_sides = sum(1 for spread in spreads if spread > _MAX_BORDER_SPREAD_FRACTION)
    no_frame = (
        scattered_sides >= _MIN_SCATTERED_SIDES
        or max(spreads) > _SEVERE_BORDER_SPREAD_FRACTION
    )
    flags = dict(CENTERING_LOW_CONFIDENCE_FLAG) if no_frame else {}

    if no_frame:
        # No clean printed frame -- full-art, or artwork bleeding to the cut.
        # Every number above is then the argmax of noise, so this declines to
        # score rather than publishing a plausible-looking ratio.
        #
        # The reading is kept as `indicative_estimate`, deliberately NOT under
        # the keys a measurement lives at. rules_engine reads `worse_side_pct`
        # off the top level and skips the rule when it is absent; that skip is
        # the correct behaviour here, and hoisting the estimate into that key
        # would silently resurrect it as five company verdicts on a card
        # nothing could measure. The distinct key is what keeps an estimate
        # from being mistaken for a measurement anywhere downstream.
        measurements = {
            "indicative_estimate": reading,
            "assessment": assessment.unmeasurable((assessment.CENTERING_NO_FRAME,)).as_dict(),
        }
        return {
            "category": CATEGORY,
            "raw_score": None,
            "measurements": measurements,
            "flags": flags,
        }

    raw_score = round(score_from_worse_pct(worse_side_pct), 2)
    reading["assessment"] = assessment.measured(
        raw_score, assessment.CONFIDENCE_CENTERING_CLEAN_FRAME, ()
    ).as_dict()
    return {"category": CATEGORY, "raw_score": raw_score, "measurements": reading, "flags": flags}
