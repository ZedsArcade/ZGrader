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

from zgrader.analysis import assessment, capture, scoring
from zgrader.models import AnalysisCategory

CATEGORY = AnalysisCategory.edges

_WHITENING_SATURATION_DEFICIT = 40.0

# Strip geometry. Exported because annotate.annotate_edges and
# regions._build_edge_regions have to draw exactly the strips that were
# measured -- they each used to carry their own copy of these numbers, so
# retuning here silently desynchronized the overlay from the measurement.
CORNER_EXCLUSION_FRACTION = 0.12
STRIP_DEPTH_FRACTION = 0.04


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
    # No pixels to look at is not evidence of a clean edge. This used to
    # return a hardcoded 10.0, i.e. absence of data scored as perfection --
    # the edge is reported unmeasured instead and measure_edges leaves it out
    # of the category mean.
    if outer_saturation.size == 0:
        return {"score": None, "measured": False}

    ref_sat = float(np.mean(inner_saturation)) if inner_saturation.size else float(np.mean(outer_saturation))
    deficit = np.clip(ref_sat - outer_saturation.astype(np.float32), 0, None)
    whitened_mask = deficit > _WHITENING_SATURATION_DEFICIT
    whitened_fraction = float(np.mean(whitened_mask))

    collapsed_along_edge = np.any(whitened_mask, axis=along_axis)
    longest_run = _longest_true_run(collapsed_along_edge)
    run_fraction = longest_run / max(1, len(collapsed_along_edge))

    score = scoring.edge_score(whitened_fraction, run_fraction)
    return {
        "score": round(score, 2),
        "measured": True,
        "whitened_fraction": round(whitened_fraction, 3),
        "longest_run_fraction": round(run_fraction, 3),
        "reference_saturation": round(ref_sat, 1),
    }


def measure_edges(
    card_image: np.ndarray,
    corner_exclusion_fraction: float = CORNER_EXCLUSION_FRACTION,
    strip_depth_fraction: float = STRIP_DEPTH_FRACTION,
    px_per_mm: float | None = None,
) -> dict:
    """px_per_mm is optional; omitting it means no claim is made about whether
    the capture was good enough (see capture.resolution_limitation)."""
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

    measured = [e["score"] for e in per_edge.values() if e.get("measured")]
    if not measured:
        # Every strip was empty, so the crop is degenerate (far too small, or
        # collapsed by a bad warp). Fail loudly rather than emit a score --
        # pipeline turns this into a PipelineError and the submission into an
        # operator-visible error, which is the honest outcome.
        raise ValueError(
            "No edge strip contained any pixels -- the deskewed card image is "
            "too small or the crop is degenerate."
        )
    raw_score = round(float(np.mean(measured)), 2)

    partial = len(measured) < len(per_edge)
    capture_code, too_low_resolution = capture.resolution_limitation(px_per_mm)
    measurements = {
        "per_edge": per_edge,
        "measured_edges": len(measured),
    }

    if too_low_resolution:
        # Edge whitening is a fraction of a millimetre of exposed cardstock at
        # the cut. Below the resolution floor the outer strip is a handful of
        # pixels wide and any saturation deficit in it is as likely to be
        # compression noise as wear. Same treatment as corners: keep the
        # per-edge numbers as diagnostics, publish no score.
        measurements["assessment"] = assessment.unmeasurable((capture_code,)).as_dict()
        return {
            "category": CATEGORY,
            "raw_score": None,
            "measurements": measurements,
            "flags": {
                "lower_confidence": True,
                "reason": (
                    "The card occupies too few pixels in this photo for edge "
                    "wear to be visible at all, so edges were not scored. A "
                    "closer or higher-resolution photo would let this be "
                    "measured."
                ),
            },
        }

    limitations = [assessment.EDGES_PARTIAL] if partial else []
    confidence = assessment.CONFIDENCE_EDGES_PARTIAL if partial else assessment.CONFIDENCE_EDGES
    if capture_code is not None:
        limitations.append(capture_code)
        confidence *= assessment.CONFIDENCE_MODEST_RESOLUTION_FACTOR

    measurements["assessment"] = assessment.measured(
        raw_score, confidence, tuple(limitations)
    ).as_dict()
    flags = {}
    if partial:
        unmeasured = sorted(name for name, e in per_edge.items() if not e.get("measured"))
        flags = {
            "lower_confidence": True,
            "reason": (
                "Some edges could not be measured and were left out of this "
                f"score rather than counted as clean: {', '.join(unmeasured)}."
            ),
        }
    return {"category": CATEGORY, "raw_score": raw_score, "measurements": measurements, "flags": flags}
