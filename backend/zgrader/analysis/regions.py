"""Builds per-region "defect breakout" data for the web results page: named
image regions (corners/edges/frame/surface blobs) with normalized bounding
boxes, a leader-line anchor point, and an already-localized note for flagged
regions.

Consumed only for front/back-side AnalysisResult rows (a defect belongs to
one physical scan, not the averaged "combined" abstraction) and stored under
measurements["regions"] -- no schema change needed since
AnalysisResult.measurements is JSONB.

Geometry mirrors zgrader.analysis.annotate's drawing functions exactly (same
fractions, same box math) so the breakout boxes line up with what the PDF
already draws -- see that module's docstrings for why each fraction exists.
"""

import cv2
import numpy as np

from zgrader.models import AnalysisCategory

MAX_SURFACE_REGIONS = 6
MIN_BLOB_AREA_MM2 = 0.5
# A scratch/scuff is either elongated (thin line -> high aspect ratio) or a
# dense solid gouge (fills most of its own bounding box -> high fill
# ratio). An individual text glyph's bounding box is close to square
# (aspect ratio near 1) and mostly empty space around the ink strokes
# (fill ratio well under these thresholds in practice) -- this heuristic
# rejects glyph-shaped blobs (card rules text) while keeping scratch-shaped
# ones. Tunable v1 starting point, like MIN_BLOB_AREA_MM2 above.
_MIN_ASPECT_RATIO = 2.0
_MIN_FILL_RATIO = 0.7

# Matches annotate.py's _FLAG_COLOR/_OK_COLOR cutoff -- same "worth calling
# out" threshold already used everywhere else in this pipeline.
_FLAG_THRESHOLD = 8.0

_CORNER_LABELS_EN = {
    "top_left": "top-left corner",
    "top_right": "top-right corner",
    "bottom_left": "bottom-left corner",
    "bottom_right": "bottom-right corner",
}
_CORNER_LABELS_ES = {
    "top_left": "esquina superior izquierda",
    "top_right": "esquina superior derecha",
    "bottom_left": "esquina inferior izquierda",
    "bottom_right": "esquina inferior derecha",
}
_EDGE_LABELS_EN = {"top": "top edge", "bottom": "bottom edge", "left": "left edge", "right": "right edge"}
_EDGE_LABELS_ES = {
    "top": "borde superior",
    "bottom": "borde inferior",
    "left": "borde izquierdo",
    "right": "borde derecho",
}


def _corner_note(name: str, info: dict, is_es: bool) -> str:
    label = (_CORNER_LABELS_ES if is_es else _CORNER_LABELS_EN)[name]
    if is_es:
        return f"Desgaste/redondeo detectado en la {label} (puntuación {info['combined_score']:.1f}/10)."
    return f"Whitening/rounding detected on the {label} (score {info['combined_score']:.1f}/10)."


def _edge_note(name: str, info: dict, is_es: bool) -> str:
    label = (_EDGE_LABELS_ES if is_es else _EDGE_LABELS_EN)[name]
    if is_es:
        return f"Blanqueamiento detectado en el {label} (puntuación {info['score']:.1f}/10)."
    return f"Whitening detected on the {label} (score {info['score']:.1f}/10)."


def _centering_note(worse_side_pct: float, is_es: bool) -> str:
    better_side_pct = 100 - worse_side_pct
    if is_es:
        return f"Carta descentrada ({worse_side_pct:.0f}/{better_side_pct:.0f})."
    return f"Card is off-center ({worse_side_pct:.0f}/{better_side_pct:.0f})."


def _surface_note(length_mm: float, is_es: bool) -> str:
    # Deliberately no fabricated per-blob "impact" number here (e.g. no
    # "Subgrade impact: -1.0") -- there's no real per-blob scoring formula
    # anywhere in this codebase, only a whole-image aggregate score. Stating
    # a made-up number would look precise without being real; a calibrated
    # per-defect impact score is a reasonable follow-up once real
    # methodology exists, not something to invent here.
    if is_es:
        return f"Posible rayón en la superficie, aprox. {length_mm:.1f}mm."
    return f"Possible surface scratch, approx. {length_mm:.1f}mm."


def _region(
    id_: str,
    kind: str,
    severity: str,
    score: float,
    bbox_px: tuple[float, float, float, float],
    anchor_px: tuple[float, float],
    w: int,
    h: int,
    note: str | None,
) -> dict:
    x0, y0, x1, y1 = bbox_px
    ax, ay = anchor_px
    return {
        "id": id_,
        "kind": kind,
        "severity": severity,
        "score": round(float(score), 2),
        "bbox_norm": [round(x0 / w, 4), round(y0 / h, 4), round(x1 / w, 4), round(y1 / h, 4)],
        "anchor_norm": [round(ax / w, 4), round(ay / h, 4)],
        "note": note,
    }


def _build_corner_regions(card_shape: tuple[int, int], language: str, result: dict) -> list[dict]:
    h, w = card_shape
    is_es = language == "es"
    corner_fraction = result["measurements"].get("corner_fraction", 0.12)
    size = max(8, int(min(h, w) * corner_fraction))
    inset = max(1, int(size * 0.08))

    boxes = {
        "top_left": (0, 0, size, size),
        "top_right": (w - size, 0, w, size),
        "bottom_left": (0, h - size, size, h),
        "bottom_right": (w - size, h - size, w, h),
    }
    regions = []
    for name, info in result["measurements"]["per_corner"].items():
        box = boxes[name]
        score = info["combined_score"]
        flagged = score < _FLAG_THRESHOLD
        anchor = (
            inset if "left" in name else w - inset,
            inset if "top" in name else h - inset,
        )
        note = _corner_note(name, info, is_es) if flagged else None
        regions.append(_region(name, "corner", "flag" if flagged else "ok", score, box, anchor, w, h, note))
    return regions


def _build_edge_regions(card_shape: tuple[int, int], language: str, result: dict) -> list[dict]:
    h, w = card_shape
    is_es = language == "es"
    # edges.py doesn't persist these fractions (unlike corners.py's
    # corner_fraction) -- hardcoded to match annotate_edges's own defaults,
    # a pre-existing duplication in this codebase, not introduced here.
    ex_h, ex_w = int(h * 0.12), int(w * 0.12)
    depth_h, depth_w = max(2, int(h * 0.04)), max(2, int(w * 0.04))

    boxes = {
        "top": (ex_w, 0, w - ex_w, depth_h),
        "bottom": (ex_w, h - depth_h, w - ex_w, h),
        "left": (0, ex_h, depth_w, h - ex_h),
        "right": (w - depth_w, ex_h, w, h - ex_h),
    }
    regions = []
    for name, info in result["measurements"]["per_edge"].items():
        box = boxes[name]
        score = info["score"]
        flagged = score < _FLAG_THRESHOLD
        anchor = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        note = _edge_note(name, info, is_es) if flagged else None
        regions.append(_region(name, "edge", "flag" if flagged else "ok", score, box, anchor, w, h, note))
    return regions


def _build_centering_regions(card_shape: tuple[int, int], language: str, result: dict) -> list[dict]:
    h, w = card_shape
    is_es = language == "es"
    score = result["raw_score"]
    if score >= _FLAG_THRESHOLD:
        return []

    m = result["measurements"]
    box = (m["left_px"], m["top_px"], w - m["right_px"], h - m["bottom_px"])
    anchor = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
    note = _centering_note(m["worse_side_pct"], is_es)
    return [_region("frame", "frame", "flag", score, box, anchor, w, h, note)]


def _build_surface_regions(
    card_shape: tuple[int, int], dpi: int, language: str, result: dict, anomaly_mask: np.ndarray | None
) -> list[dict]:
    h, w = card_shape
    is_es = language == "es"
    if anomaly_mask is None or not anomaly_mask.any():
        return []

    ex_fraction = result["measurements"].get("corner_exclusion_fraction", 0.12)
    ex_h, ex_w = int(h * ex_fraction), int(w * ex_fraction)

    num_labels, _labels, stats, centroids = cv2.connectedComponentsWithStats(
        anomaly_mask.astype(np.uint8), connectivity=8
    )

    px_per_mm = dpi / 25.4
    min_area_px = MIN_BLOB_AREA_MM2 * px_per_mm * px_per_mm

    def _is_scratch_like(label: int) -> bool:
        bw = stats[label, cv2.CC_STAT_WIDTH]
        bh = stats[label, cv2.CC_STAT_HEIGHT]
        area = stats[label, cv2.CC_STAT_AREA]
        aspect_ratio = max(bw, bh) / max(1, min(bw, bh))
        fill_ratio = area / max(1, bw * bh)
        return aspect_ratio >= _MIN_ASPECT_RATIO or fill_ratio >= _MIN_FILL_RATIO

    # label 0 is always the background component -- skip it.
    blobs = [
        (label, stats[label, cv2.CC_STAT_AREA])
        for label in range(1, num_labels)
        if stats[label, cv2.CC_STAT_AREA] >= min_area_px and _is_scratch_like(label)
    ]
    blobs.sort(key=lambda item: item[1], reverse=True)
    blobs = blobs[:MAX_SURFACE_REGIONS]

    regions = []
    for i, (label, _area) in enumerate(blobs):
        # anomaly_mask is computed on the cropped `face` sub-image (see
        # surface.py's measure_surface), so every coordinate here needs the
        # same (ex_w, ex_h) offset applied to land on the full card_image.
        x = stats[label, cv2.CC_STAT_LEFT] + ex_w
        y = stats[label, cv2.CC_STAT_TOP] + ex_h
        w_px = stats[label, cv2.CC_STAT_WIDTH]
        h_px = stats[label, cv2.CC_STAT_HEIGHT]
        cx = centroids[label][0] + ex_w
        cy = centroids[label][1] + ex_h

        length_mm = max(w_px, h_px) / px_per_mm
        note = _surface_note(length_mm, is_es)
        box = (x, y, x + w_px, y + h_px)
        regions.append(_region(f"blob_{i}", "blob", "flag", result["raw_score"], box, (cx, cy), w, h, note))
    return regions


def build_regions(
    category: AnalysisCategory,
    card_shape: tuple[int, int],
    dpi: int,
    language: str,
    result: dict,
    extra,
) -> list[dict]:
    """card_shape is (height, width), matching np.ndarray.shape[:2]."""
    if category == AnalysisCategory.corners:
        return _build_corner_regions(card_shape, language, result)
    if category == AnalysisCategory.edges:
        return _build_edge_regions(card_shape, language, result)
    if category == AnalysisCategory.centering:
        return _build_centering_regions(card_shape, language, result)
    if category == AnalysisCategory.surface:
        return _build_surface_regions(card_shape, dpi, language, result, extra)
    raise ValueError(f"Unknown analysis category: {category}")
