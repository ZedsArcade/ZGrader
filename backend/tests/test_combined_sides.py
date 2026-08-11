"""What a combined front/back assessment says when one side could not be read.

Found in production, on SUB-00011. The back's corners and edges declined for
low resolution, and the combined rows came back like this:

    combined  corners  raw_score=7.45  state=unmeasurable  confidence=0.0

Both at once: a number, and a claim that no number could be produced. Two
functions disagreed. `combine_front_back` keeps the measurable side's score at
full weight -- deliberately, so a front-only submission scores from the front.
`_combine_assessments` marked the result unmeasurable if *either* side had.

The inconsistency had a sharper edge than the contradiction. A submission with
no back at all returns the front's block unchanged and is reported `measured`,
so uploading a poor back produced a worse outcome than uploading none.
"""

from zgrader.analysis import assessment
from zgrader.analysis.pipeline import _combine_assessments


def _measured(score=8.0, confidence=0.8, limitations=()):
    return assessment.measured(score, confidence, tuple(limitations)).as_dict()


def _declined(limitations=(assessment.CAPTURE_TOO_LOW_RESOLUTION,)):
    return assessment.unmeasurable(tuple(limitations)).as_dict()


def test_one_readable_side_still_produces_a_score():
    """The bug. A real measurement of the front is not nothing."""
    combined = _combine_assessments(_measured(), _declined())

    assert combined["state"] == assessment.MEASURED
    assert combined["confidence"] > 0.0
    assert assessment.COMBINED_SINGLE_SIDE in combined["limitations"]


def test_it_says_which_way_it_is_narrower():
    """A quieter number with no explanation is the thing this codebase keeps
    removing. The reason the reading is narrower has to travel with it."""
    combined = _combine_assessments(_measured(), _declined())

    assert assessment.COMBINED_SINGLE_SIDE in combined["limitations"]
    # The declining side's own reason is kept too -- the operator needs both.
    assert assessment.CAPTURE_TOO_LOW_RESOLUTION in combined["limitations"]


def test_a_single_side_costs_confidence():
    both = _combine_assessments(_measured(confidence=0.8), _measured(confidence=0.8))
    one = _combine_assessments(_measured(confidence=0.8), _declined())

    assert one["confidence"] < both["confidence"], (
        "reading one face should be worth less than reading two"
    )


def test_uploading_a_poor_back_is_not_worse_than_uploading_none():
    """The inconsistency that made the old behaviour indefensible."""
    front_only = _combine_assessments(_measured(), None)
    front_plus_bad_back = _combine_assessments(_measured(), _declined())

    assert front_only["state"] == assessment.MEASURED
    assert front_plus_bad_back["state"] == assessment.MEASURED, (
        "adding an unreadable back turned a measurable result into an unmeasurable one"
    )


def test_a_clean_back_does_not_rescue_an_unreadable_front():
    """The sides are not interchangeable, and this is the guard that caught it.

    A first pass at the fix treated them symmetrically, which would have
    scored a card off its back when the front could not be read. A card back
    is a near-symmetric printed design, almost always well centred and rarely
    handled, so that reading flatters the card on the face nobody buys it for
    -- the same reason the weighting is 70/30 rather than even.
    """
    combined = _combine_assessments(
        _declined((assessment.CENTERING_NO_FRAME,)),
        _measured(score=9.0, confidence=0.9),
    )

    assert combined["state"] == assessment.UNMEASURABLE
    assert combined["confidence"] == 0.0
    assert assessment.CENTERING_NO_FRAME in combined["limitations"]
    # Not a "narrower reading" -- there is no reading of the face that counts.
    assert assessment.COMBINED_SINGLE_SIDE not in combined["limitations"]


def test_both_sides_declining_is_still_unmeasurable():
    """The guard against over-correcting. With nothing readable there is
    nothing to stand on, and the reasons still belong in the record."""
    combined = _combine_assessments(
        _declined((assessment.CENTERING_NO_FRAME,)),
        _declined((assessment.CAPTURE_TOO_LOW_RESOLUTION,)),
    )

    assert combined["state"] == assessment.UNMEASURABLE
    assert combined["confidence"] == 0.0
    assert combined["score_low"] is None and combined["score_high"] is None
    assert assessment.CENTERING_NO_FRAME in combined["limitations"]
    assert assessment.CAPTURE_TOO_LOW_RESOLUTION in combined["limitations"]
    # Not claimed: there is no single side carrying this, there is no side at all.
    assert assessment.COMBINED_SINGLE_SIDE not in combined["limitations"]


def test_two_readable_sides_are_unchanged():
    """The common case must not move. Lowest confidence, union of
    limitations, no single-side marker."""
    combined = _combine_assessments(
        _measured(confidence=0.9, limitations=(assessment.SURFACE_DIFFUSE_LIGHT,)),
        _measured(confidence=0.6, limitations=(assessment.CORNERS_PALE_BORDER,)),
    )

    assert combined["state"] == assessment.MEASURED
    assert combined["confidence"] == 0.6
    assert assessment.COMBINED_SINGLE_SIDE not in combined["limitations"]
    assert assessment.SURFACE_DIFFUSE_LIGHT in combined["limitations"]
    assert assessment.CORNERS_PALE_BORDER in combined["limitations"]


def test_the_interval_comes_only_from_sides_that_had_one():
    """A side with no reading has no bounds to contribute. Treating its
    absence as a wide interval would invent uncertainty rather than report
    it."""
    single = _measured(score=8.0, confidence=0.8)
    combined = _combine_assessments(single, _declined())

    assert combined["score_low"] == single["score_low"]
    assert combined["score_high"] == single["score_high"]


def test_every_limitation_code_it_can_emit_has_copy_in_both_languages():
    """AGENTS.md: adding a code means adding copy in both languages, because a
    limitation nobody wrote words for should not reach a customer."""
    from zgrader.reports.strings import LIMITATION_LABELS

    for language in ("en", "es"):
        assert assessment.COMBINED_SINGLE_SIDE in LIMITATION_LABELS[language], (
            f"{language} has no wording for {assessment.COMBINED_SINGLE_SIDE}"
        )
