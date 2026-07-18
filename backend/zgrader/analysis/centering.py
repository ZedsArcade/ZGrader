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

from zgrader.models import AnalysisCategory

CATEGORY = AnalysisCategory.centering


def _first_strong_edge(strip: np.ndarray, skip_px: int = 3) -> float:
    """Index of the strongest gradient point in `strip`, skipping the first
    `skip_px` samples (the physical cut edge itself, not the printed border)."""
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
) -> float:
    h, w = edge_map.shape
    if side in ("left", "right"):
        search_depth = max(4, int(w * search_fraction))
        margin = max(1, int(h * corner_margin_fraction))
        sample_rows = np.linspace(margin, max(margin, h - margin - 1), num_samples).astype(int)
        widths = []
        for r in sample_rows:
            strip = (
                edge_map[r, 0:search_depth]
                if side == "left"
                else edge_map[r, w - search_depth : w][::-1]
            )
            widths.append(_first_strong_edge(strip))
        return float(np.median(widths))
    else:
        search_depth = max(4, int(h * search_fraction))
        margin = max(1, int(w * corner_margin_fraction))
        sample_cols = np.linspace(margin, max(margin, w - margin - 1), num_samples).astype(int)
        widths = []
        for c in sample_cols:
            strip = (
                edge_map[0:search_depth, c]
                if side == "top"
                else edge_map[h - search_depth : h, c][::-1]
            )
            widths.append(_first_strong_edge(strip))
        return float(np.median(widths))


def _score_from_worse_pct(worse_pct: float) -> float:
    """50/50 -> 10.0, 100/0 -> 0.0, linear in between."""
    score = 10.0 - (worse_pct - 50.0) / 5.0
    return float(np.clip(score, 0.0, 10.0))


def measure_centering(card_image: np.ndarray, dpi: int) -> dict:
    gray = cv2.cvtColor(card_image, cv2.COLOR_BGR2GRAY)
    edge_map = np.abs(cv2.Laplacian(gray, cv2.CV_64F))

    left = _measure_border(edge_map, "left")
    right = _measure_border(edge_map, "right")
    top = _measure_border(edge_map, "top")
    bottom = _measure_border(edge_map, "bottom")

    px_per_mm = dpi / 25.4
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

    measurements = {
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
    raw_score = round(_score_from_worse_pct(worse_side_pct), 2)
    return {"category": CATEGORY, "raw_score": raw_score, "measurements": measurements, "flags": {}}
