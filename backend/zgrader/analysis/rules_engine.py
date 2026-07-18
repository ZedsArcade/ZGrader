"""Config-driven multi-company comparison engine.

For each active GradingCompanyToleranceRule, evaluate the submission's
per-category AnalysisResult against that company's thresholds and emit a
GradingCompanyComparison: a severity flag plus a templated "points of
contention" note. This NEVER produces a numeric grade prediction for any
company -- only flag/no-flag and reasoning, per product requirements.

Thresholds live entirely in the GradingCompanyToleranceRule table (seeded by
zgrader/seed/tolerance_rules_seed.py) so they can be tuned later against
real submitted-grade outcomes without touching this code.
"""

from sqlalchemy.orm import Session

from zgrader.models import (
    AnalysisResult,
    AnalysisSide,
    GradingCompanyComparison,
    GradingCompanyToleranceRule,
    Submission,
    ToleranceSeverity,
)

_SEVERITY_WORDS = {
    ToleranceSeverity.none: "not expected to be flagged",
    ToleranceSeverity.minor: "likely to draw a minor deduction",
    ToleranceSeverity.major: "likely to draw a significant deduction",
}


def _severity_for_centering(worse_side_pct: float, thresholds: dict) -> ToleranceSeverity:
    if worse_side_pct >= thresholds["major_at"]:
        return ToleranceSeverity.major
    if worse_side_pct >= thresholds["minor_at"]:
        return ToleranceSeverity.minor
    return ToleranceSeverity.none


def _severity_for_score(raw_score: float, thresholds: dict) -> ToleranceSeverity:
    if raw_score < thresholds["major_below"]:
        return ToleranceSeverity.major
    if raw_score < thresholds["minor_below"]:
        return ToleranceSeverity.minor
    return ToleranceSeverity.none


def _combined_results_by_category(submission: Submission) -> dict[str, AnalysisResult]:
    """Pick one AnalysisResult per category, preferring the `combined`
    front+back result over a lone `front`/`back` result if that's all
    that's available."""
    by_category: dict[str, AnalysisResult] = {}
    for result in submission.analysis_results:
        existing = by_category.get(result.category)
        if existing is None or result.side == AnalysisSide.combined:
            by_category[result.category] = result
    return by_category


def evaluate(db: Session, submission: Submission) -> list[GradingCompanyComparison]:
    combined_by_category = _combined_results_by_category(submission)

    rules = (
        db.query(GradingCompanyToleranceRule)
        .filter(GradingCompanyToleranceRule.active.is_(True))
        .all()
    )

    comparisons: list[GradingCompanyComparison] = []
    for rule in rules:
        result = combined_by_category.get(rule.category)
        if result is None:
            continue

        measurements = result.measurements or {}
        if rule.metric_key == "worse_side_pct":
            worse_side_pct = measurements.get("worse_side_pct")
            if worse_side_pct is None:
                continue
            severity = _severity_for_centering(worse_side_pct, rule.thresholds)
            note = rule.note_template.format(
                worse_side_pct=worse_side_pct,
                better_side_pct=100 - worse_side_pct,
                severity_word=_SEVERITY_WORDS[severity],
            )
        elif rule.metric_key == "raw_score":
            raw_score = float(result.raw_score)
            severity = _severity_for_score(raw_score, rule.thresholds)
            note = rule.note_template.format(
                raw_score=raw_score,
                category=rule.category,
                severity_word=_SEVERITY_WORDS[severity],
            )
        else:
            continue

        comparison = GradingCompanyComparison(
            submission_id=submission.id,
            company=rule.company,
            category=rule.category,
            severity=severity,
            contention_note=note,
        )
        db.add(comparison)
        comparisons.append(comparison)

    db.flush()
    return comparisons
