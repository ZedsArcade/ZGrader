"""Centering rows shaped like the pipeline's, for tests that need a declined or
scored centering side without running OpenCV.

Built by hand because `_persist_combined` needs every category's result at
once. The combined row is assembled from the same functions it uses --
`assessment.combine_assessments`, `scoring.combine_front_back`,
`scoring.combine_sides_by_name` -- and the same "score follows the assessment"
rule, so it matches what the pipeline stores.
"""

import copy

from zgrader.analysis import assessment, centering, scoring
from zgrader.models import AnalysisCategory, AnalysisResult, AnalysisSide

PX_PER_MM = 10.0


def declined_side(*extra_limitations: str) -> dict:
    """A side where no printed frame was found. Left and top were read; right
    and bottom were not, so their indicative widths are the 0.0 refusal."""
    limitations = (assessment.CENTERING_NO_FRAME, *extra_limitations)
    return {
        "indicative_estimate": {
            "left_px": 30.0,
            "right_px": 0.0,
            "top_px": 28.0,
            "bottom_px": 0.0,
            "per_side": {
                "left": {"measured": True},
                "right": {"measured": False},
                "top": {"measured": True},
                "bottom": {"measured": False},
            },
        },
        "assessment": assessment.unmeasurable(limitations).as_dict(),
        "card_geometry": {"px_per_mm": PX_PER_MM},
        "regions": [],
    }


def scored_side(left: float = 30.0, right: float = 34.0, top: float = 30.0, bottom: float = 30.0) -> dict:
    ratios = centering.ratios_from_widths(left, right, top, bottom)
    score = round(centering.score_from_worse_pct(ratios["worse_side_pct"]), 2)
    return {
        "left_px": left,
        "right_px": right,
        "top_px": top,
        "bottom_px": bottom,
        "lr_ratio": ratios["lr_ratio"],
        "tb_ratio": ratios["tb_ratio"],
        "worse_side_pct": ratios["worse_side_pct"],
        "assessment": assessment.measured(score, assessment.CONFIDENCE_CENTERING_CLEAN_FRAME).as_dict(),
        "card_geometry": {"px_per_mm": PX_PER_MM},
        "regions": [],
    }


def side_score(side: dict | None) -> float | None:
    if side is None or side["assessment"]["state"] != assessment.MEASURED:
        return None
    return round(centering.score_from_worse_pct(side["worse_side_pct"]), 2)


def add_centering_rows(db, submission, front: dict, back: dict | None = None) -> None:
    for side_enum, measurements in ((AnalysisSide.front, front), (AnalysisSide.back, back)):
        if measurements is None:
            continue
        db.add(
            AnalysisResult(
                submission_id=submission.id,
                category=AnalysisCategory.centering,
                side=side_enum,
                raw_score=side_score(measurements),
                measurements=copy.deepcopy(measurements),
                flags={},
            )
        )

    combined: dict = {"front": copy.deepcopy(front)}
    if back is not None:
        combined["back"] = copy.deepcopy(back)
    if front.get("worse_side_pct") is not None:
        combined["worse_side_pct"] = round(
            scoring.combine_front_back(front["worse_side_pct"], (back or {}).get("worse_side_pct")), 1
        )
        combined["original_worse_side_pct"] = combined["worse_side_pct"]
    combined["assessment"] = assessment.combine_assessments(
        front["assessment"], back["assessment"] if back else None
    )
    scores = {
        name: score
        for name, score in (("front", side_score(front)), ("back", side_score(back)))
        if score is not None
    }
    raw = (
        scoring.combine_sides_by_name(scores)
        if combined["assessment"]["state"] == assessment.MEASURED
        else None
    )
    combined["original_raw_score"] = raw
    db.add(
        AnalysisResult(
            submission_id=submission.id,
            category=AnalysisCategory.centering,
            side=AnalysisSide.combined,
            raw_score=raw,
            measurements=combined,
            flags={},
        )
    )
    db.flush()
