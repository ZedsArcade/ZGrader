"""Orchestrates the full per-submission analysis pipeline: preprocess each
scan, run centering/corners/edges/surface on front and back, persist
per-side and combined AnalysisResult rows with annotated images, then hand
off to the multi-company rules engine.
"""

import io
import logging
from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from zgrader.analysis import (
    ai,
    annotate,
    assessment,
    centering,
    corners,
    creases,
    edges,
    preprocessing,
    recompute,
    regions,
    rules_engine,
    scale,
    scoring,
    surface,
)

logger = logging.getLogger(__name__)
from zgrader.config import config
from zgrader.models import (
    AnalysisCategory,
    AnalysisResult,
    AnalysisSide,
    ScanImage,
    ScanSide,
    Submission,
    SubmissionStatus,
)


class PipelineError(Exception):
    pass


# Every analyser takes the same four inputs, whether or not it uses all of
# them: the rectified card, its exact scale, the card mask in that same raster,
# and the fitted geometry. Uniform signatures keep the dispatch table below a
# table rather than four special cases, and mean adding an input to one
# analyser does not reshape the loop that calls them.


def _analyze_centering(
    card_image: np.ndarray, px_per_mm: float, mask: np.ndarray | None, geometry: dict | None
) -> tuple[dict, None]:
    return centering.measure_centering(card_image, px_per_mm), None


def _analyze_corners(
    card_image: np.ndarray, px_per_mm: float, mask: np.ndarray | None, geometry: dict | None
) -> tuple[dict, None]:
    return corners.measure_corners(card_image, px_per_mm=px_per_mm, mask=mask), None


def _analyze_edges(
    card_image: np.ndarray, px_per_mm: float, mask: np.ndarray | None, geometry: dict | None
) -> tuple[dict, None]:
    return edges.measure_edges(card_image, px_per_mm=px_per_mm, geometry=geometry), None


def _analyze_surface(
    card_image: np.ndarray, px_per_mm: float, mask: np.ndarray | None, geometry: dict | None
) -> tuple[dict, np.ndarray]:
    return surface.measure_surface(card_image, px_per_mm=px_per_mm)


_ANALYZERS = {
    AnalysisCategory.centering: _analyze_centering,
    AnalysisCategory.corners: _analyze_corners,
    AnalysisCategory.edges: _analyze_edges,
    AnalysisCategory.surface: _analyze_surface,
}


def _annotate_category(category: AnalysisCategory, card_image: np.ndarray, result: dict, extra):
    if result["raw_score"] is None:
        # Nothing was measurable, so there is nothing to draw. Every overlay in
        # annotate.py is an assertion -- a green corner box says "checked and
        # clean", a centering rectangle says "the border is here" -- and an
        # unscored category has made no such claim. The plain deskewed card is
        # still saved under the category's filename so the report and the
        # results page keep working unchanged.
        #
        # This also covers a real crash: annotate_centering reads left_px off
        # the top-level measurements, and an unmeasurable centering result
        # moves those under `indicative_estimate`, so a genuine full-art card
        # would have raised KeyError here.
        return annotate.to_pil(card_image)
    if category == AnalysisCategory.centering:
        return annotate.annotate_centering(card_image, result["measurements"])
    if category == AnalysisCategory.corners:
        return annotate.annotate_corners(card_image, result["measurements"])
    if category == AnalysisCategory.edges:
        return annotate.annotate_edges(card_image, result["measurements"]["per_edge"])
    if category == AnalysisCategory.surface:
        return annotate.annotate_surface(card_image, extra)
    raise ValueError(f"Unknown analysis category: {category}")


def _run_ai_analysis(card_image: np.ndarray, side: str, language: str, code: str) -> list[dict]:
    analyzer = ai.get_analyzer()
    if analyzer is None:
        return []
    try:
        buffer = io.BytesIO()
        annotate.to_pil(card_image).save(buffer, format="PNG")
        return analyzer.analyze(buffer.getvalue(), side, language)
    except Exception:  # noqa: BLE001 -- an unavailable model must not fail analysis
        logger.warning("AI analyzer failed for %s %s -- skipping", code, side)
        return []


def _persist_side(
    db: Session,
    submission: Submission,
    reports_dir: Path,
    side: ScanSide,
    card_image: np.ndarray,
    px_per_mm: float,
    geometry: dict | None = None,
    geometry_limitations: tuple[str, ...] = (),
    mask: np.ndarray | None = None,
) -> dict[AnalysisCategory, dict]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    results: dict[AnalysisCategory, dict] = {}

    # The plain deskewed photo, previously never persisted (it only existed
    # transiently as `card_image`) -- the web results page's base photo for
    # this side, served by GET /submissions/{code}/scans/{side}/photo.
    annotate.to_pil(card_image).save(reports_dir / f"{side.value}_base.png")

    h, w = card_image.shape[:2]
    language = submission.language.value

    # Optional external AI "second opinion" for this side -- off unless a
    # model is configured, and never allowed to break analysis. Attached to
    # the surface result's measurements below (surface is always present).
    ai_observations = _run_ai_analysis(card_image, side.value, language, submission.submission_code)

    for category, analyzer in _ANALYZERS.items():
        result, extra = analyzer(card_image, px_per_mm, mask, geometry)
        # Geometry is established once per scan, not once per category, so it
        # is folded in here rather than threaded through four analyser
        # signatures to be used the same way in each. It only devalues a
        # reading; it never rescues one.
        if geometry_limitations:
            result["measurements"]["assessment"] = assessment.with_limitations(
                result["measurements"].get("assessment"),
                geometry_limitations,
                result["raw_score"],
            )
        if geometry is not None:
            # Unscored, and stored on every category because each one measures
            # from this boundary. The per-side residuals are what a later phase
            # turns into an edge-roughness channel.
            result["measurements"]["card_geometry"] = geometry
        image = _annotate_category(category, card_image, result, extra)
        image_path = reports_dir / f"{side.value}_{category.value}.png"
        image.save(image_path)

        result["measurements"]["regions"] = regions.build_regions(
            category, (h, w), px_per_mm, language, result, extra
        )
        if category == AnalysisCategory.surface:
            # Crease candidates ride along the surface side's regions so they
            # reuse crops/overlay/dismiss; flag-only (no score effect).
            crease_lines = creases.detect_creases(card_image, px_per_mm)
            result["measurements"]["regions"].extend(
                regions.build_crease_regions((h, w), language, crease_lines)
            )
            if ai_observations:
                result["measurements"]["ai_observations"] = ai_observations
        for region in result["measurements"]["regions"]:
            if region["severity"] != "flag":
                continue
            x0, y0, x1, y1 = region["bbox_norm"]
            bbox_px = (x0 * w, y0 * h, x1 * w, y1 * h)
            # A crease's bbox spans most of the card, so the crop alone shows
            # "somewhere in here" -- draw the actual segment inside it.
            line_norm = region.get("line_norm")
            line_px = (
                (line_norm[0] * w, line_norm[1] * h, line_norm[2] * w, line_norm[3] * h)
                if line_norm
                else None
            )
            crop = annotate.crop_region(card_image, bbox_px, line_px=line_px)
            crop_path = reports_dir / f"{side.value}_{category.value}_{region['id']}_crop.png"
            crop.save(crop_path)

        db.add(
            AnalysisResult(
                submission_id=submission.id,
                category=category,
                side=AnalysisSide(side.value),
                raw_score=result["raw_score"],
                measurements=result["measurements"],
                annotated_image_path=str(image_path),
                flags=result.get("flags", {}),
            )
        )
        results[category] = result

    return results


def _combine_score(front_score: float | None, back_score: float | None) -> float | None:
    return scoring.combine_front_back(front_score, back_score)


def _combine_assessments(front: dict | None, back: dict | None) -> dict | None:
    """Merge two sides' assessments pessimistically.

    Lowest confidence, union of limitations, and unmeasurable if either side
    was: a category is only as trustworthy as its weaker face, and a
    limitation that applied to one side applied to the card the customer sent.
    Averaging confidence would let a clean back talk up an unreadable front,
    which is the same mistake the 70/30 score weighting exists to avoid.
    """
    blocks = [b for b in (front, back) if b]
    if not blocks:
        return None
    if len(blocks) == 1:
        return dict(blocks[0])

    limitations = sorted({code for b in blocks for code in b["limitations"]})
    unmeasurable = any(b["state"] != assessment.MEASURED for b in blocks)
    lows = [b["score_low"] for b in blocks if b["score_low"] is not None]
    highs = [b["score_high"] for b in blocks if b["score_high"] is not None]
    return {
        "state": assessment.UNMEASURABLE if unmeasurable else assessment.MEASURED,
        "confidence": min(b["confidence"] for b in blocks),
        "score_low": None if unmeasurable or not lows else min(lows),
        "score_high": None if unmeasurable or not highs else max(highs),
        "limitations": limitations,
    }


def _persist_combined(
    db: Session,
    submission: Submission,
    front_results: dict[AnalysisCategory, dict],
    back_results: dict[AnalysisCategory, dict] | None,
) -> None:
    for category in _ANALYZERS:
        front_result = front_results[category]
        back_result = back_results[category] if back_results else None

        measurements = {"front": front_result["measurements"]}
        flags = dict(front_result.get("flags", {}))
        if back_result:
            measurements["back"] = back_result["measurements"]
            flags.update(back_result.get("flags", {}))

        if category == AnalysisCategory.centering:
            # rules_engine reads centering's "worse_side_pct" straight off
            # the combined result's top-level measurements (unlike
            # corners/edges/surface, which key off raw_score instead) -- it
            # has to be hoisted out of the front/back nesting above, or the
            # comparison engine silently skips every centering rule.
            front_worse = front_result["measurements"].get("worse_side_pct")
            back_worse = back_result["measurements"].get("worse_side_pct") if back_result else None
            if front_worse is not None:
                # Weighted the same way as the scores: this is the figure the
                # rules engine compares against every company's centering
                # tolerance, so a well-cut back must not average away a
                # badly-cut front.
                measurements["worse_side_pct"] = round(
                    scoring.combine_front_back(front_worse, back_worse), 1
                )
            if "worse_side_pct" in measurements:
                # Nothing reads this yet, but recompute.py overwrites
                # worse_side_pct in place when a client dismisses the frame
                # finding, so this is the only surviving record of the
                # measured ratio. Kept deliberately -- it is the centering
                # counterpart to original_raw_score below, which the UI and
                # PDF do render as "was X.X".
                measurements["original_worse_side_pct"] = measurements["worse_side_pct"]

        # Hoist a combined assessment alongside the combined score, so the
        # report and the UI can read one place rather than reaching into the
        # front/back nesting. The pessimistic merge is the point: a category
        # is only as trustworthy as its weaker side, and a limitation that
        # applied to either face applied to the card.
        measurements["assessment"] = _combine_assessments(
            front_result["measurements"].get("assessment"),
            back_result["measurements"].get("assessment") if back_result else None,
        )

        combined_score = _combine_score(
            front_result["raw_score"], back_result["raw_score"] if back_result else None
        )
        # Pristine auto-detected value, preserved so the UI/report can show
        # "was X.X" if the client later dismisses findings (recompute.py
        # overwrites raw_score but never touches this).
        measurements["original_raw_score"] = combined_score

        db.add(
            AnalysisResult(
                submission_id=submission.id,
                category=category,
                side=AnalysisSide.combined,
                raw_score=combined_score,
                measurements=measurements,
                annotated_image_path=None,
                flags=flags,
            )
        )


def _load_deskewed_card(
    scan: ScanImage, width_mm: float, height_mm: float
) -> preprocessing.RectifiedCard:
    """Rectify one scan to a canonical raster.

    The customer's crop points are passed as a region-of-interest hint, not as
    the card's geometry. This used to warp straight to them, which made every
    downstream measurement a function of where four handles were dragged: a
    crop half a millimetre inside the card removed the damage from the image
    before anything looked at it, and one half a millimetre outside put
    scanner backing where the card's edge should be. The crop still rejects
    background and neighbouring cards, which is what it is for.
    """
    image = preprocessing.load_image(scan.file_path)
    roi = np.array(scan.crop_points, dtype="float32") if scan.crop_points is not None else None
    return preprocessing.rectify(image, width_mm, height_mm, roi_quad=roi)


def run_analysis(db: Session, submission: Submission) -> None:
    """Run the full pipeline for a submission whose front/back ScanImage
    rows are already populated. Persists AnalysisResult and
    GradingCompanyComparison rows and advances submission.status to
    draft_ready. Raises PipelineError on failure -- the caller is
    responsible for catching it and setting submission.status = error."""

    scans_by_side = {scan.side: scan for scan in submission.scan_images}
    front_scan = scans_by_side.get(ScanSide.front)
    back_scan = scans_by_side.get(ScanSide.back)
    if front_scan is None:
        raise PipelineError(f"Submission {submission.submission_code} has no front scan")

    submission.status = SubmissionStatus.processing
    db.flush()

    reports_dir = Path(config.reports_dir) / submission.submission_code

    # Physical card size drives the pixel->mm scale (see analysis/scale.py);
    # the image file's DPI metadata is meaningless for a phone photo.
    width_mm, height_mm = scale.dimensions_for(db, submission.card.game if submission.card else None)

    try:
        front = _load_deskewed_card(front_scan, width_mm, height_mm)
    except ValueError as exc:
        raise PipelineError(f"Front scan preprocessing failed: {exc}") from exc
    front_results = _persist_side(
        db,
        submission,
        reports_dir,
        ScanSide.front,
        front.image,
        # Exact, not inferred: the raster was built at this scale from the
        # card's known physical size, so it is no longer an average of two
        # axis measurements that a bad crop can pull apart.
        front.px_per_mm,
        front.geometry,
        front.limitations,
        front.mask,
    )

    back_results = None
    if back_scan is not None:
        try:
            back = _load_deskewed_card(back_scan, width_mm, height_mm)
        except ValueError as exc:
            raise PipelineError(f"Back scan preprocessing failed: {exc}") from exc
        back_results = _persist_side(
            db,
            submission,
            reports_dir,
            ScanSide.back,
            back.image,
            back.px_per_mm,
            back.geometry,
            back.limitations,
            back.mask,
        )

    _persist_combined(db, submission, front_results, back_results)
    db.flush()

    rules_engine.evaluate(db, submission)

    # A re-analysis (e.g. a late back scan) rebuilds every row from scratch;
    # re-apply any dismissals the client had already made so their
    # adjustments aren't silently lost. Region ids are stable across
    # re-analysis, so previously-dismissed keys still resolve.
    if submission.dismissed_regions:
        db.expire(submission, ["analysis_results", "company_comparisons"])
        recompute.recompute_submission(db, submission)

    submission.status = SubmissionStatus.draft_ready
    db.flush()
