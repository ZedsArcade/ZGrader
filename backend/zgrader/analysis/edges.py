"""Edge analysis: how ragged each of the four cut edges is, and how far it has
frayed toward the white cardstock underneath.

WHY THE REFERENCE HAD TO CHANGE
-------------------------------
Whitening is measured by comparing the outermost sliver of card against clean
card a little further in. That comparison is only meaningful if "a little
further in" is still the same printed material.

The previous version sampled the outer 4% of the card and used the next 4%
inward as its reference, which assumes the printed border is thicker than 8%
of the card. Real Pokemon borders are around 5-6%. When the border is thinner
than the window, the reference lands on *artwork*, and the perfectly ordinary
colour difference between a border and the art it frames is read as whitening
along the entire length of the edge.

Measured on the fixtures, this was not a corner case:

    white_border_clean   border 0-3.5mm, artwork beyond    edges 0.00 / 10
    pokemon_front        border 0-4.5mm, reference straddled the transition

An undamaged white-bordered card scored zero. It is the worst false positive
in the pipeline and it fires on exactly the cards customers most often submit.

So the border is now **found** rather than assumed. A median colour profile is
built inward from each cut edge, the border/artwork transition is located as
the largest colour step in it, and the reference is taken from inside the
border only. When the border is too thin to hold both a sample and a
reference, the edge says so instead of inventing a number.

TWO CHANNELS, LIKE CORNERS
--------------------------
    photometric   lightness rise and chroma loss at the cut, against clean
                  border at the same position along the edge
    geometric     how far the fitted boundary wanders, in millimetres --
                  roughness along the whole edge and the single deepest nick

The geometric channel is new and nearly free: geometry.py already fits a
sub-pixel line to each side and keeps the residuals. A nick is a physical
excursion from a straight cut, which is a better description of a chewed edge
than any colour comparison, and it works on a border with no colour at all.

The worse of the two sets the score rather than their sum, for the same reason
as corners: a frayed edge is usually both, and adding them would count one
defect twice.
"""

import cv2
import numpy as np

from zgrader.analysis import assessment, capture, scoring
from zgrader.models import AnalysisCategory

CATEGORY = AnalysisCategory.edges

# --- Sampling geometry ------------------------------------------------------
# All in millimetres, because every quantity here is physical. The old
# fractions-of-the-card versions meant the strip examined a different amount of
# actual card on every scan.

#: How far inward to look for the border/artwork transition. Comfortably past
#: any real card's border without reaching the middle of the artwork.
MAX_BORDER_SEARCH_MM = 12.0

#: The sliver actually assessed for wear: the cut itself and just behind it.
OUTER_STRIP_MM = 0.4

#: Skipped when establishing what clean border looks like. Without it the
#: reference would include the frayed zone being measured, and a badly whitened
#: edge would calibrate itself as normal.
REFERENCE_INSET_MM = 0.6

#: Below this much clean border between the inset and the artwork, there is no
#: room for a reference that is not partly artwork. The edge is still reported,
#: with a limitation, rather than scored against the wrong material.
MIN_REFERENCE_WIDTH_MM = 0.8

#: Corner exclusion stays a fraction: it exists to hand those regions to
#: corners.py, whose window is defined the same way.
CORNER_EXCLUSION_FRACTION = 0.12

#: ARBITRARY. Colour step, in 8-bit Lab units, that marks the border/artwork
#: transition. Measured across the fixture set the real steps are enormous --
#: 112 and 192 in lightness alone -- so this only has to clear within-border
#: variation, which on a real photograph is the noisier quantity. Deliberately
#: well below the observed steps and well above print noise.
BORDER_TRANSITION_DELTA_E = 25.0

#: ARBITRARY. Per-position whitening, in the combined Lab measure below, above
#: which that position counts as whitened.
WHITENING_DELTA_THRESHOLD = 22.0

# Retained for the overlay and region boxes, which draw the outer strip. Both
# read these rather than carrying their own copies -- they used to, and
# retuning here silently desynchronised the drawing from the measurement.
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


def _edge_band(lab: np.ndarray, name: str, exclusion: float, depth_px: int) -> np.ndarray:
    """A band along one edge, oriented so axis 0 is depth inward from the cut
    and axis 1 runs along the edge.

    The flips are what let one analysis function serve all four edges, exactly
    as corner_crops does for corners.
    """
    h, w = lab.shape[:2]
    ex_h, ex_w = int(h * exclusion), int(w * exclusion)
    depth_px = max(2, min(depth_px, h // 2, w // 2))

    if name == "top":
        return lab[0:depth_px, ex_w : w - ex_w]
    if name == "bottom":
        return lab[h - depth_px : h, ex_w : w - ex_w][::-1]
    if name == "left":
        return np.transpose(lab[ex_h : h - ex_h, 0:depth_px], (1, 0, 2))
    return np.transpose(lab[ex_h : h - ex_h, w - depth_px : w][:, ::-1], (1, 0, 2))


def _border_depth_px(band: np.ndarray, px_per_mm: float) -> int | None:
    """Depth at which the printed border gives way to artwork, or None if no
    such transition is visible within the search window.

    None is a real answer, not a failure: a full-art card has artwork running
    to the cut, and comparing the outermost sliver against the artwork just
    behind it is still a valid local comparison. What must not happen is a
    transition landing *inside* the reference, which is the case this exists to
    detect.
    """
    inset = max(1, int(round(REFERENCE_INSET_MM * px_per_mm)))
    if band.shape[0] <= inset + 2:
        return None

    # Median across the edge's length, so a defect at one position cannot move
    # the profile: this is a question about the card's printing, not its wear.
    profile = np.median(band, axis=1)
    reference_colour = np.median(profile[inset : inset + max(2, int(0.5 * px_per_mm))], axis=0)
    delta = np.linalg.norm(profile - reference_colour, axis=1)

    beyond = np.nonzero(delta[inset:] > BORDER_TRANSITION_DELTA_E)[0]
    if not len(beyond):
        return None
    return int(beyond[0] + inset)


def _analyze_edge(band: np.ndarray, px_per_mm: float) -> dict:
    """Photometric wear along one edge, against clean border at the same
    position along that edge."""
    depth = band.shape[0]
    outer_px = max(1, int(round(OUTER_STRIP_MM * px_per_mm)))
    inset_px = max(1, int(round(REFERENCE_INSET_MM * px_per_mm)))

    if depth <= inset_px + 1 or band.shape[1] < 2:
        return {"score": None, "measured": False}

    transition = _border_depth_px(band, px_per_mm)
    reference_end = depth if transition is None else transition
    reference_width_mm = (reference_end - inset_px) / px_per_mm
    thin_border = reference_width_mm < MIN_REFERENCE_WIDTH_MM

    if thin_border:
        # Not enough clean border to reference against. Widening into the
        # artwork is exactly the bug this module was rewritten to remove, so
        # the edge reports that it could not be assessed photometrically and
        # leans on the geometric channel instead.
        return {
            "score": None,
            "measured": False,
            "reason": "thin_border",
            "border_width_mm": round((reference_end) / px_per_mm, 2),
        }

    outer = band[0:outer_px]
    reference = band[inset_px:reference_end]

    # Per-position, not a single figure for the whole edge: artwork and print
    # vary along an edge, and a global reference re-introduces a milder form of
    # the same false positive.
    outer_l = np.median(outer[:, :, 0], axis=0)
    outer_c = np.median(np.hypot(outer[:, :, 1] - 128.0, outer[:, :, 2] - 128.0), axis=0)
    ref_l = np.median(reference[:, :, 0], axis=0)
    ref_c = np.median(np.hypot(reference[:, :, 1] - 128.0, reference[:, :, 2] - 128.0), axis=0)

    lightness_rise = outer_l - ref_l
    chroma_loss = ref_c - outer_c
    # Whitening is both at once. Taking the larger of the two rather than their
    # sum keeps this on the same footing as corners, and stops a border that is
    # merely dark from reading as frayed.
    whitening = np.maximum(np.clip(lightness_rise, 0, None), np.clip(chroma_loss, 0, None))

    whitened_mask = whitening > WHITENING_DELTA_THRESHOLD
    whitened_fraction = float(np.mean(whitened_mask))
    longest_run = _longest_true_run(whitened_mask)
    run_fraction = longest_run / max(1, len(whitened_mask))

    return {
        "measured": True,
        "whitened_fraction": round(whitened_fraction, 3),
        "longest_run_fraction": round(run_fraction, 3),
        "longest_run_mm": round(longest_run / px_per_mm, 2),
        # Median describes the edge's typical state; peak describes its worst
        # point. Both are needed because edge damage is usually localised -- a
        # quarter of an edge can be badly frayed while the median position is
        # untouched, so a median alone reads as a clean edge.
        "median_lightness_rise": round(float(np.median(lightness_rise)), 1),
        "median_chroma_loss": round(float(np.median(chroma_loss)), 1),
        "peak_lightness_rise": round(float(np.max(lightness_rise)), 1),
        "peak_chroma_loss": round(float(np.max(chroma_loss)), 1),
        "border_width_mm": round(reference_end / px_per_mm, 2),
        "border_found": transition is not None,
    }


def _geometric(side: dict | None, px_per_mm: float) -> dict:
    """Edge roughness and the deepest nick, in millimetres.

    Free, in the sense that geometry.py already computed these while fitting
    the card's sides -- but new as a *scored* channel. It is the only edge
    measurement that works on a border with no colour to lose.
    """
    if not side or not side.get("refined"):
        return {"geometric_measured": False}
    return {
        "geometric_measured": True,
        "roughness_mm": round(side["roughness_px"] / px_per_mm, 3),
        "max_excursion_mm": round(side["max_excursion_px"] / px_per_mm, 3),
        "bow_mm": round(side["bow_px"] / px_per_mm, 3),
    }


def measure_edges(
    card_image: np.ndarray,
    corner_exclusion_fraction: float = CORNER_EXCLUSION_FRACTION,
    px_per_mm: float | None = None,
    geometry: dict | None = None,
) -> dict:
    """Assess all four edges.

    `geometry` is the block from preprocessing.rectify; its per-side residuals
    become the geometric channel. Without it, and without px_per_mm, the
    category falls back to the photometric channel alone and says so.
    """
    lab = cv2.cvtColor(card_image, cv2.COLOR_BGR2LAB).astype(np.float32)
    scale = px_per_mm or (min(card_image.shape[:2]) / 88.0)
    depth_px = int(round(MAX_BORDER_SEARCH_MM * scale))
    sides = (geometry or {}).get("sides", {})

    per_edge: dict[str, dict] = {}
    for name in ("top", "bottom", "left", "right"):
        band = _edge_band(lab, name, corner_exclusion_fraction, depth_px)
        info = _analyze_edge(band, scale)
        info.update(_geometric(sides.get(name), scale))

        photometric = (
            scoring.edge_photometric_penalty(
                info["whitened_fraction"], info["longest_run_fraction"]
            )
            if info.get("measured")
            else None
        )
        geometric = (
            scoring.edge_geometric_penalty(info["max_excursion_mm"], info["roughness_mm"])
            if info.get("geometric_measured")
            else None
        )
        penalties = [p for p in (photometric, geometric) if p is not None]
        if penalties:
            info["score"] = round(scoring.clip_score(10.0 - max(penalties)), 2)
            info["measured"] = True
        else:
            info["score"] = None
            info["measured"] = False
        per_edge[name] = info

    measured = [e["score"] for e in per_edge.values() if e.get("measured")]
    if not measured:
        raise ValueError(
            "No edge could be assessed -- the deskewed card image is too small "
            "or the crop is degenerate."
        )
    raw_score = round(float(np.mean(measured)), 2)

    partial = len(measured) < len(per_edge)
    thin = [n for n, e in per_edge.items() if e.get("reason") == "thin_border"]
    capture_code, too_low_resolution = capture.resolution_limitation(px_per_mm)
    measurements = {
        "per_edge": per_edge,
        "measured_edges": len(measured),
        "thin_border_edges": sorted(thin),
    }

    if too_low_resolution:
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

    limitations: list[str] = []
    confidence = assessment.CONFIDENCE_EDGES
    if partial:
        limitations.append(assessment.EDGES_PARTIAL)
        confidence = assessment.CONFIDENCE_EDGES_PARTIAL
    if thin:
        limitations.append(assessment.EDGES_THIN_BORDER)
        confidence = min(confidence, assessment.CONFIDENCE_EDGES_THIN_BORDER)
    if capture_code is not None:
        limitations.append(capture_code)
        confidence *= assessment.CONFIDENCE_MODEST_RESOLUTION_FACTOR

    measurements["assessment"] = assessment.measured(
        raw_score, confidence, tuple(limitations)
    ).as_dict()

    flags = {}
    if partial or thin:
        parts = []
        if partial:
            unmeasured = sorted(n for n, e in per_edge.items() if not e.get("measured"))
            parts.append(
                "Some edges could not be measured and were left out of this "
                f"score rather than counted as clean: {', '.join(unmeasured)}."
            )
        if thin:
            parts.append(
                "This card's printed border is too narrow to sample a clean "
                f"reference beside the cut on: {', '.join(sorted(thin))}. Those "
                "edges were assessed on shape alone, not discolouration."
            )
        flags = {"lower_confidence": True, "reason": " ".join(parts)}
    return {"category": CATEGORY, "raw_score": raw_score, "measurements": measurements, "flags": flags}
