"""Placing centering lines on a side the pipeline declined to measure.

A placement is a claim by the customer, not a measurement, so it has to be
allowed only where the declined reading still stands on a trustworthy card
outline, scored through the same functions as a measurement, and labelled
everywhere as what it is.
"""

from zgrader.analysis import assessment, centering, scoring


def _declined(*limitations, px_per_mm=10.0):
    return {
        "assessment": {
            "state": "unmeasurable",
            "confidence": 0.0,
            "score_low": None,
            "score_high": None,
            "limitations": list(limitations),
        },
        "card_geometry": {"px_per_mm": px_per_mm},
    }


# --- eligibility --------------------------------------------------------


def test_a_side_with_no_printed_frame_can_be_placed():
    assert centering.placement_eligible(_declined(assessment.CENTERING_NO_FRAME)) is True


def test_a_side_whose_edges_were_not_found_cannot_be_placed():
    """The raster may be mostly desk; lines on it would score a card nobody has seen."""
    measurements = _declined(assessment.CENTERING_NO_FRAME, assessment.GEOMETRY_UNVERIFIED)
    assert centering.placement_eligible(measurements) is False


def test_a_side_declined_for_another_reason_cannot_be_placed():
    assert centering.placement_eligible(_declined(assessment.CAPTURE_TOO_LOW_RESOLUTION)) is False


def test_a_side_without_a_scale_cannot_be_placed():
    measurements = _declined(assessment.CENTERING_NO_FRAME, px_per_mm=0)
    assert centering.placement_eligible(measurements) is False


def test_a_scored_side_is_not_a_placement():
    measured = {
        "assessment": {"state": "measured", "confidence": 0.9, "limitations": []},
        "card_geometry": {"px_per_mm": 10.0},
    }
    assert centering.placement_eligible(measured) is False


def test_nothing_stored_is_not_eligible():
    assert centering.placement_eligible(None) is False


# --- widths ---------------------------------------------------------------


def test_widths_need_all_four_numbers():
    assert centering.widths_from({"left_px": 1, "right_px": 2, "top_px": 3, "bottom_px": 4}) == (1.0, 2.0, 3.0, 4.0)
    assert centering.widths_from({"left_px": 1.0}) is None
    assert centering.widths_from(None) is None
    assert centering.widths_from({"left_px": "1", "right_px": 2, "top_px": 3, "bottom_px": 4}) is None


# --- the constants the endpoint and the page share ------------------------


def test_placement_bounds_are_the_published_ones():
    assert scoring.CENTERING_PLACEMENT_MAX_MM == 8.0
    assert scoring.CENTERING_PLACEMENT_DEFAULT_MM == 3.0


def test_the_placed_code_is_a_registered_limitation():
    assert assessment.CENTERING_CLIENT_PLACED in assessment.ALL_LIMITATION_CODES
    assert assessment.CONFIDENCE_CENTERING_NO_FRAME < assessment.CONFIDENCE_CENTERING_CLIENT_PLACED
    assert assessment.CONFIDENCE_CENTERING_CLIENT_PLACED < assessment.CONFIDENCE_CENTERING_PARTIAL_FRAME


def test_the_placed_code_has_report_copy_in_both_languages():
    from zgrader.reports.strings import LIMITATION_LABELS

    assert "placed by hand" in LIMITATION_LABELS["en"][assessment.CENTERING_CLIENT_PLACED]
    assert LIMITATION_LABELS["es"][assessment.CENTERING_CLIENT_PLACED]
