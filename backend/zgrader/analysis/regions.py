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
# A genuine scratch/print-line is elongated AND has a thin mean stroke.
# Card text -- the dominant false positive on holo/full-art cards -- gets
# grouped by connected-component analysis into per-word blobs; measured
# with the real variance detector these come out at ~0.9-1.3mm mean stroke
# thickness, whereas a real hairline scratch is ~0.6mm, so the thickness
# gate is what actually rejects text. The modest aspect floor additionally
# rejects near-round holo sparkles (a diagonal scratch's own bounding box
# is "fat", ~2.1, so the floor is kept low). Both thresholds were tuned
# against the real detector on rendered text vs. the scratch fixture;
# still best-effort -- see the surface-analysis limitation note in
# surface.py for why this whole category is lower-confidence.
_MIN_ASPECT_RATIO = 1.8
_MAX_SCRATCH_THICKNESS_MM = 0.85

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


def _crease_note(length_mm: float, is_es: bool) -> str:
    if is_es:
        return f"Posible pliegue, aprox. {length_mm:.0f}mm."
    return f"Possible crease, approx. {length_mm:.0f}mm."


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
    region = _region("frame", "frame", "flag", score, box, anchor, w, h, note)
    # Full-art / holo cards often have no clean printed border to measure
    # against (see centering.py's CENTERING_LOW_CONFIDENCE_FLAG) -- when the
    # measurement is flagged uncertain, mark the region so the UI can draw a
    # muted/dashed box instead of asserting a precise centering frame.
    if result.get("flags", {}).get("lower_confidence"):
        region["low_confidence"] = True
    return [region]


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
        longest = max(bw, bh)
        aspect_ratio = longest / max(1, min(bw, bh))
        # Mean stroke thickness ~= filled pixel area / length. Orientation-
        # robust (unlike min(bbox side), which is large for a *diagonal*
        # hairline whose bounding box is big on both axes): a real scratch
        # has a thin mean stroke at any angle, while a word's summed letter
        # strokes give a much thicker mean.
        mean_thickness_mm = (area / longest) / px_per_mm
        return aspect_ratio >= _MIN_ASPECT_RATIO and mean_thickness_mm <= _MAX_SCRATCH_THICKNESS_MM

    # label 0 is always the background component -- skip it.
    blobs = [
        (label, stats[label, cv2.CC_STAT_AREA])
        for label in range(1, num_labels)
        if stats[label, cv2.CC_STAT_AREA] >= min_area_px and _is_scratch_like(label)
    ]
    blobs.sort(key=lambda item: item[1], reverse=True)
    blobs = blobs[:MAX_SURFACE_REGIONS]

    # anomaly_fraction (surface.py) is mean(anomaly_mask), i.e.
    # anomaly_px / mask.size -- so a blob's contribution to that fraction is
    # its own pixel count over the same denominator. Storing it per blob
    # lets recompute.py subtract a dismissed blob and re-derive the surface
    # score without reprocessing the image.
    face_area_px = anomaly_mask.size

    regions = []
    for i, (label, blob_area_px) in enumerate(blobs):
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
        region = _region(f"blob_{i}", "blob", "flag", result["raw_score"], box, (cx, cy), w, h, note)
        region["area_fraction"] = round(float(blob_area_px) / max(1, face_area_px), 6)
        regions.append(region)
    return regions


def build_crease_regions(
    card_shape: tuple[int, int], dpi: int, language: str, crease_lines: list[dict]
) -> list[dict]:
    """Turn detected crease line segments (see creases.detect_creases) into
    flagged, lower-confidence regions. These are appended to the surface
    side's regions so they reuse the crop/annotation/dismiss machinery, but
    carry no `area_fraction` and no score, so they never change the numeric
    grade -- a v1 flag-only treatment (recompute.py ignores them)."""
    h, w = card_shape
    is_es = language == "es"
    out = []
    for i, line in enumerate(crease_lines):
        (x1, y1), (x2, y2) = line["p1"], line["p2"]
        box = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        anchor = ((x1 + x2) / 2, (y1 + y2) / 2)
        note = _crease_note(line["length_mm"], is_es)
        region = _region(f"crease_{i}", "crease", "flag", 0.0, box, anchor, w, h, note)
        region["low_confidence"] = True
        out.append(region)
    return out


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
