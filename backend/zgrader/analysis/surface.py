"""Surface analysis: flag scratches/print-line anomalies via local texture
variance (a sliding-window variance map computed with the box-filter trick:
Var(X) = E[X^2] - E[X]^2), excluding the corner/edge margins.

IMPORTANT LIMITATION (documented here and surfaced in the PDF report):
flatbed scanning uses diffuse light, not the raking/angled light professional
graders use specifically to catch surface scratches and print lines. Defects
only visible under angled light will be under-detected by this category --
it is intentionally flagged "lower_confidence" in every result.
"""

import cv2
import numpy as np

from zgrader.analysis import assessment, scoring
from zgrader.models import AnalysisCategory

CATEGORY = AnalysisCategory.surface

SURFACE_LOWER_CONFIDENCE_FLAG = {
    "lower_confidence": True,
    "reason": (
        "Flatbed scanning uses diffuse light, not the raking/angled light "
        "professional graders use to catch surface scratches and print lines. "
        "This category may under-detect defects only visible under angled light."
    ),
}


# --- Which anomalies are physically scratch-like ----------------------------
#
# These live here rather than in regions.py because the *score* needs them, and
# a filter that decides what a customer is shown but not what they are charged
# for is two different opinions about the same card. regions.py imports them
# back for its overlay boxes, so the drawing and the number stay in step.
#
# A genuine scratch or print line is elongated AND has a thin mean stroke. Card
# text -- the dominant false positive on holo and full-art cards -- groups into
# per-word blobs at roughly 0.9-1.3mm mean stroke thickness, where a real
# hairline scratch is about 0.6mm, so the thickness gate is what actually
# rejects text. The modest aspect floor additionally rejects near-round holo
# sparkles; a diagonal scratch's own bounding box is "fat" at about 2.1, so the
# floor is kept low.
#
# Both are described in customer-facing terms on the public /methodology page,
# and its figures are generated from this code.
#: Below this raw anomaly fraction, the image carries no fine detail at all
#: and surface cannot be assessed.
#:
#: Every real card has micro-texture: paper fibre, print rosettes, the edges of
#: its own artwork. A sharp photograph of one flags about 0.4% of the face even
#: when the card is clean, and a real photograph flags 2.4-3.3%. So a reading
#: near zero does not mean "nothing is wrong with this card", it means the
#: image has nothing in it to find -- blur or blown-out glare has removed the
#: high-frequency content that a scratch would also have lived in.
#:
#: Measured on the fixtures: the deliberately soft capture flags 0.0000 and the
#: glared one 0.0003, against 0.0038 for the same card sharp. Both used to
#: score a flat 10.00 -- absence of evidence as perfection, which is the
#: pattern the resolution gate removed from corners and edges. Surface had no
#: capture gate at all.
#:
#: This is content-independent in the way sharpness is not: it asks whether
#: *this* image has detail, not whether it has as much as some other card.
MIN_DETAIL_FRACTION = 0.001

MIN_BLOB_AREA_MM2 = 0.5
MIN_ASPECT_RATIO = 1.8
MAX_SCRATCH_THICKNESS_MM = 0.85


def scratch_like_fraction(anomaly_mask: np.ndarray, px_per_mm: float) -> float:
    """Fraction of the examined face occupied by physically scratch-like
    anomalies, rather than by everything the variance threshold noticed.

    This is the number the score is built from, and the reason is what real
    photographs showed. The raw threshold mask holds one connected component on
    a synthetic card and between 237 and 1183 on a photograph of a real one --
    paper fibre, print rosettes, holo sparkle and JPEG noise. It flagged 2.4 to
    3.3% of every real card, which drove every one of them to a surface score
    between 3.4 and 5.3 regardless of condition.

    The filter that separates a scratch from grain already existed and was
    already applied to the regions a customer is shown. It simply was not
    applied to the score, so the report displayed six findings while the number
    was computed from several hundred. Synthetics never revealed it because
    their raw and filtered fractions are identical to four decimal places --
    there is nothing on a generated card for the filter to reject.
    """
    if px_per_mm is None or px_per_mm <= 0 or not anomaly_mask.any():
        return float(np.mean(anomaly_mask))

    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        anomaly_mask.astype(np.uint8), connectivity=8
    )
    min_area_px = MIN_BLOB_AREA_MM2 * px_per_mm * px_per_mm

    kept = 0
    for label in range(1, count):  # label 0 is the background
        width = stats[label, cv2.CC_STAT_WIDTH]
        height = stats[label, cv2.CC_STAT_HEIGHT]
        area = stats[label, cv2.CC_STAT_AREA]
        if area < min_area_px:
            continue
        longest = max(width, height)
        aspect = longest / max(1, min(width, height))
        # Mean stroke thickness ~= filled area / length. Orientation-robust,
        # unlike min(bbox side), which is large for a diagonal hairline.
        thickness_mm = (area / longest) / px_per_mm
        if aspect >= MIN_ASPECT_RATIO and thickness_mm <= MAX_SCRATCH_THICKNESS_MM:
            kept += area
    return float(kept) / anomaly_mask.size


def score_from_anomaly_fraction(anomaly_fraction: float) -> float:
    """Thin delegate to the scoring layer.

    The mapping lives in analysis/scoring.py; detecting anomalous texture and
    deciding what a given amount of it is worth are separate jobs. Kept as a
    name because recompute.py and regions.py call it.
    """
    return scoring.surface_score(anomaly_fraction)


def _local_variance(gray: np.ndarray, window: int = 9) -> np.ndarray:
    gray_f = gray.astype(np.float32)
    mean = cv2.boxFilter(gray_f, ddepth=-1, ksize=(window, window))
    sq_mean = cv2.boxFilter(gray_f * gray_f, ddepth=-1, ksize=(window, window))
    return np.clip(sq_mean - mean * mean, 0, None)


def measure_surface(card_image: np.ndarray, corner_exclusion_fraction: float = 0.12, px_per_mm: float | None = None) -> tuple[dict, np.ndarray]:
    h, w = card_image.shape[:2]
    ex_h, ex_w = int(h * corner_exclusion_fraction), int(w * corner_exclusion_fraction)
    face = card_image[ex_h : h - ex_h, ex_w : w - ex_w]
    gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)

    local_var = _local_variance(gray)
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    threshold = float(np.mean(local_var) + 3.0 * np.std(local_var))
    anomaly_mask = local_var > threshold
    raw_anomaly_fraction = float(np.mean(anomaly_mask))
    # Scored on what survives the physical filter, not on everything the
    # variance threshold noticed. See scratch_like_fraction.
    anomaly_fraction = scratch_like_fraction(anomaly_mask, px_per_mm)

    # No fine detail in the image at all means no scratch could have shown up
    # either. See MIN_DETAIL_FRACTION.
    no_detail = raw_anomaly_fraction < MIN_DETAIL_FRACTION
    raw_score = None if no_detail else round(score_from_anomaly_fraction(anomaly_fraction), 2)

    measurements = {
        "anomaly_fraction": round(anomaly_fraction, 4),
        # Kept alongside so the gap between "noticed" and "believed" stays
        # visible; on a real photograph it is several times larger.
        "raw_anomaly_fraction": round(raw_anomaly_fraction, 4),
        "laplacian_variance": round(laplacian_var, 1),
        "corner_exclusion_fraction": corner_exclusion_fraction,
    }
    if no_detail:
        measurements["assessment"] = assessment.unmeasurable(
            (assessment.SURFACE_NO_DETAIL,)
        ).as_dict()
        flags = {
            "lower_confidence": True,
            "reason": (
                "This photo carries no fine detail on the card's face -- blur or "
                "blown-out glare has removed it -- so a scratch could not have "
                "shown up in it either. Surface was not scored. A sharper photo, "
                "or one without the glare, would let it be assessed."
            ),
        }
    else:
        measurements["assessment"] = assessment.measured(
            raw_score,
            assessment.CONFIDENCE_SURFACE,
            (assessment.SURFACE_DIFFUSE_LIGHT,),
        ).as_dict()
        flags = SURFACE_LOWER_CONFIDENCE_FLAG

    result = {
        "category": CATEGORY,
        "raw_score": raw_score,
        "measurements": measurements,
        "flags": flags,
    }
    return result, anomaly_mask
