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


def combine_front_back(front: float, back: float | None) -> float:
    """Combine a per-side value into the single figure shown to the customer.

    A missing back is not scored as absent-and-therefore-fine: the front value
    stands on its own, which is what a front-only "partial check" submission
    is asking for.
    """
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

# ARBITRARY. A saturation deficit of 80 (out of 255) takes a corner to zero.
# Nothing measured this; it was chosen so the synthetic whitened corner scored
# badly enough to be visible.
CORNER_SATURATION_DEFICIT_FOR_ZERO = 80.0

# ARBITRARY, both. A whitened fraction alone can cost 15 points and a single
# contiguous run another 10, so either can zero an edge on its own. The run
# term exists because one 3mm chip matters more than the same pixel count
# scattered as speckle, which is a real grading distinction -- but the specific
# weights are not.
EDGE_WHITENED_FRACTION_WEIGHT = 15.0
EDGE_LONGEST_RUN_WEIGHT = 10.0

# ARBITRARY. 5% of the card flagged drives surface to zero.
SURFACE_ANOMALY_FRACTION_FOR_ZERO = 0.05


def _clip_score(value: float) -> float:
    return float(np.clip(value, 0.0, 10.0))


def centering_score(worse_side_pct: float) -> float:
    """50/50 -> 10.0, 100/0 -> 0.0, linear in between.

    `worse_side_pct` is the larger share of a ratio, e.g. 58 for a 58/42 split.
    """
    return _clip_score(10.0 - (worse_side_pct - 50.0) * CENTERING_POINTS_PER_PCT)


def corner_whitening_score(saturation_deficit: float) -> float:
    """How much colour a corner has lost relative to card a little further in.

    The deficit is in HSV saturation units (0-255); zero means the tip is as
    saturated as its reference and nothing has frayed toward bare cardstock.
    """
    return _clip_score(
        10.0 - (10.0 * saturation_deficit / CORNER_SATURATION_DEFICIT_FOR_ZERO)
    )


def edge_score(whitened_fraction: float, longest_run_fraction: float) -> float:
    """Both how much of an edge is whitened and how concentrated it is.

    Graders weight a single long chip more heavily than the same amount of
    speckle, which is why the run term exists at all rather than area alone.
    """
    return _clip_score(
        10.0
        - whitened_fraction * EDGE_WHITENED_FRACTION_WEIGHT
        - longest_run_fraction * EDGE_LONGEST_RUN_WEIGHT
    )


def surface_score(anomaly_fraction: float) -> float:
    """Fraction of the card's face flagged as anomalous texture."""
    return _clip_score(10.0 - anomaly_fraction * (10.0 / SURFACE_ANOMALY_FRACTION_FOR_ZERO))
