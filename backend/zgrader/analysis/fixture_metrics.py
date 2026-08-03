"""Run the analysis pipeline over one image and flatten the result.

Shared by the drift harness (scripts/fixture_drift.py) and the test that gives
it teeth (tests/test_fixture_drift.py), so the two can never disagree about
what "the metrics" are.

Deliberately does not touch the database, the filesystem or the region/crop
machinery. It measures what the detectors compute, which is the thing that
moves when someone retunes a threshold -- everything downstream of that is
already covered by its own tests.
"""

import numpy as np

from zgrader.analysis import centering, corners, edges, preprocessing, surface

# Rounded before comparison. Small enough to catch a real retune, loose enough
# that a different OpenCV or BLAS build doesn't produce phantom drift on the
# last float bit.
PRECISION = 3


def _round(value: float) -> float:
    return round(float(value), PRECISION)


def measure_image(image: np.ndarray, width_mm: float, height_mm: float) -> dict[str, float]:
    """Every number the four analysers produce for one card, flattened.

    Flat rather than nested so a diff can name exactly what moved --
    "corners.per_corner.top_left.whitening_score" is a useful failure message;
    "corners changed" is not.
    """
    # The same entry point the pipeline uses, so the harness measures what
    # ships. No roi_quad: a fixture has no customer crop, and passing one would
    # test the hint path rather than detection.
    rectified = preprocessing.rectify(image, width_mm, height_mm)
    card = rectified.image
    px_per_mm = rectified.px_per_mm

    metrics: dict[str, float] = {
        "px_per_mm": _round(px_per_mm),
        "card_height_px": float(card.shape[0]),
        "card_width_px": float(card.shape[1]),
        # Geometry drifts before scores do -- a change to the edge fit shows up
        # here as a moved apex or a changed roughness long before it has moved
        # a category score enough to notice.
        "geometry.fitted": float(rectified.geometry["method"] == "ransac"),
        "geometry.aspect_deviation": _round(rectified.geometry["aspect_deviation"]),
        "geometry.limitation_count": float(len(rectified.limitations)),
    }
    for name, side in sorted(rectified.geometry.get("sides", {}).items()):
        metrics[f"geometry.{name}.inlier_fraction"] = _round(side["inlier_fraction"])
        metrics[f"geometry.{name}.roughness_px"] = _round(side["roughness_px"])
        metrics[f"geometry.{name}.max_excursion_px"] = _round(side["max_excursion_px"])
        metrics[f"geometry.{name}.bow_px"] = _round(side["bow_px"])

    def _record_assessment(prefix: str, result: dict) -> None:
        """Confidence and the interval are customer-visible claims, so drift in
        them matters as much as drift in the score itself. Limitation codes are
        captured as a count -- the codes are asserted directly in
        test_assessment.py, and a count is enough here to catch one appearing
        or vanishing."""
        block = result["measurements"].get("assessment")
        if block is None:
            return
        metrics[f"{prefix}.confidence"] = _round(block["confidence"])
        metrics[f"{prefix}.unmeasurable"] = float(block["state"] != "measured")
        metrics[f"{prefix}.limitation_count"] = float(len(block["limitations"]))
        if block["score_low"] is not None:
            metrics[f"{prefix}.score_low"] = _round(block["score_low"])
            metrics[f"{prefix}.score_high"] = _round(block["score_high"])

    cen = centering.measure_centering(card, px_per_mm)
    # Unmeasurable centering has no score and no top-level ratio -- the reading
    # moves under `indicative_estimate`, which is measured here too so that a
    # change in the estimate still shows as drift even though it is
    # non-binding.
    cen_reading = cen["measurements"].get("indicative_estimate", cen["measurements"])
    if cen["raw_score"] is not None:
        metrics["centering.raw_score"] = _round(cen["raw_score"])
    metrics["centering.worse_side_pct"] = _round(cen_reading["worse_side_pct"])
    metrics["centering.lr_left_pct"] = _round(cen_reading["lr_ratio"][0])
    metrics["centering.tb_top_pct"] = _round(cen_reading["tb_ratio"][0])
    # A flag is a customer-visible claim about reliability, so drift in it
    # matters as much as drift in a number.
    metrics["centering.lower_confidence"] = float(
        bool(cen["flags"].get("lower_confidence", False))
    )

    _record_assessment("centering", cen)

    cor = corners.measure_corners(card, px_per_mm=px_per_mm)
    # Corners and edges can now decline to score on a capture too small for
    # the wear to exist in. The per-corner/per-edge numbers are still computed
    # and still tracked -- they are the diagnostics a later retune gets
    # compared against -- but there is no category score to record.
    if cor["raw_score"] is not None:
        metrics["corners.raw_score"] = _round(cor["raw_score"])
    for name, info in cor["measurements"]["per_corner"].items():
        metrics[f"corners.{name}.combined_score"] = _round(info["combined_score"])
        metrics[f"corners.{name}.whitening_score"] = _round(info["whitening_score"])

    _record_assessment("corners", cor)

    edg = edges.measure_edges(card, px_per_mm=px_per_mm)
    if edg["raw_score"] is not None:
        metrics["edges.raw_score"] = _round(edg["raw_score"])
    for name, info in edg["measurements"]["per_edge"].items():
        if info.get("score") is None:
            continue
        metrics[f"edges.{name}.score"] = _round(info["score"])
        metrics[f"edges.{name}.whitened_fraction"] = _round(info["whitened_fraction"])

    _record_assessment("edges", edg)

    sur, _mask = surface.measure_surface(card)
    metrics["surface.raw_score"] = _round(sur["raw_score"])
    metrics["surface.anomaly_fraction"] = _round(sur["measurements"]["anomaly_fraction"])

    _record_assessment("surface", sur)

    return metrics


# Note there is deliberately no `measure_fixture(name)` here. Building a
# fixture needs tests/fixtures/generate_samples.py, and this module ships
# inside the package -- importing test code from it would put the test tree on
# the runtime dependency path. The harness in scripts/fixture_drift.py joins
# the two instead.
