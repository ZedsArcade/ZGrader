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
    AuditLog,
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


# --- revalidating a stored adjustment against a fresh row (final review 1) -


def _dropped_audit_rows(db_session, submission) -> list[AuditLog]:
    return (
        db_session.query(AuditLog)
        .filter_by(submission_id=submission.id, action="centering_adjustment_dropped")
        .all()
    )


def _replace_front_with_scored(db_session, submission, **widths) -> None:
    """Simulate what a real re-analysis does to the per-side/combined rows:
    delete the old centering rows and add freshly scored ones."""
    db_session.query(AnalysisResult).filter_by(
        submission_id=submission.id, category=AnalysisCategory.centering
    ).delete()
    add_centering_rows(db_session, submission, scored_side(**widths))
    db_session.commit()
    db_session.refresh(submission)


def test_revalidation_drops_a_placement_beyond_the_new_detections_nudge_cap(db_session):
    """A placement is checked against the row it was made on -- eligibility and
    the 8mm placement bound. If re-analysis replaces that row with a scored
    one, the same widths have to pass the *nudge* cap instead, or they would
    flow through the nudge branch of _adjusted_side_score uncapped and with
    no centering_client_placed label: the exact bug reproduced in the review
    (2.22 at confidence 0.4, labelled, became 2.22 at confidence 0.9,
    unlabelled)."""
    submission = _with_rows(db_session, "SUB-PLC07", declined_side())
    # Bottom 8mm, top 1mm -- both inside the 8mm placement bound.
    placement = {"left_px": 30.0, "right_px": 30.0, "top_px": 10.0, "bottom_px": 80.0}
    _set_adjustment(db_session, submission, "front", placement)
    assert _combined(db_session, submission).raw_score is not None

    # The fresh detection reads all four widths at 3mm (30px @ 10px/mm) --
    # 5mm and 2mm away from the stored placement, both beyond the 4mm default
    # nudge cap.
    _replace_front_with_scored(db_session, submission, left=30.0, right=30.0, top=30.0, bottom=30.0)

    pipeline._revalidate_centering_adjustments(db_session, submission)
    db_session.commit()
    recompute.recompute_submission(db_session, submission)
    db_session.commit()

    assert (submission.centering_adjustments or {}).get("front") is None
    dropped = _dropped_audit_rows(db_session, submission)
    assert len(dropped) == 1
    assert dropped[0].detail["side"] == "front"
    assert dropped[0].user_id is None

    row = _combined(db_session, submission)
    expected = side_score(scored_side(left=30.0, right=30.0, top=30.0, bottom=30.0))
    assert float(row.raw_score) == expected
    block = row.measurements["assessment"]
    # The plain scored reading, not a detected-looking 2.22 at confidence 0.9
    # with nothing marking it as ever having been placed.
    assert assessment.CENTERING_CLIENT_PLACED not in block["limitations"]
    assert block["confidence"] == assessment.CONFIDENCE_CENTERING_CLEAN_FRAME


def test_revalidation_keeps_a_placement_within_the_new_detections_nudge_cap(db_session):
    """The companion case: the same flow, but the placement sits within 4mm of
    the freshly detected 3mm lines, so it survives -- now as a nudge -- and
    nothing is dropped or audited."""
    submission = _with_rows(db_session, "SUB-PLC08", declined_side())
    # 1mm and 2mm from the eventual 3mm detection -- inside the 4mm cap.
    placement = {"left_px": 30.0, "right_px": 30.0, "top_px": 20.0, "bottom_px": 50.0}
    _set_adjustment(db_session, submission, "front", placement)

    _replace_front_with_scored(db_session, submission, left=30.0, right=30.0, top=30.0, bottom=30.0)

    pipeline._revalidate_centering_adjustments(db_session, submission)
    db_session.commit()
    recompute.recompute_submission(db_session, submission)
    db_session.commit()

    assert (submission.centering_adjustments or {}).get("front") == placement
    assert _dropped_audit_rows(db_session, submission) == []

    row = _combined(db_session, submission)
    assert row.raw_score is not None
    block = row.measurements["assessment"]
    assert assessment.CENTERING_CLIENT_PLACED not in block["limitations"]
    assert block["confidence"] == assessment.CONFIDENCE_CENTERING_CLEAN_FRAME


# --- check_centering_adjustment: the shared check itself -------------------


def test_check_centering_adjustment_not_measurable():
    measured = _declined(assessment.GEOMETRY_UNVERIFIED)
    assert recompute.check_centering_adjustment(measured, False, PLACED, 4.0) == (None, "not_measurable")


def test_check_centering_adjustment_no_scale():
    """Reachable on the nudge path -- `placement_eligible` already folds a
    scale check into its own answer, so a declined side without one is
    "not_measurable" before this check ever runs (see the test above)."""
    measured = dict(scored_side())
    measured["card_geometry"] = {"px_per_mm": 0}
    assert recompute.check_centering_adjustment(measured, True, PLACED, 4.0) == (None, "no_scale")


def test_check_centering_adjustment_place_within_bound_is_allowed():
    measured = _declined(assessment.CENTERING_NO_FRAME)
    assert recompute.check_centering_adjustment(measured, False, PLACED, 4.0) == ("place", None)


def test_check_centering_adjustment_beyond_placement_bound():
    measured = _declined(assessment.CENTERING_NO_FRAME)  # px_per_mm=10
    widths = {"left_px": 90.0, "right_px": 30.0, "top_px": 25.0, "bottom_px": 35.0}
    mode, reason = recompute.check_centering_adjustment(measured, False, widths, 4.0)
    assert mode is None
    assert reason == "beyond_placement_bound:left_px"


def test_check_centering_adjustment_placement_bound_tolerance():
    """0.05px tolerance either side of the 8mm bound (final review Minor 1)."""
    measured = _declined(assessment.CENTERING_NO_FRAME)  # px_per_mm=10 -> 80px bound
    at_bound = {"left_px": 80.04, "right_px": 30.0, "top_px": 25.0, "bottom_px": 35.0}
    assert recompute.check_centering_adjustment(measured, False, at_bound, 4.0) == ("place", None)

    beyond = {"left_px": 80.06, "right_px": 30.0, "top_px": 25.0, "bottom_px": 35.0}
    mode, reason = recompute.check_centering_adjustment(measured, False, beyond, 4.0)
    assert mode is None
    assert reason == "beyond_placement_bound:left_px"


def test_check_centering_adjustment_no_axis():
    measured = _declined(assessment.CENTERING_NO_FRAME)
    zeros = {"left_px": 0, "right_px": 0, "top_px": 0, "bottom_px": 0}
    assert recompute.check_centering_adjustment(measured, False, zeros, 4.0) == (None, "no_axis")


def test_check_centering_adjustment_nudge_within_cap_is_allowed():
    measured = scored_side()  # left=30, right=34, top=30, bottom=30, px_per_mm=10
    widths = {"left_px": 30.0, "right_px": 34.0, "top_px": 30.0, "bottom_px": 30.0}
    assert recompute.check_centering_adjustment(measured, True, widths, 4.0) == ("nudge", None)


def test_check_centering_adjustment_no_detected_width():
    measured = scored_side()
    del measured["right_px"]
    mode, reason = recompute.check_centering_adjustment(measured, True, PLACED, 4.0)
    assert mode is None
    assert reason == "no_detected_width:right_px"


def test_check_centering_adjustment_beyond_nudge_cap():
    measured = scored_side()  # bottom detected at 30px, px_per_mm=10 -> 4mm cap = 40px
    widths = {"left_px": 30.0, "right_px": 34.0, "top_px": 30.0, "bottom_px": 30.0 + 50.0}
    mode, reason = recompute.check_centering_adjustment(measured, True, widths, 4.0)
    assert mode is None
    assert reason == "beyond_nudge_cap:bottom_px"


def test_check_centering_adjustment_nudge_cap_tolerance():
    measured = scored_side()
    limit_px = 4.0 * 10.0
    at_cap = {"left_px": 30.0, "right_px": 34.0, "top_px": 30.0, "bottom_px": 30.0 + limit_px + 0.04}
    assert recompute.check_centering_adjustment(measured, True, at_cap, 4.0) == ("nudge", None)

    beyond_cap = {"left_px": 30.0, "right_px": 34.0, "top_px": 30.0, "bottom_px": 30.0 + limit_px + 0.06}
    mode, reason = recompute.check_centering_adjustment(measured, True, beyond_cap, 4.0)
    assert mode is None
    assert reason == "beyond_nudge_cap:bottom_px"


def test_check_centering_adjustment_enforce_nudge_cap_false_keeps_a_beyond_cap_nudge():
    measured = scored_side()
    widths = {"left_px": 30.0, "right_px": 34.0, "top_px": 30.0, "bottom_px": 30.0 + 500.0}
    assert recompute.check_centering_adjustment(measured, True, widths, 4.0, enforce_nudge_cap=False) == (
        "nudge",
        None,
    )


# --- spec test: a placed front combines with a scored back (final review 4) -


def test_a_placed_front_combines_with_a_scored_back(db_session):
    back = scored_side()
    submission = _with_rows(db_session, "SUB-PLC09", declined_side(), back)

    _set_adjustment(db_session, submission, "front", PLACED)

    row = _combined(db_session, submission)
    block = row.measurements["assessment"]
    assert block["state"] == "measured"
    assert assessment.CENTERING_CLIENT_PLACED in block["limitations"]
    assert block["confidence"] == assessment.CONFIDENCE_CENTERING_CLIENT_PLACED
    assert float(row.raw_score) == scoring.combine_sides_by_name(
        {"front": _placed_score()[0], "back": side_score(back)}
    )
