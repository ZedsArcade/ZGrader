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

from zgrader.analysis import centering, rules_engine
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
) -> tuple[float, float | None]:
    """Adjusted (raw_score, worse_side_pct) for one side, treating dismissed
    regions as clean. worse_side_pct is only meaningful for centering."""
    regions = side_measurements.get("regions", [])

    if category in ("corners", "edges"):
        kept = [r["score"] for r in regions if r["id"] not in dismissed_ids]
        # All findings dismissed -> the client asserts this side is clean.
        score = sum(kept) / len(kept) if kept else 10.0
        return round(float(score), 2), None

    if category == "centering":
        if "frame" in dismissed_ids:
            # The client says the card is fine -> perfectly centered.
            return 10.0, 50.0
        worse = side_measurements.get("worse_side_pct")
        if worse is None:
            return 10.0, None
        return round(centering._score_from_worse_pct(worse), 2), float(worse)

    if category == "surface":
        anomaly_fraction = side_measurements.get("anomaly_fraction", 0.0)
        dismissed_area = sum(
            r.get("area_fraction", 0.0) for r in regions if r["id"] in dismissed_ids
        )
        adjusted = max(0.0, anomaly_fraction - dismissed_area)
        score = min(10.0, max(0.0, 10.0 - adjusted * 200.0))
        return round(float(score), 2), None

    # Unknown category -- leave whatever the stored per-side score implied.
    return 10.0, None


def recompute_submission(db: Session, submission: Submission) -> None:
    """Overwrite the combined AnalysisResult scores to reflect the client's
    dismissed_regions and rebuild the company comparisons. A no-op-equivalent
    (empty dismissed set) restores the original auto-detected scores."""
    dismissed = _parse_dismissed(submission.dismissed_regions)

    for row in submission.analysis_results:
        if row.side != AnalysisSide.combined:
            continue
        category = row.category.value if hasattr(row.category, "value") else str(row.category)
        measurements = dict(row.measurements or {})

        side_scores: list[float] = []
        side_worse: list[float] = []
        for side in ("front", "back"):
            side_m = measurements.get(side)
            if side_m is None:
                continue
            score, worse = _adjusted_side_score(
                category, side_m, dismissed.get((side, category), set())
            )
            side_scores.append(score)
            if worse is not None:
                side_worse.append(worse)

        if not side_scores:
            continue

        row.raw_score = round(sum(side_scores) / len(side_scores), 2)
        if category == "centering" and side_worse:
            measurements["worse_side_pct"] = round(sum(side_worse) / len(side_worse), 1)
            row.measurements = measurements  # reassign so SQLAlchemy tracks the JSONB change

    db.flush()

    db.query(GradingCompanyComparison).filter(
        GradingCompanyComparison.submission_id == submission.id
    ).delete()
    rules_engine.evaluate(db, submission)
    db.flush()
