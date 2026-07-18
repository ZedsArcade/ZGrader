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


def _local_variance(gray: np.ndarray, window: int = 9) -> np.ndarray:
    gray_f = gray.astype(np.float32)
    mean = cv2.boxFilter(gray_f, ddepth=-1, ksize=(window, window))
    sq_mean = cv2.boxFilter(gray_f * gray_f, ddepth=-1, ksize=(window, window))
    return np.clip(sq_mean - mean * mean, 0, None)


def measure_surface(card_image: np.ndarray, corner_exclusion_fraction: float = 0.12) -> tuple[dict, np.ndarray]:
    h, w = card_image.shape[:2]
    ex_h, ex_w = int(h * corner_exclusion_fraction), int(w * corner_exclusion_fraction)
    face = card_image[ex_h : h - ex_h, ex_w : w - ex_w]
    gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)

    local_var = _local_variance(gray)
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    threshold = float(np.mean(local_var) + 3.0 * np.std(local_var))
    anomaly_mask = local_var > threshold
    anomaly_fraction = float(np.mean(anomaly_mask))

    raw_score = round(float(np.clip(10.0 - anomaly_fraction * 200.0, 0.0, 10.0)), 2)
    measurements = {
        "anomaly_fraction": round(anomaly_fraction, 4),
        "laplacian_variance": round(laplacian_var, 1),
        "corner_exclusion_fraction": corner_exclusion_fraction,
    }
    result = {
        "category": CATEGORY,
        "raw_score": raw_score,
        "measurements": measurements,
        "flags": SURFACE_LOWER_CONFIDENCE_FLAG,
    }
    return result, anomaly_mask
