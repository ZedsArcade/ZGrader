"""Corner analysis: how much material a corner has lost, and how far it has
frayed toward the white cardstock underneath.

TWO MEASUREMENTS, NOT ONE
-------------------------
Until now this category measured discolouration only, and said so in a
customer-facing caveat: a corner worn blunt but not stained was not penalised
at all. That was not a modelling choice, it was a missing prerequisite.
Measuring material loss needs to know where the corner *should* be, and the
old preprocessing put the corner wherever the card's material happened to end
-- so a chipped corner was traced tight and the damage left the image before
anything looked at it.

`geometry.py` fixed that. Apexes now come from intersecting lines fitted to
the straight parts of each side, so the rectified raster is the card's *ideal*
rectangle and any gap at its corners is material the card should have and does
not. That gap is measurable in mm^2, which is a physical quantity a customer
can check against the card in their hand.

So:

    material loss   area missing beyond the factory corner radius, in mm^2,
                    plus how far the apex itself has been pushed back, in mm
    whitening       lightness up and chroma down against a local reference
                    on the same border

WHY LAB RATHER THAN HSV SATURATION
----------------------------------
Whitening is bare paper showing through: the corner gets *lighter* and *less
colourful*. HSV saturation collapses both into one number and is numerically
unstable where value is low, so a dark border and a genuinely whitened one
could produce the same reading. CIELAB separates them -- L for lightness,
chroma for colourfulness -- and both directions are reported, so the score can
combine them explicitly instead of by accident.

The white-bordered blind spot survives this and is still declared: a border
with no colour has little chroma to lose. Material loss is what now carries
those cards, which is the point of measuring it.

WHY NO ARC FIT
--------------
The plan called for a RANSAC arc fitted to each corner, giving a radius. It is
not here on purpose. The radius and the area deficit are two views of the same
rounding, and the area is both the more direct measurement and the one a
customer can verify. A second correlated number with its own uncalibrated
threshold would add a way to disagree with ourselves, not a way to be more
right. If a distinction between "evenly rounded" and "one sharp bite" turns
out to matter, the apex offset already reported next to the area is the
cheaper way to get at it.
"""

import cv2
import numpy as np

from zgrader.analysis import assessment, capture, scoring
from zgrader.models import AnalysisCategory

CATEGORY = AnalysisCategory.corners

#: Side of the square window examined at each corner, in millimetres. A
#: physical size rather than a fraction of the card: corner damage is a
#: physical thing, and 5mm comfortably contains the ~1.5mm factory radius plus
#: any realistic wear without reaching into artwork.
CORNER_WINDOW_MM = 5.0

#: Depth into the window, as a fraction of it, of the region sampled as the
#: corner tip and of the reference strip it is compared against. The tip is
#: the part that frays; the reference is the same printed border a little
#: further along the edge, which is what makes the comparison local.
_TIP_FRACTION = 0.25
_REFERENCE_START = 0.6
_REFERENCE_WIDTH = 0.15

CORNERS_WHITENING_ONLY_FLAG = {
    "lower_confidence": True,
    "reason": (
        "The card's boundary could not be established for this scan, so corner "
        "material loss was not measured. Corners were assessed for "
        "discolouration only, which means a corner worn blunt but not "
        "discoloured will not be penalised here."
    ),
}


def _window_px(card_image: np.ndarray, px_per_mm: float | None) -> int:
    """Corner window size in pixels.

    Falls back to a fraction of the card when no scale is supplied, so callers
    that only want the whitening diagnostics still work.
    """
    h, w = card_image.shape[:2]
    if px_per_mm is None or px_per_mm <= 0:
        return max(8, int(min(h, w) * 0.12))
    return max(8, min(int(round(CORNER_WINDOW_MM * px_per_mm)), int(min(h, w) * 0.25)))


def corner_crops(
    card_image: np.ndarray, size: int | None = None, corner_fraction: float | None = None
) -> dict[str, np.ndarray]:
    """Corner crops normalized so the card's tip is always at [0, 0].

    The flips are what let one analysis function serve all four corners.
    """
    h, w = card_image.shape[:2]
    if size is None:
        size = max(8, int(min(h, w) * (corner_fraction if corner_fraction else 0.12)))
    size = max(2, min(size, min(h, w)))
    return {
        "top_left": card_image[0:size, 0:size],
        "top_right": np.fliplr(card_image[0:size, w - size : w]),
        "bottom_left": np.flipud(card_image[h - size : h, 0:size]),
        "bottom_right": np.flipud(np.fliplr(card_image[h - size : h, w - size : w])),
    }


#: Fraction of the canonical raster that may be missing from the card mask
#: before the mask is judged not to describe a card at all.
#:
#: The raster *is* the card's ideal rectangle, so a sound mask fills essentially
#: all of it. Measured across 29 real photographs the separation is stark:
#: every trustworthy corner reading came from a mask 99.85-99.89% filled, while
#: the unreliable ones were missing 2% to 56%. Those were not cards with
#: material missing -- they were photographs where thresholding caught the desk,
#: a shadow or a glare bloom, and corners then measured 24mm^2 of "loss" against
#: a boundary that was not the card's.
#:
#: 1% sits an order of magnitude above the sound cases and well below the
#: failures. For scale, genuine damage is far smaller still: a 2.5mm corner chip
#: is about 6mm^2, or 0.11% of a card, so real wear never approaches this.
#:
#: The consequence of tripping it is *not* a bad score. Material loss becomes
#: unmeasurable and the category falls back to whitening alone, declaring
#: CORNERS_WHITENING_ONLY -- the same honest degradation used when no mask is
#: supplied at all. A wrong boundary must not be allowed to produce a confident
#: number, which is what it was doing: the same card scored 0.00 in one
#: photograph and 9.52 in another.
MAX_MASK_MISSING_FRACTION = 0.01


#: Distance from the apex, in millimetres, beyond which the card's boundary is
#: straight edge rather than corner. Used to calibrate the mask's own boundary
#: offset -- see _edge_inset_px. Comfortably outside the ~1.5mm factory radius.
_STRAIGHT_EDGE_START_MM = 3.0


def _edge_inset_px(mask_crop: np.ndarray, px_per_mm: float) -> tuple[int, int]:
    """How far inside the ideal rectangle the mask's boundary actually sits,
    measured on the straight parts of the two edges meeting at this corner.

    Without this the measurement is badly wrong, and wrong in a way that looks
    plausible. The mask comes from a threshold and lands about a pixel inside
    the sub-pixel line fit the raster's edges were built from, so every window
    accumulates a sliver of "missing" material along its two straight sides.
    Measured on the fixtures, the deficit at a *mint* corner grew linearly with
    the window -- 0.61mm^2 at 2.5mm, 0.82 at 5mm, 1.24 at 10mm -- which is not
    a property of any corner. It is two edges times one pixel.

    The median is taken over the straight section only, and it is a median
    precisely so a nick in that stretch of edge moves nothing.

    It can only remove whole pixels, because the mask is binary and has no
    sub-pixel boundary to offer. What survives is about 0.2mm^2 at 24 px/mm on
    a 5mm window -- visible as a difference between a card's left and right
    corners on an axis-aligned synthetic, and largely self-cancelling on a real
    card whose edge crosses pixel rows at an angle. Bounded by a test rather
    than left to drift.
    """
    size = mask_crop.shape[0]
    start = min(size - 1, int(round(_STRAIGHT_EDGE_START_MM * px_per_mm)))
    if start >= size - 1:
        return 0, 0

    def _first_material(lines: np.ndarray) -> int:
        # A line with no material at all would report 0 from argmax, which
        # reads as "no inset" -- the opposite of the truth -- so those are
        # dropped rather than counted.
        present = lines.any(axis=1)
        if not present.any():
            return 0
        return int(np.median(np.argmax(lines[present], axis=1)))

    rows_inset = _first_material(mask_crop[start:, :] != 0)
    cols_inset = _first_material((mask_crop[:, start:] != 0).T)
    return rows_inset, cols_inset


def _material_loss(mask_crop: np.ndarray, px_per_mm: float) -> dict:
    """How much of the ideal corner is not card, and how blunt the tip is.

    `mask_crop` is oriented like every other corner crop, so [0, 0] is the
    ideal apex. Non-zero means card material.
    """
    # Only the region the card is genuinely expected to fill counts. The strip
    # outside the calibrated boundary offset is an artefact of how the mask was
    # thresholded, not material the card is missing.
    inset_r, inset_c = _edge_inset_px(mask_crop, px_per_mm)
    expected = np.zeros(mask_crop.shape, dtype=bool)
    expected[inset_r:, inset_c:] = True

    missing = (mask_crop == 0) & expected
    area_px = float(np.count_nonzero(missing))
    area_mm2 = area_px / (px_per_mm * px_per_mm)

    nominal = scoring.nominal_corner_deficit_mm2()
    # Two things are forgiven: the factory rounding, which is real card
    # geometry, and a noise floor, which is this measurement's own resolution.
    # Both are reported so the raw area stays inspectable.
    excess_mm2 = max(0.0, area_mm2 - nominal - scoring.CORNER_AREA_NOISE_FLOOR_MM2)

    # How far back the tip has been pushed: distance from the ideal apex to the
    # nearest surviving material. Reported alongside the area because the two
    # separate a corner evenly rounded from one with a single deep bite, which
    # the area alone cannot.
    present = np.argwhere(mask_crop != 0)
    if len(present):
        apex_offset_mm = float(np.min(np.hypot(present[:, 0], present[:, 1]))) / px_per_mm
    else:
        # Nothing in the whole window is card. Physically that is not a worn
        # corner, it is a detection failure or a crop landing off the card --
        # so report the window's own size rather than an unbounded number.
        apex_offset_mm = mask_crop.shape[0] / px_per_mm

    return {
        "missing_area_mm2": round(area_mm2, 3),
        "excess_area_mm2": round(excess_mm2, 3),
        "apex_offset_mm": round(apex_offset_mm, 3),
        "nominal_area_mm2": round(nominal, 3),
    }


#: How far inside the card's boundary to pull back before sampling colour, in
#: millimetres. A sensor integrates over a pixel, so the pixels straddling the
#: cut are blends of card and whatever is behind it. They are inside the mask
#: and they are not card colour: against dark backing they lose chroma, which
#: is precisely the signature of whitening, so an ordinary rounded corner read
#: as badly frayed. Small enough not to miss real tip wear, which extends far
#: further than this.
_COLOUR_SAMPLE_INSET_MM = 0.2


def _whitening(
    crop: np.ndarray, mask_crop: np.ndarray | None, px_per_mm: float | None = None
) -> dict:
    """Lightness rise and chroma loss at the tip, against a local reference.

    Where a mask is available, non-card pixels are excluded from the tip
    sample. Without that, a chipped corner's exposed scanner backing lands in
    the very region being measured -- and dark backing reads as the opposite of
    whitening, so the worst corners would look the cleanest.
    """
    size = crop.shape[0]
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB).astype(np.float32)
    lightness = lab[:, :, 0]
    # OpenCV stores a* and b* biased by 128 in 8-bit; chroma is the distance
    # from the neutral axis, so the bias has to come off first.
    chroma = np.hypot(lab[:, :, 1] - 128.0, lab[:, :, 2] - 128.0)

    tip = max(3, int(size * _TIP_FRACTION))
    tip_slice = (slice(0, tip), slice(0, tip))
    ref_slice = (
        slice(int(size * _REFERENCE_START), size),
        slice(0, max(2, int(size * _REFERENCE_WIDTH))),
    )

    tip_valid = np.ones((tip, tip), dtype=bool)
    ref_valid = np.ones_like(lightness[ref_slice], dtype=bool)
    if mask_crop is not None:
        sampling_mask = mask_crop
        if px_per_mm:
            inset = max(1, int(round(_COLOUR_SAMPLE_INSET_MM * px_per_mm)))
            sampling_mask = cv2.erode(
                mask_crop, np.ones((2 * inset + 1, 2 * inset + 1), np.uint8)
            )
        tip_valid = sampling_mask[tip_slice] != 0
        # The reference needs the same treatment as the tip, and for a sharper
        # reason: it is a narrow strip hard against the cut, so a larger share
        # of it is boundary blend. Left unmasked those darker pixels drag the
        # reference lightness down, the tip reads as brighter than its own
        # border by comparison, and a clean white-bordered card is reported as
        # whitened -- measured at 1.1 points on the white-bordered fixture
        # before this line existed.
        ref_valid = sampling_mask[ref_slice] != 0
        if not ref_valid.any():
            ref_valid = np.ones_like(ref_valid)
    if not tip_valid.any():
        # Every pixel of the tip is missing material. There is no card left
        # there to have a colour, so whitening is not measurable at this
        # corner -- the material-loss channel is already saying everything
        # there is to say about it.
        return {
            "lightness_rise": 0.0,
            "chroma_loss": 0.0,
            "tip_lightness": None,
            "reference_chroma": round(float(np.mean(chroma[ref_slice][ref_valid])), 1),
            "whitening_measured": False,
        }

    tip_lightness = float(np.mean(lightness[tip_slice][tip_valid]))
    tip_chroma = float(np.mean(chroma[tip_slice][tip_valid]))
    ref_lightness = float(np.mean(lightness[ref_slice][ref_valid]))
    ref_chroma = float(np.mean(chroma[ref_slice][ref_valid]))

    return {
        "lightness_rise": round(tip_lightness - ref_lightness, 1),
        "chroma_loss": round(ref_chroma - tip_chroma, 1),
        "tip_lightness": round(tip_lightness, 1),
        "reference_chroma": round(ref_chroma, 1),
        "whitening_measured": True,
    }


def measure_corners(
    card_image: np.ndarray,
    corner_fraction: float | None = None,
    px_per_mm: float | None = None,
    mask: np.ndarray | None = None,
) -> dict:
    """Assess all four corners.

    `mask` is the canonical card mask from preprocessing.rectify -- the same
    raster as `card_image`, non-zero where there is card. Without it material
    loss cannot be measured and the category degrades to whitening only,
    declaring that in its limitations rather than quietly scoring less.
    """
    size = _window_px(card_image, px_per_mm)
    crops = corner_crops(card_image, size=size, corner_fraction=corner_fraction)
    mask_usable = mask is not None and mask.shape[:2] == card_image.shape[:2]
    mask_missing = float(np.mean(mask == 0)) if mask_usable else 1.0
    if mask_usable and mask_missing > MAX_MASK_MISSING_FRACTION:
        # The mask is not describing a card. See MAX_MASK_MISSING_FRACTION.
        mask_usable = False

    mask_crops = (
        corner_crops(mask, size=size, corner_fraction=corner_fraction) if mask_usable else {}
    )
    can_measure_material = bool(mask_crops) and px_per_mm is not None and px_per_mm > 0

    per_corner: dict[str, dict] = {}
    for name, crop in crops.items():
        mask_crop = mask_crops.get(name)
        info = dict(_whitening(crop, mask_crop, px_per_mm))
        if can_measure_material:
            info.update(_material_loss(mask_crop, px_per_mm))
        excess = info.get("excess_area_mm2") if can_measure_material else None
        info["combined_score"] = round(
            scoring.corner_score(excess, info["lightness_rise"], info["chroma_loss"]), 2
        )
        info["material_measured"] = can_measure_material
        per_corner[name] = info

    scores = [c["combined_score"] for c in per_corner.values()]
    raw_score = round(scoring.corners_category_score(scores), 2)
    worst_corner = min(per_corner, key=lambda k: per_corner[k]["combined_score"])

    # A pale border has almost no chroma to lose, so the whitening channel is
    # weak there. This used to be the category's central blind spot; it is now
    # a caveat on one of two channels, because material loss does not care what
    # colour the border is.
    mean_reference_chroma = float(np.mean([c["reference_chroma"] for c in per_corner.values()]))
    pale = mean_reference_chroma < assessment.PALE_BORDER_CHROMA

    capture_code, too_low_resolution = capture.resolution_limitation(px_per_mm)

    measurements = {
        "per_corner": per_corner,
        "worst_corner": worst_corner,
        # Both the physical size (for a customer) and the pixel size (so the
        # annotator and the region boxes draw exactly the window that was
        # measured -- they each used to derive their own from a fraction, which
        # is how an overlay silently stops matching its measurement).
        "corner_window_mm": round(size / px_per_mm, 2) if px_per_mm else None,
        "corner_window_px": size,
        "mean_reference_chroma": round(mean_reference_chroma, 1),
        "material_measured": can_measure_material,
        "mask_missing_fraction": round(mask_missing, 5),
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
                    "The card occupies too few pixels in this photo for corner "
                    "wear to be visible at all, so corners were not scored. A "
                    "closer or higher-resolution photo would let this be "
                    "measured."
                ),
            },
        }

    limitations: list[str] = []
    confidence = assessment.CONFIDENCE_CORNERS
    if not can_measure_material:
        limitations.append(assessment.CORNERS_WHITENING_ONLY)
        confidence = assessment.CONFIDENCE_CORNERS_WHITENING_ONLY
    if pale:
        limitations.append(assessment.CORNERS_PALE_BORDER)
        # A pale border costs far less than it used to. It disables one of two
        # channels now rather than the only one, so the confidence floor for
        # these cards is set by whether material loss was measurable.
        confidence = min(
            confidence,
            assessment.CONFIDENCE_CORNERS_PALE_BORDER
            if not can_measure_material
            else assessment.CONFIDENCE_CORNERS_PALE_BORDER_WITH_MATERIAL,
        )
    if capture_code is not None:
        limitations.append(capture_code)
        confidence *= assessment.CONFIDENCE_MODEST_RESOLUTION_FACTOR

    measurements["assessment"] = assessment.measured(
        raw_score, confidence, tuple(limitations)
    ).as_dict()
    flags = dict(CORNERS_WHITENING_ONLY_FLAG) if not can_measure_material else {}
    return {
        "category": CATEGORY,
        "raw_score": raw_score,
        "measurements": measurements,
        "flags": flags,
    }
