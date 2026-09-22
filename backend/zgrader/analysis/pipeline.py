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
    artifacts,
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
    AuditLog,
    GradingCompanyComparison,
    ScanImage,
    ScanSide,
    Submission,
    SubmissionStatus,
)
from zgrader.models.settings import get_or_create_settings


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
    artifacts.save_derived(annotate.to_pil(card_image), reports_dir, f"{side.value}_base")

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
        # signatures to be used the same way in each. It never rescues a
        # reading -- it either devalues it or, when the boundary itself could
        # not be trusted, removes the score entirely. See
        # assessment.DISQUALIFYING_LIMITATIONS for why that is not merely a
        # harsher confidence factor.
        assessment.apply_external_limitations(result, geometry_limitations)
        if geometry is not None:
            # Unscored, and stored on every category because each one measures
            # from this boundary. The per-side residuals are what a later phase
            # turns into an edge-roughness channel.
            result["measurements"]["card_geometry"] = geometry
        image = _annotate_category(category, card_image, result, extra)
        image_path = artifacts.save_derived(image, reports_dir, f"{side.value}_{category.value}")

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
            artifacts.save_derived(
                crop, reports_dir, f"{side.value}_{category.value}_{region['id']}_crop"
            )

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
        measurements["assessment"] = assessment.combine_assessments(
            front_result["measurements"].get("assessment"),
            back_result["measurements"].get("assessment") if back_result else None,
        )

        combined_score = _combine_score(
            front_result["raw_score"], back_result["raw_score"] if back_result else None
        )
        # The score follows the assessment, never the other way round. Without
        # this, a card whose front could not be read but whose back could
        # would carry the back's number under a state of `unmeasurable` --
        # combine_front_back returns the one side that has a value, and it
        # does not know the merge above just refused to stand behind it.
        #
        # That contradiction shipped: SUB-00011 stored raw_score 7.45 next to
        # state "unmeasurable" on the same row. A number and a statement that
        # there is no number are not a pair of caveats, they are a bug.
        if (measurements["assessment"] or {}).get("state") != assessment.MEASURED:
            combined_score = None
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


def load_deskewed_card(
    scan: ScanImage,
    width_mm: float,
    height_mm: float,
    crop_points: list[list[float]] | None = None,
) -> preprocessing.RectifiedCard:
    """Rectify one scan to a canonical raster.

    The customer's crop points are passed as a region-of-interest hint, not as
    the card's geometry. This used to warp straight to them, which made every
    downstream measurement a function of where four handles were dragged: a
    crop half a millimetre inside the card removed the damage from the image
    before anything looked at it, and one half a millimetre outside put
    scanner backing where the card's edge should be. The crop still rejects
    background and neighbouring cards, which is what it is for.

    `crop_points` overrides what the scan has stored, which is how the
    pre-submission crop check asks "would this crop work?" without persisting
    anything. It shares this function rather than rebuilding the call because
    a check that computed geometry even slightly differently could pass a crop
    the pipeline then declines -- and a check that disagrees with the thing it
    is checking is worse than no check at all.
    """
    image = preprocessing.load_image(scan.file_path)
    points = crop_points if crop_points is not None else scan.crop_points
    roi = np.array(points, dtype="float32") if points is not None else None
    return preprocessing.rectify(image, width_mm, height_mm, roi_quad=roi)


def _revalidate_centering_adjustments(db: Session, submission: Submission) -> None:
    """Drop any stored centering adjustment or placement that no longer fits
    the freshly persisted per-side centering rows, auditing each drop.

    A re-analysis rebuilds every per-side row from scratch, and a stored
    adjustment was validated against the *previous* one -- the border may now
    be detected where it wasn't, or lost where it was. Revalidating through
    `recompute.check_centering_adjustment`, the same check the endpoint runs
    on a proposed move, means a placement a fresh detection now covers
    survives as a nudge, and a nudge on a side that now declined survives as
    a placement, each within its own bound; only a widths set that fits
    neither mode is dropped. Without this, re-analysis could leave a
    placement's widths read back through the nudge branch of
    `recompute._adjusted_side_score` uncapped and unlabelled -- a 4mm cap
    ignored on a reading nobody flagged as placed by hand.

    The nudge cap is not enforced here when `centering_adjust_limit_mm` is 0:
    the kill switch means "refuse anything new," not "invalidate everything
    already stored" (see the setting's own comment). The placement bound,
    eligibility and scale are always enforced -- those aren't the kill
    switch's business.
    """
    adjustments = submission.centering_adjustments or {}
    if not adjustments:
        return

    settings = get_or_create_settings(db)
    limit_mm = float(settings.centering_adjust_limit_mm or 0)
    rows = {
        row.side.value: row
        for row in submission.analysis_results
        if row.category == AnalysisCategory.centering and row.side != AnalysisSide.combined
    }

    remaining = dict(adjustments)
    for side, widths in adjustments.items():
        row = rows.get(side)
        if row is None:
            remaining.pop(side, None)
            db.add(
                AuditLog(
                    submission_id=submission.id,
                    user_id=None,
                    action="centering_adjustment_dropped",
                    detail={"side": side, "reason": "no_row"},
                )
            )
            continue
        _mode, reason = recompute.check_centering_adjustment(
            row.measurements or {},
            row.raw_score is not None,
            widths,
            limit_mm,
            enforce_nudge_cap=limit_mm > 0,
        )
        if reason is not None:
            remaining.pop(side, None)
            db.add(
                AuditLog(
                    submission_id=submission.id,
                    user_id=None,
                    action="centering_adjustment_dropped",
                    detail={"side": side, "reason": reason},
                )
            )

    # A new dict, so SQLAlchemy tracks the JSONB change even when nothing was
    # dropped and the contents happen to compare equal.
    submission.centering_adjustments = remaining or None


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
        front = load_deskewed_card(front_scan, width_mm, height_mm)
    except ValueError as exc:
        raise PipelineError(f"Front scan preprocessing failed: {exc}") from exc
    # Foil is a property of the card, not of either photograph, so it joins
    # the geometry limitations rather than being re-derived per side.
    #
    # **Taken from the customer's declaration, not detected.** Detecting it
    # from the image was tried and rejected on measurement: clipped-highlight
    # density looked decisive on per-card averages -- foil cards 5.6-9.1% of
    # the face against 0.6-2.8% for plain ones -- but per photograph it
    # overlaps badly. A plain card under high glare reads 10.7%, above most
    # foil shots, while a foil card in flat light reads 0.4%. Clipping cannot
    # separate foil from glare in a single frame, and local variance and
    # sparkle density do not separate at all: plain cards score the same or
    # higher on both.
    #
    # So the reliable signal is the one already in the database and never read
    # until now. Card.foil has been a declared field the analysis ignored.
    card_limitations = (
        (assessment.CARD_IS_FOIL,)
        if submission.card is not None and submission.card.foil
        else ()
    )

    # A re-analysis replaces the previous assessment rather than adding to it.
    #
    # Nothing here upserts -- _persist_side and rules_engine.evaluate both
    # insert fresh rows -- so without this a rerun leaves two complete sets
    # behind. One production submission accumulated three. It reads as storage
    # growth rather than wrong numbers only because every consumer happens to
    # take the newest; anything that aggregated instead would multiply-count
    # silently.
    #
    # This used to live in the caller, guarded by `status == draft_ready`, so
    # only one of the several ways to re-run analysis actually cleaned up:
    # dev_trigger never did, and neither did a rerun from the error state.
    # Doing it here means every caller gets it by construction, which is the
    # only version that stays true.
    #
    # Placed after the front raster loaded successfully, so a scan that cannot
    # be preprocessed raises PipelineError with the previous assessment still
    # intact -- the caller commits `status = error`, and that commit would
    # otherwise make the deletion permanent.
    db.query(AnalysisResult).filter(
        AnalysisResult.submission_id == submission.id
    ).delete(synchronize_session=False)
    db.query(GradingCompanyComparison).filter(
        GradingCompanyComparison.submission_id == submission.id
    ).delete(synchronize_session=False)
    # A bulk delete goes round the identity map, so these collections would
    # still hand out rows that no longer exist -- and both _persist_combined
    # and rules_engine.evaluate read them.
    db.expire(submission, ["analysis_results", "company_comparisons"])

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
        front.limitations + card_limitations,
        front.mask,
    )

    back_results = None
    if back_scan is not None:
        try:
            back = load_deskewed_card(back_scan, width_mm, height_mm)
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
            back.limitations + card_limitations,
            back.mask,
        )

    _persist_combined(db, submission, front_results, back_results)
    db.flush()

    rules_engine.evaluate(db, submission)

    # A re-analysis (e.g. a late back scan) rebuilds every row from scratch;
    # re-apply any dismissals and centering adjustments/placements the client
    # had already made so they aren't silently lost. Region ids are stable
    # across re-analysis, so previously-dismissed keys still resolve. Centering
    # adjustments are revalidated against the fresh per-side rows first --
    # `_revalidate_centering_adjustments` -- and anything that no longer fits
    # either bound is dropped and audited rather than re-scored against a row
    # it was never checked against. Without this, a re-analysis could turn a
    # capped, labelled placement into an uncapped, unlabelled detected reading:
    # the combined row is derived below.
    _revalidate_centering_adjustments(db, submission)
    if submission.dismissed_regions or submission.centering_adjustments:
        db.expire(submission, ["analysis_results", "company_comparisons"])
        recompute.recompute_submission(db, submission)

    submission.status = SubmissionStatus.draft_ready
    db.flush()
