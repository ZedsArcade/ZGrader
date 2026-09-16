"""Placing centering lines on a side the pipeline declined to measure.

A placement is a claim by the customer, not a measurement, so it has to be
allowed only where the declined reading still stands on a trustworthy card
outline, scored through the same functions as a measurement, and labelled
everywhere as what it is.
"""

import copy
import hashlib

import cv2

from zgrader.analysis import assessment, centering, pipeline, recompute, scoring
from zgrader.auth.security import hash_password
from zgrader.models import (
    AnalysisCategory,
    AnalysisResult,
    AnalysisSide,
    Card,
    GradingCompanyComparison,
    ScanImage,
    ScanSide,
    Submission,
    SubmissionLanguage,
    SubmissionStatus,
    User,
)

from tests.centering_rows import add_centering_rows, declined_side, scored_side, side_score
from tests.fixtures.generate_samples import build_fixture


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


# --- recompute: a placement becomes a reading, and clearing undoes it -----

#: T/B 25/35 is a 41.7/58.3 split; L/R is even. So the worse side is 58.3.
PLACED = {"left_px": 30.0, "right_px": 30.0, "top_px": 25.0, "bottom_px": 35.0}


def _placed_score() -> tuple[float, float]:
    worse = centering.ratios_from_widths(*centering.widths_from(PLACED))["worse_side_pct"]
    return round(centering.score_from_worse_pct(worse), 2), worse


def _submission(db_session, code: str) -> Submission:
    user = User(email=f"{code.lower()}@example.com", hashed_password=hash_password("hunter2pass"), is_verified=True)
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code=code,
        user_id=user.id,
        status=SubmissionStatus.draft_ready,
        language=SubmissionLanguage.en,
    )
    db_session.add(submission)
    db_session.flush()
    return submission


def _with_rows(db_session, code, front, back=None) -> Submission:
    submission = _submission(db_session, code)
    add_centering_rows(db_session, submission, front, back)
    db_session.commit()
    db_session.refresh(submission)
    return submission


def _combined(db_session, submission) -> AnalysisResult:
    db_session.expire_all()
    return (
        db_session.query(AnalysisResult)
        .filter_by(submission_id=submission.id, category=AnalysisCategory.centering, side=AnalysisSide.combined)
        .one()
    )


def _centering_comparisons(db_session, submission) -> int:
    return (
        db_session.query(GradingCompanyComparison)
        .filter_by(submission_id=submission.id, category="centering")
        .count()
    )


def _set_adjustment(db_session, submission, side, widths) -> None:
    adjustments = dict(submission.centering_adjustments or {})
    if widths is None:
        adjustments.pop(side, None)
    else:
        adjustments[side] = dict(widths)
    submission.centering_adjustments = adjustments or None
    recompute.recompute_submission(db_session, submission)
    db_session.commit()


def test_recompute_never_resurrects_a_score_the_front_declined(db_session):
    """Front declined, back scored: the combined reading is unmeasurable, and a
    recompute for any reason must leave it that way -- no number, no hoisted
    worse_side_pct, no centering comparisons."""
    submission = _with_rows(db_session, "SUB-PLC00", declined_side(), scored_side())
    assert _combined(db_session, submission).raw_score is None

    recompute.recompute_submission(db_session, submission)
    db_session.commit()

    row = _combined(db_session, submission)
    assert row.raw_score is None
    assert "worse_side_pct" not in row.measurements
    assert _centering_comparisons(db_session, submission) == 0


def test_placing_a_declined_front_scores_the_combined_row(db_session):
    submission = _with_rows(db_session, "SUB-PLC01", declined_side())

    _set_adjustment(db_session, submission, "front", PLACED)

    row = _combined(db_session, submission)
    score, worse = _placed_score()
    block = row.measurements["assessment"]
    assert float(row.raw_score) == score
    assert block["state"] == "measured"
    assert block["limitations"] == [assessment.CENTERING_CLIENT_PLACED]
    assert block["confidence"] == assessment.CONFIDENCE_CENTERING_CLIENT_PLACED
    assert row.measurements["worse_side_pct"] == round(worse, 1)
    assert _centering_comparisons(db_session, submission) > 0


def test_clearing_a_placement_restores_the_original_exactly(db_session):
    """The reverse direction, which is where the equivalent bugs lived. The
    helper's rows carry no `original_assessment`, like every row analysed
    before this shipped, so this also covers the first-recompute case."""
    submission = _with_rows(db_session, "SUB-PLC02", declined_side())
    original = copy.deepcopy(_combined(db_session, submission).measurements["assessment"])

    _set_adjustment(db_session, submission, "front", PLACED)
    _set_adjustment(db_session, submission, "front", None)

    row = _combined(db_session, submission)
    assert row.raw_score is None
    assert row.measurements["assessment"] == original
    assert row.measurements["original_assessment"] == original
    assert "worse_side_pct" not in row.measurements
    assert _centering_comparisons(db_session, submission) == 0


def test_a_side_whose_edges_were_not_found_is_not_placed(db_session):
    submission = _with_rows(db_session, "SUB-PLC03", declined_side(assessment.GEOMETRY_UNVERIFIED))

    _set_adjustment(db_session, submission, "front", PLACED)

    assert _combined(db_session, submission).raw_score is None


def test_a_placed_back_combines_with_a_scored_front(db_session):
    front = scored_side()
    submission = _with_rows(db_session, "SUB-PLC04", front, declined_side())

    _set_adjustment(db_session, submission, "back", PLACED)

    row = _combined(db_session, submission)
    block = row.measurements["assessment"]
    assert block["state"] == "measured"
    assert assessment.CENTERING_CLIENT_PLACED in block["limitations"]
    assert block["confidence"] == assessment.CONFIDENCE_CENTERING_CLIENT_PLACED
    assert float(row.raw_score) == scoring.combine_sides_by_name(
        {"front": side_score(front), "back": _placed_score()[0]}
    )


def test_a_placed_front_with_an_unplaced_declined_back_is_a_single_side_reading(db_session):
    submission = _with_rows(db_session, "SUB-PLC05", declined_side(), declined_side())

    _set_adjustment(db_session, submission, "front", PLACED)

    block = _combined(db_session, submission).measurements["assessment"]
    assert block["state"] == "measured"
    assert assessment.COMBINED_SINGLE_SIDE in block["limitations"]
    assert block["confidence"] == round(
        assessment.CONFIDENCE_CENTERING_CLIENT_PLACED * assessment.CONFIDENCE_SINGLE_SIDE_FACTOR, 2
    )


def test_placed_side_needs_an_axis_with_both_lines_inside_the_card():
    """Every line at the card's edge leaves no axis at all, and
    ratios_from_widths would fall back to a perfect 50/50."""
    zeros = {"left_px": 0, "right_px": 0, "top_px": 0, "bottom_px": 0}
    assert recompute.placed_side(declined_side(), zeros) is None
    assert recompute.placed_side(declined_side(), PLACED) is not None


# --- a placement survives re-analysis --------------------------------------


def _combined_centering_row(db_session, submission) -> AnalysisResult:
    db_session.expire_all()
    return (
        db_session.query(AnalysisResult)
        .filter_by(submission_id=submission.id, category=AnalysisCategory.centering, side=AnalysisSide.combined)
        .one()
    )


def test_a_placement_survives_re_analysis(db_session, tmp_path):
    """A late back scan, a re-confirmed crop -- anything that reruns the
    pipeline -- must not silently drop a stored placement. Before the fix,
    run_analysis only re-applied recompute when dismissed_regions was set, so
    a rebuilt centering row came back unmeasurable while
    centering_adjustments and client_adjusted stayed put: the report
    contradicting itself."""
    user = User(
        email="plc-reanalysis@example.com",
        hashed_password=hash_password("hunter2pass"),
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code="SUB-PLC06",
        user_id=user.id,
        status=SubmissionStatus.draft_ready,
        language=SubmissionLanguage.en,
    )
    db_session.add(submission)
    db_session.flush()
    db_session.add(Card(submission_id=submission.id, game="Pokemon", card_name="Full Art"))

    # full_art_centered declines centering with centering_no_frame while the
    # edge fit itself holds -- exactly the shape a placement is for.
    image = build_fixture("full_art_centered")
    height, width = image.shape[:2]
    front_path = tmp_path / "scan_front.png"
    cv2.imwrite(str(front_path), image)
    db_session.add(
        ScanImage(
            submission_id=submission.id,
            side=ScanSide.front,
            file_path=str(front_path),
            original_filename="scan_front.png",
            dpi=600,
            width_px=width,
            height_px=height,
            checksum=hashlib.sha256(front_path.read_bytes()).hexdigest(),
        )
    )
    db_session.commit()

    pipeline.run_analysis(db_session, submission)
    db_session.commit()

    front_row = (
        db_session.query(AnalysisResult)
        .filter_by(submission_id=submission.id, category=AnalysisCategory.centering, side=AnalysisSide.front)
        .one()
    )
    ppm = front_row.measurements["card_geometry"]["px_per_mm"]

    submission.centering_adjustments = {
        "front": {
            "left_px": 2.5 * ppm,
            "right_px": 3.5 * ppm,
            "top_px": 3.0 * ppm,
            "bottom_px": 3.0 * ppm,
        }
    }
    recompute.recompute_submission(db_session, submission)
    db_session.commit()

    assert _combined_centering_row(db_session, submission).raw_score is not None

    pipeline.run_analysis(db_session, submission)
    db_session.commit()

    row = _combined_centering_row(db_session, submission)
    assert row.raw_score is not None
    assert assessment.CENTERING_CLIENT_PLACED in row.measurements["assessment"]["limitations"]
