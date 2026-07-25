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
_MAX_CREASES = 3


def detect_creases(card_image: np.ndarray, dpi: int) -> list[dict]:
    """Returns up to _MAX_CREASES candidate crease lines as
    {"p1": (x, y), "p2": (x, y), "length_mm": float} in full-card pixel
    coordinates (x, y). Empty when nothing crosses the interior."""
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

    px_per_mm = dpi / 25.4
    candidates = []
    for line in raw.reshape(-1, 4):
        x1, y1, x2, y2 = (int(v) for v in line)
        length_px = float(np.hypot(x2 - x1, y2 - y1))
        candidates.append((length_px, (x1 + ex_w, y1 + ex_h), (x2 + ex_w, y2 + ex_h)))

    # Longest first, then greedily drop near-duplicate/near-collinear lines so
    # a single crease traced as several segments counts once.
    candidates.sort(key=lambda c: c[0], reverse=True)
    kept: list[tuple[float, tuple[int, int], tuple[int, int]]] = []
    for cand in candidates:
        if all(not _similar(cand, k) for k in kept):
            kept.append(cand)
        if len(kept) >= _MAX_CREASES:
            break

    return [
        {"p1": p1, "p2": p2, "length_mm": round(length_px / px_per_mm, 1)}
        for length_px, p1, p2 in kept
    ]


def _similar(a, b, tol_px: int = 40) -> bool:
    """Two segments are near-duplicates if both endpoints of one are close to
    the corresponding endpoints of the other (either orientation)."""
    _, a1, a2 = a
    _, b1, b2 = b
    straight = _dist(a1, b1) < tol_px and _dist(a2, b2) < tol_px
    flipped = _dist(a1, b2) < tol_px and _dist(a2, b1) < tol_px
    return straight or flipped


def _dist(p, q) -> float:
    return float(np.hypot(p[0] - q[0], p[1] - q[1]))
