"""How measurements become the numbers a customer sees.

**Measurement and scoring are separate jobs and this is where the second one
lives.** A detector's business is producing a physical quantity -- millimetres
of border, a saturation deficit, a flagged-area fraction. Turning that into
"7.5 out of 10" is a product judgement about how harshly to treat a defect, and
it belongs in one swappable place rather than buried in the module that did the
measuring.

Every mapping below was previously inline in its detector, which meant the four
categories' scoring philosophies could drift apart silently and nobody could
see them side by side. Collected here, they can be compared, and replaced
wholesale -- by a fitted monotonic mapping, say -- without touching a detector.

**None of it is calibrated.** There is no labelled set of graded outcomes to
fit against, so every constant here is a reasoned starting point. Each is
tagged with what it is actually based on, because "published tolerance" and "a
number that looked about right" deserve very different amounts of trust, and
after a few months nobody remembers which was which.
"""

import numpy as np

# --- Calibration provenance -------------------------------------------------
# Recorded per constant so the difference between an evidenced number and a
# guess survives the people who made them.
#
#   DERIVED  -- follows from a published tolerance or physical fact
#   REASONED -- defensible argument, no measurement behind it
#   ARBITRARY-- a plausible number chosen to get something shipped
# ----------------------------------------------------------------------------

# A card is looked at, bought and graded front-first: a scuffed back rarely
# costs what a scuffed front costs. An unweighted mean let a pristine back
# hide a damaged front by exactly half, which no grading company does.
#
# Front-dominant rather than front-only, because the back still carries real
# signal -- centering in particular is judged on both faces.
FRONT_WEIGHT = 0.7
BACK_WEIGHT = 1.0 - FRONT_WEIGHT


def combine_front_back(front: float | None, back: float | None) -> float | None:
    """Combine a per-side value into the single figure shown to the customer.

    A missing back is not scored as absent-and-therefore-fine: the front value
    stands on its own, which is what a front-only "partial check" submission
    is asking for.

    None means unmeasurable on that side. A side with no score contributes
    nothing rather than a zero, so one measurable side carries the result at
    full weight -- weighting a present value by 0.7 because the other side was
    unreadable would quietly cap it at 7.0. Both unmeasurable gives None: the
    combined figure is unmeasurable too, not perfect and not zero.
    """
    if front is None and back is None:
        return None
    if front is None:
        return round(float(back), 2)
    if back is None:
        return round(float(front), 2)
    return round(FRONT_WEIGHT * float(front) + BACK_WEIGHT * float(back), 2)


def combine_sides_by_name(scores_by_side: dict[str, float]) -> float | None:
    """`combine_front_back` for callers holding a {side_name: value} mapping.

    Returns None when there is nothing to combine. Used by recompute.py, which
    rebuilds side values after a client dismissal and must apply exactly the
    same weighting the pipeline applied originally -- it previously took a
    plain mean of whichever sides happened to be present.
    """
    front = scores_by_side.get("front")
    back = scores_by_side.get("back")
    if front is None and back is None:
        return None
    if front is None:
        # Back-only should not happen (analysis requires a front scan), but
        # weighting a lone value by 0.3 would be nonsense if it ever did.
        return round(float(back), 2)
    return combine_front_back(front, back)


# ---------------------------------------------------------------------------
# Per-category mappings: physical quantity -> 0-10 score.
#
# Each was lifted verbatim from its detector, so behaviour is unchanged by the
# move -- the drift harness is the proof of that, and any future change to
# these numbers should show up there as deliberate per-fixture drift.
# ---------------------------------------------------------------------------

# DERIVED (loosely). Centering is the one category where the companies publish
# something: roughly 55/45 for a Gem Mint 10, 60/40 for a 9, 65/35 for an 8.
# A 50/50 card scores 10 and every 5 percentage points of asymmetry costs a
# point, which puts 55/45 at 9 and 65/35 at 7 -- close to those bands without
# claiming to reproduce any company's actual cutoffs.
CENTERING_POINTS_PER_PCT = 1.0 / 5.0

# --- Corners ---------------------------------------------------------------
#
# DERIVED, from geometry. A factory corner is not a right angle -- it is
# die-cut to a radius of roughly 1.5mm, so a perfect corner is *already*
# missing area relative to the ideal rectangle the card is rectified to. A
# quarter-circle of radius r inset into a square corner leaves r^2(1 - pi/4)
# empty, which at 1.5mm is 0.48mm^2. Without forgiving it every mint card
# would read as damaged.
#
# **What the fixtures do and do not confirm.** They are generated with this
# same 1.5mm radius, so measuring 0.48mm^2 back off them confirms the
# measurement chain end to end -- mask, rectification, inset calibration and
# area arithmetic all agree with the geometry for a known ground truth. That
# is worth having and is asserted in test_corners.py. It says nothing about
# whether 1.5mm is the right number for a real Pokemon card, because the
# fixture radius was set from the same assumption. Only a real card measured
# with calipers settles that.
#
# One constant for every game today. CardDimensionReference is where a
# per-game radius would live once anyone measures one.
NOMINAL_CORNER_RADIUS_MM = 1.5

# REASONED, from the measurement's own resolution. The card mask is binary, so
# its boundary sits a whole number of pixels inside the ideal edge and the
# calibration that removes that bias can only remove whole pixels too. One
# pixel at ~24 px/mm across a 5mm window is 0.21mm^2, and that is what a
# *mint* corner's residual deficit turned out to be -- enough to stop any card
# scoring 10 on corners, which is a claim about cards rather than about the
# measurement.
#
# Deficits below this are therefore not reported as damage. Nothing is gained
# by resolving differences smaller than the noise that produces them, and a
# systematic sag on every clean card is worse than a slightly blunt detector:
# it biases every number downstream in the same direction. The cost is real
# and worth stating -- wear finer than about a half-millimetre nick is now
# invisible here, because it is genuinely indistinguishable from quantisation.
CORNER_AREA_NOISE_FLOOR_MM2 = 0.25

# ARBITRARY. Excess material loss, over and above that factory rounding, that
# drives a corner to zero. 4mm^2 beyond nominal is roughly a 3mm bite out of
# the tip -- unambiguous damage on a card that is 63mm across.
CORNER_EXCESS_AREA_FOR_ZERO_MM2 = 4.0

# ARBITRARY, both. Whitening is now measured in CIELAB against a local
# reference on the same border: a frayed corner gets *lighter* (L up) and
# *less colourful* (chroma down). These are the deltas, in OpenCV's 8-bit Lab
# units, that take a corner to zero on their own.
#
# The previous single HSV-saturation threshold is gone. Saturation conflates
# the two effects and is unstable where value is low, so a dark border and a
# whitened one could produce the same number.
CORNER_LIGHTNESS_RISE_FOR_ZERO = 60.0
CORNER_CHROMA_LOSS_FOR_ZERO = 60.0

# ARBITRARY. How much the worst corner anchors the category, against the mean
# of all four. A plain mean let three clean corners hide one destroyed corner
# by a factor of four, which no grading company does -- corners are graded on
# the worst one, and a card with a single crushed tip is not three-quarters
# mint. Kept below 1.0 so the other three still count for something.
CORNER_WORST_WEIGHT = 0.5

# ARBITRARY, both. A whitened fraction alone can cost 15 points and a single
# contiguous run another 10, so either can zero an edge on its own. The run
# term exists because one 3mm chip matters more than the same pixel count
# scattered as speckle, which is a real grading distinction -- but the specific
# weights are not.
EDGE_WHITENED_FRACTION_WEIGHT = 15.0
EDGE_LONGEST_RUN_WEIGHT = 10.0

# --- Edges, geometric channel ----------------------------------------------
#
# REASONED. These describe how far the cut wanders from the straight line
# fitted through it, in millimetres, and they are the only edge measurement
# that works on a border with no colour to lose.
#
# A 1mm bite out of an edge is unmistakable damage on a 63mm card -- visible
# across a room, and the kind of thing that caps a grade outright. Roughness is
# a standard deviation rather than a single excursion, so it is a much smaller
# quantity: 0.3mm of wander along a whole edge is a chewed edge, where a clean
# factory cut measured on the fixtures sits near zero and a deliberately bad
# capture reaches 0.09mm.
EDGE_NICK_DEPTH_FOR_ZERO_MM = 1.0
EDGE_ROUGHNESS_FOR_ZERO_MM = 0.30

# ARBITRARY. 5% of the card flagged drives surface to zero.
SURFACE_ANOMALY_FRACTION_FOR_ZERO = 0.05


def _clip_score(value: float) -> float:
    return float(np.clip(value, 0.0, 10.0))


def centering_score(worse_side_pct: float) -> float:
    """50/50 -> 10.0, 100/0 -> 0.0, linear in between.

    `worse_side_pct` is the larger share of a ratio, e.g. 58 for a 58/42 split.
    """
    return _clip_score(10.0 - (worse_side_pct - 50.0) * CENTERING_POINTS_PER_PCT)


def nominal_corner_deficit_mm2(radius_mm: float = NOMINAL_CORNER_RADIUS_MM) -> float:
    """Area a *perfect* factory corner is missing from a square corner.

    The card is rectified to its ideal rectangle, so a rounded corner leaves
    real empty area there. This is the amount to forgive before calling
    anything damage.
    """
    return (1.0 - np.pi / 4.0) * radius_mm * radius_mm


def corner_material_penalty(excess_area_mm2: float) -> float:
    """Points lost to material that is missing beyond the factory rounding."""
    return _clip_score(10.0 * excess_area_mm2 / CORNER_EXCESS_AREA_FOR_ZERO_MM2)


def corner_whitening_penalty(lightness_rise: float, chroma_loss: float) -> float:
    """Points lost to a corner having frayed toward bare cardstock.

    Both channels describe the same physical event from different directions,
    so the worse of the two is taken rather than their sum. On real wear they
    move together -- exposed core is lighter *and* less colourful -- and adding
    them would count one defect twice.
    """
    return _clip_score(
        10.0
        * max(
            max(0.0, lightness_rise) / CORNER_LIGHTNESS_RISE_FOR_ZERO,
            max(0.0, chroma_loss) / CORNER_CHROMA_LOSS_FOR_ZERO,
        )
    )


def corner_score(
    excess_area_mm2: float | None, lightness_rise: float, chroma_loss: float
) -> float:
    """One corner, from material loss and whitening together.

    The worse of the two penalties applies, not their sum, for the same reason
    the two whitening channels combine that way: a chipped corner is almost
    always a whitened one, and a card should not be punished twice for a single
    piece of damage. The trade is that a corner which is genuinely both scores
    no worse than its worst aspect -- the first thing to revisit against real
    graded cards.

    `excess_area_mm2` is None when no card mask was available, in which case
    the corner is scored on whitening alone and the category says so.
    """
    whitening = corner_whitening_penalty(lightness_rise, chroma_loss)
    if excess_area_mm2 is None:
        return _clip_score(10.0 - whitening)
    return _clip_score(10.0 - max(corner_material_penalty(excess_area_mm2), whitening))


def corners_category_score(per_corner_scores: list[float]) -> float:
    """Worst-anchored, not a plain mean.

    A mean of four let one destroyed corner cost only a quarter of the
    category. Corners are judged on the worst one, so it carries half the
    weight by itself and the mean of all four carries the rest: 10/10/10/0
    lands at 3.75 rather than 7.5.
    """
    worst = min(per_corner_scores)
    mean = float(np.mean(per_corner_scores))
    return _clip_score(CORNER_WORST_WEIGHT * worst + (1.0 - CORNER_WORST_WEIGHT) * mean)


def clip_score(value: float) -> float:
    """Public alias -- edges builds its score from two penalties and needs to
    clamp the result itself."""
    return _clip_score(value)


def edge_photometric_penalty(whitened_fraction: float, longest_run_fraction: float) -> float:
    """Points lost to an edge having frayed toward bare cardstock.

    Graders weight a single long chip more heavily than the same amount of
    speckle, which is why the run term exists at all rather than area alone.
    """
    return _clip_score(
        whitened_fraction * EDGE_WHITENED_FRACTION_WEIGHT
        + longest_run_fraction * EDGE_LONGEST_RUN_WEIGHT
    )


def edge_geometric_penalty(max_excursion_mm: float, roughness_mm: float) -> float:
    """Points lost to the cut not being straight.

    The worse of the two, not their sum: a deep nick raises the roughness that
    measures it, so adding them would count the same excursion twice.
    """
    return _clip_score(
        10.0
        * max(
            max_excursion_mm / EDGE_NICK_DEPTH_FOR_ZERO_MM,
            roughness_mm / EDGE_ROUGHNESS_FOR_ZERO_MM,
        )
    )


def edge_score(whitened_fraction: float, longest_run_fraction: float) -> float:
    """Photometric-only edge score. Kept because recompute and the tests reach
    for it; the pipeline combines both channels in edges.measure_edges."""
    return _clip_score(
        10.0 - edge_photometric_penalty(whitened_fraction, longest_run_fraction)
    )


def surface_score(anomaly_fraction: float) -> float:
    """Fraction of the card's face flagged as anomalous texture."""
    return _clip_score(10.0 - anomaly_fraction * (10.0 / SURFACE_ANOMALY_FRACTION_FOR_ZERO))
