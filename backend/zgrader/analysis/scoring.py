"""How measurements become the numbers a customer sees.

This module exists to hold scoring decisions in one place instead of scattered
through the detectors. It starts small -- front/back combination -- and is the
seam the calibration layer grows into: measurement stages emit physical
quantities, this layer maps them to grades.

Nothing here is calibrated against graded outcomes. The weights and mappings
are reasoned starting points, and they are collected here precisely so they
can be replaced wholesale (by a fitted monotonic mapping, say) without
touching a single detector.
"""

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
