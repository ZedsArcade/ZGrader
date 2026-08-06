"""Recompute a submission's assessment when the client dismisses findings
they believe the auto-detector got wrong.

The rules engine and PDF both read each category's `combined` AnalysisResult
`raw_score` (and centering's top-level `worse_side_pct`), and every category
score is derivable from the per-side data already stored in
`measurements` -- so a dismissal is a pure re-aggregation (no image
reprocessing) that overwrites the `combined` rows and re-runs the comparison
engine. The per-side rows and each combined row's `original_raw_score` are
never mutated, so this is safe to run repeatedly as toggles change.

Dismissed keys are "{side}:{category}:{region_id}", e.g.
"front:surface:blob_2" -- see Submission.dismissed_regions.
"""

from sqlalchemy.orm import Session

from zgrader.analysis import assessment, centering, rules_engine, scoring, surface
from zgrader.models import AnalysisSide, GradingCompanyComparison, Submission


def _parse_dismissed(dismissed_regions: list | None) -> dict[tuple[str, str], set[str]]:
    parsed: dict[tuple[str, str], set[str]] = {}
    for key in dismissed_regions or []:
        parts = key.split(":")
        if len(parts) != 3:
            continue
        side, category, region_id = parts
        parsed.setdefault((side, category), set()).add(region_id)
    return parsed


def _adjusted_side_score(
    category: str, side_measurements: dict, dismissed_ids: set[str]
) -> tuple[float | None, float | None]:
    """Adjusted (raw_score, worse_side_pct) for one side, treating dismissed
    regions as clean. worse_side_pct is only meaningful for centering.

    A `None` score means "no adjustment can be derived from what is stored" --
    the caller leaves the persisted score alone. That is distinct from a low
    score, and distinct from the client asserting a side is clean. Absent data
    used to be reported as 10.0 here, which manufactured a perfect score out
    of nothing.
    """
    # A side the pipeline declined to score cannot have a score re-derived for
    # it. This is generic rather than per-category on purpose: every time a
    # category has gained the ability to decline -- corners below the
    # resolution floor, centering with no frame, surface with no fine detail --
    # something downstream that assumed a number has had to be found. Checking
    # the assessment state catches the next one too.
    #
    # Caught by test_no_dismissals_reproduces_the_pipeline_score_exactly, which
    # is worded as an invariant precisely so it fails when the two paths
    # diverge rather than needing someone to predict how.
    state = (side_measurements.get("assessment") or {}).get("state")
    if state is not None and state != assessment.MEASURED:
        return None, None

    regions = side_measurements.get("regions", [])

    if category in ("corners", "edges"):
        kept = [r["score"] for r in regions if r["id"] not in dismissed_ids]
        if not kept:
            # Every finding disputed. A dispute is a claim that the detector
            # was wrong, not evidence that the card is flawless -- this used
            # to return 10.0, awarding a perfect score to the most damaged
            # cards, since those are the ones with every region flagged. The
            # measurement stands and the dispute is recorded separately (see
            # Submission.dismissed_regions and the report's Client Adjustments
            # section).
            return None, None
        if category == "corners":
            # Corners are worst-anchored, not averaged, so this has to go
            # through the same function the pipeline used or the two disagree
            # the moment nothing has even been dismissed. That is exactly the
            # drift analysis/scoring.py exists to prevent, and it reappeared
            # here the instant the aggregation changed -- caught by
            # test_no_dismissals_reproduces_the_pipeline_score_exactly, which
            # is the whole reason that test is worded the way it is.
            #
            # Applied to the kept subset: the client disputed a finding, so the
            # remaining findings are what defines the worst corner.
            return round(scoring.corners_category_score(kept), 2), None
        return round(float(sum(kept) / len(kept)), 2), None

    if category == "centering":
        if "frame" in dismissed_ids:
            # Centering has exactly one region, so dismissing it leaves
            # nothing to re-aggregate from. It used to assert a perfect 50/50
            # cut on the client's say-so; the measured ratio stands instead,
            # marked as disputed.
            return None, None
        worse = side_measurements.get("worse_side_pct")
        if worse is None:
            # Nothing was measured for this side, so there is nothing to
            # re-derive. Keep the stored score.
            return None, None
        return round(centering.score_from_worse_pct(worse), 2), float(worse)

    if category == "surface":
        anomaly_fraction = side_measurements.get("anomaly_fraction", 0.0)
        dismissed_area = sum(
            r.get("area_fraction", 0.0) for r in regions if r["id"] in dismissed_ids
        )
        adjusted = max(0.0, anomaly_fraction - dismissed_area)
        return round(surface.score_from_anomaly_fraction(adjusted), 2), None

    # Unknown category: this module doesn't know how to re-aggregate it, so
    # leave the stored score exactly as the pipeline computed it.
    return None, None


def recompute_submission(db: Session, submission: Submission) -> None:
    """Overwrite the combined AnalysisResult scores to reflect the client's
    dismissed_regions and rebuild the company comparisons. A no-op-equivalent
    (empty dismissed set) restores the original auto-detected scores."""
    dismissed = _parse_dismissed(submission.dismissed_regions)

    # This module never mutates the per-side rows, so they stay the record of
    # what was actually measured. When a side's findings are all disputed and
    # no adjustment is derivable, that measurement stands -- dropping the side
    # instead would silently re-weight the other one to 100%.
    stored_side_scores: dict[tuple[str, str], float] = {}
    for row in submission.analysis_results:
        if row.side == AnalysisSide.combined:
            continue
        side_category = row.category.value if hasattr(row.category, "value") else str(row.category)
        if row.raw_score is None:
            # Unmeasurable sides have no score to fall back to, so they are
            # left out entirely rather than contributing a zero.
            continue
        stored_side_scores[(row.side.value, side_category)] = float(row.raw_score)

    for row in submission.analysis_results:
        if row.side != AnalysisSide.combined:
            continue
        category = row.category.value if hasattr(row.category, "value") else str(row.category)
        measurements = dict(row.measurements or {})

        scores_by_side: dict[str, float] = {}
        worse_by_side: dict[str, float] = {}
        for side in ("front", "back"):
            side_m = measurements.get(side)
            if side_m is None:
                continue
            score, worse = _adjusted_side_score(
                category, side_m, dismissed.get((side, category), set())
            )
            if score is None:
                score = stored_side_scores.get((side, category))
                worse = side_m.get("worse_side_pct")
            if score is None:
                continue
            scores_by_side[side] = score
            if worse is not None:
                worse_by_side[side] = float(worse)

        combined = scoring.combine_sides_by_name(scores_by_side)
        if combined is None:
            continue

        row.raw_score = combined
        if category == "centering" and worse_by_side:
            combined_worse = scoring.combine_sides_by_name(worse_by_side)
            if combined_worse is not None:
                measurements["worse_side_pct"] = round(combined_worse, 1)
                row.measurements = measurements  # reassign so SQLAlchemy tracks the JSONB change

    db.flush()

    db.query(GradingCompanyComparison).filter(
        GradingCompanyComparison.submission_id == submission.id
    ).delete()
    rules_engine.evaluate(db, submission)
    db.flush()
