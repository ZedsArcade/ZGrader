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
    centering,
    corners,
    creases,
    edges,
    preprocessing,
    recompute,
    regions,
    rules_engine,
    scale,
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


def _analyze_centering(card_image: np.ndarray, px_per_mm: float) -> tuple[dict, None]:
    return centering.measure_centering(card_image, px_per_mm), None


def _analyze_corners(card_image: np.ndarray, px_per_mm: float) -> tuple[dict, None]:
    return corners.measure_corners(card_image), None


def _analyze_edges(card_image: np.ndarray, px_per_mm: float) -> tuple[dict, None]:
    return edges.measure_edges(card_image), None


_ANALYZERS = {
    AnalysisCategory.centering: _analyze_centering,
    AnalysisCategory.corners: _analyze_corners,
    AnalysisCategory.edges: _analyze_edges,
    AnalysisCategory.surface: lambda card_image, px_per_mm: surface.measure_surface(card_image),
}


def _annotate_category(category: AnalysisCategory, card_image: np.ndarray, result: dict, extra):
    if category == AnalysisCategory.centering:
        return annotate.annotate_centering(card_image, result["measurements"])
    if category == AnalysisCategory.corners:
        return annotate.annotate_corners(card_image, result["measurements"]["per_corner"])
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
        result, extra = analyzer(card_image, px_per_mm)
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


def _combine_score(front_score: float, back_score: float | None) -> float:
    if back_score is None:
        return front_score
    return round((front_score + back_score) / 2, 2)


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
            if front_worse is not None and back_worse is not None:
                measurements["worse_side_pct"] = round((front_worse + back_worse) / 2, 1)
            elif front_worse is not None:
                measurements["worse_side_pct"] = front_worse
            if "worse_side_pct" in measurements:
                measurements["original_worse_side_pct"] = measurements["worse_side_pct"]

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


def _load_deskewed_card(scan: ScanImage) -> np.ndarray:
    image = preprocessing.load_image(scan.file_path)
    if scan.crop_points is not None:
        points = np.array(scan.crop_points, dtype="float32")
        return preprocessing.warp_to_points(image, points)
    # Only reachable if boundary auto-detection failed at registration/
    # migration-backfill time and crop_points stayed NULL -- run_analysis is
    # otherwise only invoked once _advance_submission has confirmed this
    # side via Submission.confirmed_sides, so crop_points is normally
    # always set by this point.
    card_image, _info = preprocessing.locate_and_deskew(image)
    return card_image


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
        front_card = _load_deskewed_card(front_scan)
    except ValueError as exc:
        raise PipelineError(f"Front scan preprocessing failed: {exc}") from exc
    front_results = _persist_side(
        db,
        submission,
        reports_dir,
        ScanSide.front,
        front_card,
        scale.px_per_mm(front_card.shape[:2], width_mm, height_mm),
    )

    back_results = None
    if back_scan is not None:
        try:
            back_card = _load_deskewed_card(back_scan)
        except ValueError as exc:
            raise PipelineError(f"Back scan preprocessing failed: {exc}") from exc
        back_results = _persist_side(
            db,
            submission,
            reports_dir,
            ScanSide.back,
            back_card,
            scale.px_per_mm(back_card.shape[:2], width_mm, height_mm),
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
