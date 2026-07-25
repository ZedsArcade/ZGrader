"""Crease detection (v1, best-effort).

A crease is a broken-fibre line that, under flat diffuse scan light, shows up
(when it shows at all) as a faint long tonal line running across the card and
ignoring the printed design. This detector boosts local contrast (CLAHE),
finds edges, and keeps only long, roughly-straight lines in the card interior
-- excluding the border/frame region where the printed edges live.

IMPORTANT LIMITATION: like surface scratches, creases really want raking
(low-angle) light to cast a shadow along the ridge; a single diffuse scan
catches only pronounced creases and will have false positives on holo/foil.
So detected creases are surfaced as *lower-confidence, dismissible* findings
and deliberately do NOT change the numeric grade in this version.
"""

import cv2
import numpy as np

# Ignore this fraction of the card on every side -- the printed border/frame
# lives here and its straight edges would otherwise read as "creases".
_BORDER_EXCLUSION_FRACTION = 0.12
# A crease spans a large fraction of the card; short edges are print detail.
_MIN_LENGTH_FRACTION = 0.2
# A card rarely has more than a couple of genuinely distinct creases, and a
# lower cap keeps the report readable.
_MAX_CREASES = 2
# Two segments describe the same physical crease when they run near-parallel
# and sit close together. Both tolerances are relative to the card, not fixed
# pixel counts -- a fixed tolerance is meaningless across scan resolutions
# (it was why one crease was reported three times on a high-res photo).
_MAX_ANGLE_DIFF_DEG = 10.0
_DUP_OFFSET_FRACTION = 0.05


def detect_creases(card_image: np.ndarray, px_per_mm: float) -> list[dict]:
    """Returns up to _MAX_CREASES candidate crease lines as
    {"p1": (x, y), "p2": (x, y), "length_mm": float} in full-card pixel
    coordinates (x, y). Empty when nothing crosses the interior.

    px_per_mm comes from the card's physical size (analysis/scale.py) -- an
    image's DPI metadata bears no relation to how many pixels cover the card
    in a photo, and using it produced impossible lengths (e.g. a 244mm crease
    on an 88mm-tall card).
    """
    h, w = card_image.shape[:2]
    ex_h, ex_w = int(h * _BORDER_EXCLUSION_FRACTION), int(w * _BORDER_EXCLUSION_FRACTION)
    interior = card_image[ex_h : h - ex_h, ex_w : w - ex_w]
    if interior.size == 0:
        return []

    gray = cv2.cvtColor(interior, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
    edges = cv2.Canny(blurred, 40, 120)

    min_len = int(min(h, w) * _MIN_LENGTH_FRACTION)
    # A generous gap bridges the fragmented Canny edges a single crease
    # produces into one line; a real crease still has to clear min_len.
    raw = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=40,
        minLineLength=min_len,
        maxLineGap=int(min_len * 0.35),
    )
    if raw is None:
        return []

    candidates = []
    for line in raw.reshape(-1, 4):
        x1, y1, x2, y2 = (int(v) for v in line)
        length_px = float(np.hypot(x2 - x1, y2 - y1))
        candidates.append((length_px, (x1 + ex_w, y1 + ex_h), (x2 + ex_w, y2 + ex_h)))

    # Longest first, then greedily drop segments that describe a crease we've
    # already kept, so one physical crease traced as several fragments is
    # reported once.
    tol_px = min(h, w) * _DUP_OFFSET_FRACTION
    candidates.sort(key=lambda c: c[0], reverse=True)
    kept: list[tuple[float, tuple[int, int], tuple[int, int]]] = []
    for cand in candidates:
        if all(not _same_crease(cand, k, tol_px) for k in kept):
            kept.append(cand)
        if len(kept) >= _MAX_CREASES:
            break

    return [
        {"p1": p1, "p2": p2, "length_mm": round(length_px / px_per_mm, 1)}
        for length_px, p1, p2 in kept
    ]


def _same_crease(a, b, tol_px: float) -> bool:
    """True when two segments describe the same physical crease: near-parallel
    *and* laterally close. Comparing endpoints instead (the earlier approach)
    misses parallel fragments that trace the same crease a little apart."""
    _, a1, a2 = a
    _, b1, b2 = b
    if _angle_between(a1, a2, b1, b2) > _MAX_ANGLE_DIFF_DEG:
        return False
    # Perpendicular distance from b's midpoint to the infinite line through a.
    b_mid = ((b1[0] + b2[0]) / 2.0, (b1[1] + b2[1]) / 2.0)
    return _point_line_distance(b_mid, a1, a2) <= tol_px


def _angle_between(a1, a2, b1, b2) -> float:
    """Smallest angle (degrees, 0-90) between two undirected segments."""
    va = np.array([a2[0] - a1[0], a2[1] - a1[1]], dtype=float)
    vb = np.array([b2[0] - b1[0], b2[1] - b1[1]], dtype=float)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    cosine = abs(float(np.dot(va, vb)) / (na * nb))  # abs -> direction-agnostic
    return float(np.degrees(np.arccos(np.clip(cosine, 0.0, 1.0))))


def _point_line_distance(point, line_p1, line_p2) -> float:
    p = np.array(point, dtype=float)
    a = np.array(line_p1, dtype=float)
    b = np.array(line_p2, dtype=float)
    ab = b - a
    length = np.linalg.norm(ab)
    if length == 0:
        return float(np.linalg.norm(p - a))
    ap = p - a
    # 2D cross product magnitude (np.cross on 2-vectors is deprecated).
    return float(abs(ab[0] * ap[1] - ab[1] * ap[0]) / length)
