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

from zgrader.analysis import assessment, border, geometry, scoring
from zgrader.models import AnalysisCategory

CATEGORY = AnalysisCategory.centering

# A real printed border sits at nearly the same depth on every sample line
# down a side, so the spread (std) of the per-line edge positions is tiny
# relative to the search window. Holo/full-art surfaces with no clean
# border scatter the argmax edge at random depths, giving a large spread.
# If any side's spread exceeds this fraction of its search depth, the
# centering result is marked lower_confidence.
_MAX_BORDER_SPREAD_FRACTION = 0.15

# A single scattered side is not a borderless card -- it is one noisy edge on a
# card that visibly has a frame, and declining on it withholds a measurement we
# can actually make. Measured across the fixture set: cards with a real printed
# border sit at 0.00-0.15 on every side with at most one marginal outlier,
# while genuinely unmeasurable ones (full-art foil, a bordered foil whose holo
# scatters the edge, the worst-case capture) scatter on *all four* at 0.22-0.35.
#
# So two independent ways to conclude there is no frame worth measuring:
_MIN_SCATTERED_SIDES = 2
# ...or one side so scattered that its reading is meaningless regardless of the
# others. The synthetic full-art fixture lands at 0.42 on the side crossing its
# artwork while the uniform sides read a consistent but meaningless depth --
# without this it would be scored on the strength of three sides that found
# nothing at all.
_SEVERE_BORDER_SPREAD_FRACTION = 0.35

CENTERING_LOW_CONFIDENCE_FLAG = {
    "lower_confidence": True,
    "reason": (
        "No clear printed border was found on one or more sides -- common on "
        "full-art / holo cards where the artwork bleeds to the edge and the "
        "whole surface is high-contrast. The centering split is a best-effort "
        "estimate here and may not be reliable."
    ),
}


def _first_strong_edge(strip: np.ndarray, skip_px: int = 3) -> float:
    """Index of the strongest gradient point in `strip`, skipping the first
    `skip_px` samples (the physical cut edge itself, not the printed
    border)."""
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
) -> tuple[float, float]:
    """Returns (median_border_width_px, spread_fraction) for one side, where
    spread_fraction is the std of the per-line edge positions divided by the
    search depth -- small means a consistent real border, large means the
    edge was scattered noise (see _MAX_BORDER_SPREAD_FRACTION)."""
    h, w = edge_map.shape
    widths: list[float] = []
    if side in ("left", "right"):
        search_depth = max(4, int(w * search_fraction))
        margin = max(1, int(h * corner_margin_fraction))
        samples = np.linspace(margin, max(margin, h - margin - 1), num_samples).astype(int)
        for r in samples:
            strip = (
                edge_map[r, 0:search_depth]
                if side == "left"
                else edge_map[r, w - search_depth : w][::-1]
            )
            widths.append(_first_strong_edge(strip))
    else:
        search_depth = max(4, int(h * search_fraction))
        margin = max(1, int(w * corner_margin_fraction))
        samples = np.linspace(margin, max(margin, w - margin - 1), num_samples).astype(int)
        for c in samples:
            strip = (
                edge_map[0:search_depth, c]
                if side == "top"
                else edge_map[h - search_depth : h, c][::-1]
            )
            widths.append(_first_strong_edge(strip))

    spread_fraction = float(np.std(widths) / max(1, search_depth))
    return float(np.median(widths)), spread_fraction


def ratios_from_widths(
    left: float,
    right: float,
    top: float,
    bottom: float,
    have_lr: bool = True,
    have_tb: bool = True,
) -> dict:
    """The two centering ratios and the worse side, from four border widths.

    Extracted so `measure_centering` and the client-adjustment recompute share
    one definition of what a set of border widths means. They used to be the
    same arithmetic written twice, which is the drift `analysis/scoring.py`
    exists to prevent and which has already bitten `recompute.py` twice.

    A ratio needs *both* of its sides, and `have_lr`/`have_tb` say whether it
    has them. This is not defensive tidying: with one side missing, its width
    defaulted to zero and the pair read as a 100/0 split -- a catastrophic
    centering score manufactured out of a measurement that did not happen. An
    axis with a side missing contributes nothing instead; if that leaves no
    axis at all, `worse_side_pct` falls back to 50.0 and the caller decides
    whether a reading exists.

    The client-adjustment path always supplies all four, so both axes count.
    """

    def _split(a: float, b: float, have: bool) -> list[float] | None:
        if not have or a + b <= 0:
            return None
        return [round(100 * a / (a + b), 1), round(100 * b / (a + b), 1)]

    lr_split = _split(left, right, have_lr)
    tb_split = _split(top, bottom, have_tb)
    available = [s for s in (lr_split, tb_split) if s is not None]
    return {
        "lr_ratio": lr_split,
        "tb_ratio": tb_split,
        "measured_axes": len(available),
        "worse_side_pct": max((max(s) for s in available), default=50.0),
    }


def score_from_worse_pct(worse_pct: float) -> float:
    """Thin delegate to the scoring layer.

    The mapping itself lives in analysis/scoring.py: measuring a border and
    deciding what a given asymmetry is worth are separate jobs, and only the
    first belongs here. Kept as a name because recompute.py and the tests call
    it, and re-deriving the same score in two places is how they drift apart.
    """
    return scoring.centering_score(worse_pct)


# Backwards-compatible alias for the pre-existing private name.
_score_from_worse_pct = score_from_worse_pct

# --- Fitting the inner frame -------------------------------------------------

#: Fraction of an edge's length that must yield a transition before the side is
#: considered to have a printed border at all. A full-art card finds one at
#: almost no position; a bordered card finds one nearly everywhere.
MIN_BORDER_COVERAGE = 0.6

#: How closely the per-position transitions must sit to a straight line, in
#: millimetres, for the fit to be trusted for tilt as well as width.
#:
#: Measured: a clean printed frame fits to 0.000mm on every side of every
#: bordered fixture. Foil does not -- `foil_bordered` fits to 0.55-1.74mm,
#: because a holo pattern puts colour variation exactly where the transition
#: search is looking and individual positions land on different modes of it.
#: 0.25mm sits an order of magnitude above the clean case and well below the
#: textured one.
#:
#: A card that fails this is *not* refused. Its width falls back to the
#: whole-edge median profile below, which is the robust estimator and is the
#: one edges.py uses. What is lost is the tilt measurement, which genuinely
#: cannot be read off a scattered fit.
MAX_FRAME_RESIDUAL_MM = 0.25

#: Inlier distance for the frame fit, in pixels. A printed edge is sharp; this
#: only has to absorb the pixel quantisation of the transition search.
_FRAME_INLIER_PX = 2.5

#: Narrowest detected frame that counts as a frame at all, in millimetres.
#:
#: The transition search begins 0.6mm in, so a "border" found in the next
#: fraction of a millimetre means the colour was never stable -- there was
#: nothing to sample. This is the case a consistency test alone cannot catch,
#: and it is worth spelling out why: on uniform noise every position finds a
#: transition immediately, so the depths are all equal and fit a straight line
#: *perfectly*. A razor-sharp frame 0.6mm from the cut is not a frame, it is
#: the absence of one, and the residual test reads it as the cleanest possible
#: measurement.
#:
#: Measured: real borders across the fixture set run 2.6-7.3mm; the spurious
#: frames found on `full_art_foil` and on noise sit at 0.65-0.73mm.
MIN_BORDER_WIDTH_MM = 1.0

#: Window, in millimetres, of the rolling median applied to the per-position
#: depths before fitting.
#:
#: Foil is why. A holo pattern puts local colour variation right where the
#: transition search is looking, so individual positions report the frame a few
#: pixels early or late -- speckle around a correct trend. Measured on
#: `foil_bordered` the fitted widths were right to the hundredth of a
#: millimetre (they match what edges.py independently measured) while only
#: 36-46% of positions agreed on the line, which the consensus test then read
#: as "no frame here". A frame is a smooth line, so smoothing before fitting
#: removes the speckle without touching the trend.
#:
#: It deliberately does not rescue a card that has no frame: `full_art_foil`
#: finds a spurious transition at a *different* depth at every position, and a
#: median over half a millimetre of neighbours does not turn that into a line.
_DEPTH_SMOOTHING_MM = 0.5


def _rolling_median(values: np.ndarray, window: int) -> np.ndarray:
    """Median over a sliding window, edges padded by repetition."""
    if window < 3 or len(values) < window:
        return values
    if window % 2 == 0:
        window += 1
    half = window // 2
    padded = np.pad(values, half, mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(padded, window)
    return np.median(windows, axis=1)

#: Handed to corners.py, matching edges.
_CORNER_EXCLUSION = 0.12


def _fit_side(band: np.ndarray, px_per_mm: float) -> dict:
    """Border width and tilt for one side, from a line fitted to its inner
    frame.

    The previous version took the strongest gradient on each of twenty
    scanlines and reported their median. Two things were wrong with that. The
    median discards the one thing a set of per-position depths can tell you
    that a single number cannot -- whether the border runs *parallel* to the
    cut -- and a gradient peak finds any strong edge, not specifically the
    border, so card text or a bright element of artwork could win it.

    Fitting a line instead gives the width at the middle of the side, the rate
    at which that width changes along the side, and a consensus figure saying
    whether there was a frame there at all.
    """
    depths = border.transition_depths(band, px_per_mm)
    length = len(depths)
    if length < 8:
        return {"measured": False, "coverage": 0.0}

    valid = ~np.isnan(depths)
    coverage = float(valid.mean())
    if valid.sum() < 8 or coverage < MIN_BORDER_COVERAGE:
        return {"measured": False, "coverage": round(coverage, 3)}

    positions = np.nonzero(valid)[0].astype(np.float64)
    found = _rolling_median(
        depths[valid], max(3, int(round(_DEPTH_SMOOTHING_MM * px_per_mm)))
    )
    points = np.column_stack([positions, found])
    normal, offset, mask = geometry.fit_line_ransac(points, inlier_px=_FRAME_INLIER_PX)
    residual_mm = float(np.median(np.abs(points @ normal - offset))) / px_per_mm

    # normal . (position, depth) == offset, so depth as a function of position
    # is (offset - n0*position) / n1. A vanishing n1 would mean the frame runs
    # perpendicular to the edge, which is not a frame.
    fitted = abs(normal[1]) > 1e-6 and residual_mm <= MAX_FRAME_RESIDUAL_MM
    if fitted and float(np.median(found)) / px_per_mm < MIN_BORDER_WIDTH_MM:
        # Consistent, and consistently meaningless. See MIN_BORDER_WIDTH_MM.
        return {
            "measured": False,
            "coverage": round(coverage, 3),
            "residual_mm": round(residual_mm, 3),
        }

    if fitted:
        def depth_at(position: float) -> float:
            return float((offset - normal[0] * position) / normal[1])

        # A fitted frame has to exist along the *whole* side. If the line puts
        # the border narrower than the minimum at either end, it is not
        # describing a frame -- and the difference between the ends, which is
        # the tilt, is then an artefact rather than a diamond cut.
        #
        # This matters because tilt is scored. Real photographs produced tilts
        # of 12.4mm and 14.3mm on a 63mm card, which is not a miscut, it is the
        # border detector landing at very different depths at the two ends of a
        # side. Both scored a confident 0.00. On 5_AngleShot the fit implied a
        # border 0.23mm wide at one end and 14.5mm at the other.
        #
        # No new threshold is needed: the frame must simply still be a frame at
        # both ends. The genuine diamond-cut fixture passes comfortably -- a
        # 3.8mm border with 0.88mm of tilt runs 3.36mm to 4.24mm -- so this
        # bounds the artefact without blunting the measurement it protects.
        ends = (depth_at(0.0), depth_at(length - 1.0))
        if min(ends) < MIN_BORDER_WIDTH_MM * px_per_mm:
            fitted = False

    if fitted:
        width_px = depth_at(length / 2.0)
        tilt_px = depth_at(length - 1.0) - depth_at(0.0)
        return {
            "measured": True,
            "fitted": True,
            "coverage": round(coverage, 3),
            "inlier_fraction": round(float(mask.mean()), 3),
            "residual_mm": round(residual_mm, 3),
            "width_px": max(0.0, width_px),
            "tilt_px": tilt_px,
            "tilt_mm": round(tilt_px / px_per_mm, 3),
        }

    # The per-position transitions did not form a line -- foil, most often.
    # Fall back to the whole-edge median profile, which is the robust estimator
    # and the one edges.py uses for its reference. It gives a width and nothing
    # else: tilt is a statement about how the frame runs along the side, and
    # this reading has no per-position information left in it.
    #
    # Refusing outright would be the wrong call. A holo card has a perfectly
    # real printed border and the median profile finds it; declining to measure
    # something measurable is as much a failure as measuring it badly.
    median_depth = border.transition_depth_px(band, px_per_mm)
    if median_depth is None or median_depth / px_per_mm < MIN_BORDER_WIDTH_MM:
        return {
            "measured": False,
            "coverage": round(coverage, 3),
            "residual_mm": round(residual_mm, 3),
        }
    return {
        "measured": True,
        "fitted": False,
        "coverage": round(coverage, 3),
        "inlier_fraction": round(float(mask.mean()), 3),
        "residual_mm": round(residual_mm, 3),
        "width_px": float(median_depth),
        "tilt_px": 0.0,
        "tilt_mm": 0.0,
    }


def measure_centering(card_image: np.ndarray, px_per_mm: float) -> dict:
    lab = cv2.cvtColor(card_image, cv2.COLOR_BGR2LAB).astype(np.float32)
    depth_px = int(round(border.MAX_SEARCH_MM * px_per_mm))

    sides = {
        name: _fit_side(border.edge_band(lab, name, _CORNER_EXCLUSION, depth_px), px_per_mm)
        for name in ("left", "right", "top", "bottom")
    }

    widths = {n: s.get("width_px", 0.0) for n, s in sides.items()}
    left, right = widths["left"], widths["right"]
    top, bottom = widths["top"], widths["bottom"]

    # A ratio needs *both* of its sides. This is not defensive tidying: with
    # one side missing, its width defaulted to zero and the pair read as a
    # 100/0 split -- a catastrophic centering score manufactured out of a
    # measurement that did not happen. On `capture_worst_case` that produced a
    # confident 0.0 on a card whose other three borders were fine.
    #
    # An axis with a side missing contributes nothing instead. If that leaves
    # no axis at all, there is no centering reading to give.
    ratios = ratios_from_widths(
        left,
        right,
        top,
        bottom,
        have_lr=bool(sides["left"].get("measured") and sides["right"].get("measured")),
        have_tb=bool(sides["top"].get("measured") and sides["bottom"].get("measured")),
    )
    lr_split = ratios["lr_ratio"]
    tb_split = ratios["tb_ratio"]
    available = [s for s in (lr_split, tb_split) if s is not None]
    worse_side_pct = ratios["worse_side_pct"]
    # The card's worst tilt, which is what a diamond cut looks like from here.
    # Reported in millimetres because that is the form a customer can check
    # with a ruler against the card's own border.
    tilt_mm = max((abs(s.get("tilt_mm", 0.0)) for s in sides.values()), default=0.0)

    reading = {
        "left_px": round(left, 1),
        "right_px": round(right, 1),
        "top_px": round(top, 1),
        "bottom_px": round(bottom, 1),
        "left_mm": round(left / px_per_mm, 2),
        "right_mm": round(right / px_per_mm, 2),
        "top_mm": round(top / px_per_mm, 2),
        "bottom_mm": round(bottom / px_per_mm, 2),
        "lr_ratio": lr_split if lr_split is not None else [50.0, 50.0],
        "tb_ratio": tb_split if tb_split is not None else [50.0, 50.0],
        "measured_axes": len(available),
        "worse_side_pct": round(worse_side_pct, 1),
        "tilt_mm": round(tilt_mm, 3),
        "per_side": {
            n: {k: v for k, v in s.items() if k not in ("width_px", "tilt_px")}
            for n, s in sides.items()
        },
    }

    # No frame is now a fact about the fit rather than a heuristic about
    # scatter: either too few positions along a side produced a transition at
    # all, or too few of those agreed on a straight line. Both are direct
    # statements that there was nothing frame-shaped there, where the old
    # spread test was an indirect proxy that needed two thresholds to behave.
    unmeasured = [n for n, s in sides.items() if not s.get("measured")]
    # No complete axis means no ratio, whatever the individual sides managed.
    # A side whose width came from the median profile rather than a fitted line
    # is a weaker reading, not a missing one: the width is real, the tilt is
    # not available. Two or more unmeasurable sides means there was no frame.
    unfitted = [n for n, s in sides.items() if s.get("measured") and not s.get("fitted")]
    no_frame = not available or len(unmeasured) >= 2

    flags = dict(CENTERING_LOW_CONFIDENCE_FLAG) if no_frame else {}

    if no_frame:
        # Full-art, or artwork bleeding to the cut. Every number above is then
        # a reading of artwork, so this declines to score rather than
        # publishing a plausible-looking ratio.
        #
        # The reading is kept as `indicative_estimate`, deliberately NOT under
        # the keys a measurement lives at. rules_engine reads `worse_side_pct`
        # off the top level and skips the rule when it is absent; that skip is
        # the correct behaviour here, and hoisting the estimate into that key
        # would silently resurrect it as five company verdicts on a card
        # nothing could measure.
        return {
            "category": CATEGORY,
            "raw_score": None,
            "measurements": {
                "indicative_estimate": reading,
                "assessment": assessment.unmeasurable(
                    (assessment.CENTERING_NO_FRAME,)
                ).as_dict(),
            },
            "flags": flags,
        }

    raw_score = round(scoring.centering_score(worse_side_pct, tilt_mm), 2)
    limitations: list[str] = []
    confidence = assessment.CONFIDENCE_CENTERING_CLEAN_FRAME
    if unmeasured or unfitted:
        limitations.append(assessment.CENTERING_PARTIAL_FRAME)
        confidence = assessment.CONFIDENCE_CENTERING_PARTIAL_FRAME
    reading["assessment"] = assessment.measured(
        raw_score, confidence, tuple(limitations)
    ).as_dict()
    return {
        "category": CATEGORY,
        "raw_score": raw_score,
        "measurements": reading,
        "flags": flags,
    }
