"""Orchestrates the full per-submission analysis pipeline: preprocess each
scan, run centering/corners/edges/surface on front and back, persist
per-side and combined AnalysisResult rows with annotated images, then hand
off to the multi-company rules engine.
"""

from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from zgrader.analysis import annotate, centering, corners, edges, preprocessing, rules_engine, surface
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


def _analyze_centering(card_image: np.ndarray, dpi: int) -> tuple[dict, None]:
    return centering.measure_centering(card_image, dpi), None


def _analyze_corners(card_image: np.ndarray, dpi: int) -> tuple[dict, None]:
    return corners.measure_corners(card_image), None


def _analyze_edges(card_image: np.ndarray, dpi: int) -> tuple[dict, None]:
    return edges.measure_edges(card_image), None


_ANALYZERS = {
    AnalysisCategory.centering: _analyze_centering,
    AnalysisCategory.corners: _analyze_corners,
    AnalysisCategory.edges: _analyze_edges,
    AnalysisCategory.surface: lambda card_image, dpi: surface.measure_surface(card_image),
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


def _persist_side(
    db: Session,
    submission: Submission,
    reports_dir: Path,
    side: ScanSide,
    card_image: np.ndarray,
    dpi: int,
) -> dict[AnalysisCategory, dict]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    results: dict[AnalysisCategory, dict] = {}

    for category, analyzer in _ANALYZERS.items():
        result, extra = analyzer(card_image, dpi)
        image = _annotate_category(category, card_image, result, extra)
        image_path = reports_dir / f"{side.value}_{category.value}.png"
        image.save(image_path)

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

        db.add(
            AnalysisResult(
                submission_id=submission.id,
                category=category,
                side=AnalysisSide.combined,
                raw_score=_combine_score(
                    front_result["raw_score"], back_result["raw_score"] if back_result else None
                ),
                measurements=measurements,
                annotated_image_path=None,
                flags=flags,
            )
        )


def _load_deskewed_card(scan: ScanImage) -> np.ndarray:
    image = preprocessing.load_image(scan.file_path)
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

    try:
        front_card = _load_deskewed_card(front_scan)
    except ValueError as exc:
        raise PipelineError(f"Front scan preprocessing failed: {exc}") from exc
    front_results = _persist_side(db, submission, reports_dir, ScanSide.front, front_card, front_scan.dpi)

    back_results = None
    if back_scan is not None:
        try:
            back_card = _load_deskewed_card(back_scan)
        except ValueError as exc:
            raise PipelineError(f"Back scan preprocessing failed: {exc}") from exc
        back_results = _persist_side(db, submission, reports_dir, ScanSide.back, back_card, back_scan.dpi)

    _persist_combined(db, submission, front_results, back_results)
    db.flush()

    rules_engine.evaluate(db, submission)
    submission.status = SubmissionStatus.draft_ready
    db.flush()
