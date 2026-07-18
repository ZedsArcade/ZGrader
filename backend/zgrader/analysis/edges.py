"""Edge analysis: sample thin strips along all 4 edges (excluding the
corners, which corners.py handles separately) and flag whitening -- a
saturation drop relative to a "clean" reference strip sampled immediately
adjacent to that same edge (further inward, still within the border/frame),
since a whitened/chipped edge fades toward bare cardstock right at the cut.

The reference is deliberately LOCAL to each edge rather than a single global
sample from the card's interior artwork: many cards' border color differs
noticeably in saturation from their interior art, which would make a global
reference misfire on every edge regardless of actual wear.

Heuristic v1 (see plan): thresholds are starting points to be tuned against
real sample scans.
"""

import cv2
import numpy as np

from zgrader.models import AnalysisCategory

CATEGORY = AnalysisCategory.edges

_WHITENING_SATURATION_DEFICIT = 40.0


def _longest_true_run(mask: np.ndarray) -> int:
    longest = current = 0
    for value in mask:
        if value:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _analyze_strip(outer_saturation: np.ndarray, inner_saturation: np.ndarray, along_axis: int) -> dict:
    if outer_saturation.size == 0:
        return {"score": 10.0, "whitened_fraction": 0.0, "longest_run_fraction": 0.0, "reference_saturation": 0.0}

    ref_sat = float(np.mean(inner_saturation)) if inner_saturation.size else float(np.mean(outer_saturation))
    deficit = np.clip(ref_sat - outer_saturation.astype(np.float32), 0, None)
    whitened_mask = deficit > _WHITENING_SATURATION_DEFICIT
    whitened_fraction = float(np.mean(whitened_mask))

    collapsed_along_edge = np.any(whitened_mask, axis=along_axis)
    longest_run = _longest_true_run(collapsed_along_edge)
    run_fraction = longest_run / max(1, len(collapsed_along_edge))

    score = float(np.clip(10.0 - whitened_fraction * 15.0 - run_fraction * 10.0, 0.0, 10.0))
    return {
        "score": round(score, 2),
        "whitened_fraction": round(whitened_fraction, 3),
        "longest_run_fraction": round(run_fraction, 3),
        "reference_saturation": round(ref_sat, 1),
    }


def measure_edges(
    card_image: np.ndarray,
    corner_exclusion_fraction: float = 0.12,
    strip_depth_fraction: float = 0.04,
) -> dict:
    h, w = card_image.shape[:2]
    hsv = cv2.cvtColor(card_image, cv2.COLOR_BGR2HSV)

    ex_h, ex_w = int(h * corner_exclusion_fraction), int(w * corner_exclusion_fraction)
    depth_h = max(2, int(h * strip_depth_fraction))
    depth_w = max(2, int(w * strip_depth_fraction))

    regions = {
        # axis=0 collapses strip depth, leaving one flag per position along the edge's length
        "top": {
            "outer": hsv[0:depth_h, ex_w : w - ex_w, 1],
            "inner": hsv[depth_h : 2 * depth_h, ex_w : w - ex_w, 1],
            "axis": 0,
        },
        "bottom": {
            "outer": hsv[h - depth_h : h, ex_w : w - ex_w, 1],
            "inner": hsv[h - 2 * depth_h : h - depth_h, ex_w : w - ex_w, 1],
            "axis": 0,
        },
        "left": {
            "outer": hsv[ex_h : h - ex_h, 0:depth_w, 1],
            "inner": hsv[ex_h : h - ex_h, depth_w : 2 * depth_w, 1],
            "axis": 1,
        },
        "right": {
            "outer": hsv[ex_h : h - ex_h, w - depth_w : w, 1],
            "inner": hsv[ex_h : h - ex_h, w - 2 * depth_w : w - depth_w, 1],
            "axis": 1,
        },
    }

    per_edge = {
        name: _analyze_strip(region["outer"], region["inner"], region["axis"])
        for name, region in regions.items()
    }
    raw_score = round(float(np.mean([e["score"] for e in per_edge.values()])), 2)

    measurements = {"per_edge": per_edge}
    return {"category": CATEGORY, "raw_score": raw_score, "measurements": measurements, "flags": {}}
