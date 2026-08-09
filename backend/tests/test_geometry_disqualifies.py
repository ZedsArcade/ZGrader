"""A category must not score off a boundary that could not be verified.

Why this file exists rather than a drift-baseline entry: none of the 23
synthetic fixtures trigger the geometry fallback. Every one of them fits
cleanly with zero limitations, so `scripts/fixture_drift.py` cannot exercise
this branch at all and its baseline does not move when the behaviour changes.
The failure it guards against was found on real photographs -- 10 of 30 fell
back, and on those the mean corners score was 9.04 against 7.79 where the fit
held, because a desk has no corner wear.
"""

from unittest.mock import patch

import numpy as np
import pytest

from zgrader.analysis import assessment, fixture_metrics, preprocessing


def _result(score: float | None, confidence: float, limitations=()) -> dict:
    """A finished category result, shaped like the analysers return."""
    block = (
        assessment.measured(score, confidence, tuple(limitations))
        if score is not None
        else assessment.unmeasurable(tuple(limitations))
    )
    return {"raw_score": score, "measurements": {"assessment": block.as_dict()}, "flags": {}}


# --- the disqualifying branch ------------------------------------------


def test_unverified_geometry_removes_the_score():
    """The point of the change. A halved confidence on a 10.00 is still a
    published 10.00, and the error is biased upward -- every one of these
    failures flatters the card."""
    result = _result(10.0, 0.8)

    assessment.apply_external_limitations(result, (assessment.GEOMETRY_UNVERIFIED,))

    assert result["raw_score"] is None
    block = result["measurements"]["assessment"]
    assert block["state"] == assessment.UNMEASURABLE
    assert block["confidence"] == 0.0
    # An interval implies a score exists somewhere inside it, which is exactly
    # the claim being declined.
    assert block["score_low"] is None and block["score_high"] is None
    assert assessment.GEOMETRY_UNVERIFIED in block["limitations"]


def test_reasons_the_category_already_had_are_kept():
    """The geometry failure is added to why the reading is poor, not
    substituted for it -- the operator still needs the whole picture."""
    result = _result(7.0, 0.55, (assessment.CORNERS_WHITENING_ONLY,))

    assessment.apply_external_limitations(result, (assessment.GEOMETRY_UNVERIFIED,))

    codes = result["measurements"]["assessment"]["limitations"]
    assert assessment.CORNERS_WHITENING_ONLY in codes
    assert assessment.GEOMETRY_UNVERIFIED in codes


def test_an_already_declining_category_stays_declining():
    result = _result(None, 0.0, (assessment.CENTERING_NO_FRAME,))

    assessment.apply_external_limitations(result, (assessment.GEOMETRY_UNVERIFIED,))

    assert result["raw_score"] is None
    codes = result["measurements"]["assessment"]["limitations"]
    assert assessment.CENTERING_NO_FRAME in codes
    assert assessment.GEOMETRY_UNVERIFIED in codes


# --- everything else still only devalues -------------------------------


def test_foil_devalues_but_keeps_the_score():
    """Foil makes every reading worth less; it does not make the card
    unmeasurable. Disqualifying on it would refuse every holo submission."""
    result = _result(8.0, 0.8)

    assessment.apply_external_limitations(result, (assessment.CARD_IS_FOIL,))

    assert result["raw_score"] == 8.0
    block = result["measurements"]["assessment"]
    assert block["state"] == assessment.MEASURED
    assert block["confidence"] == pytest.approx(0.8 * assessment.CONFIDENCE_FOIL_FACTOR, abs=0.01)


def test_aspect_mismatch_devalues_but_keeps_the_score():
    """Deliberately not disqualifying: a wrong millimetre scale damages the
    physical quantities but leaves ratios intact. Different failure, and one
    nobody has measured the way the fallback was measured."""
    result = _result(8.0, 0.8)

    assessment.apply_external_limitations(result, (assessment.GEOMETRY_ASPECT_MISMATCH,))

    assert result["raw_score"] == 8.0
    assert result["measurements"]["assessment"]["state"] == assessment.MEASURED


def test_no_codes_changes_nothing():
    result = _result(9.0, 0.9)
    assessment.apply_external_limitations(result, ())
    assert result["raw_score"] == 9.0
    assert result["measurements"]["assessment"]["state"] == assessment.MEASURED


# --- the harness and production must agree -----------------------------


def test_fixture_metrics_applies_it_too(sample_scan_paths):
    """The drift harness has to see what production sees.

    Before this, fixture_metrics scored a fallback-geometry card as though the
    fit had succeeded, so the harness measured a pipeline that does not ship.
    Invisible on the synthetic set -- all 23 fit -- and wrong on a third of
    real photographs.
    """
    import cv2

    image = cv2.imread(str(sample_scan_paths["pokemon_front"]))
    real = preprocessing.rectify(image, 63.0, 88.0)

    # Same rectification, but reported as unverified. Patching the limitation
    # rather than feeding a deliberately awful image keeps the test about the
    # wiring instead of about detection's failure modes.
    forced = preprocessing.RectifiedCard(
        real.image,
        real.px_per_mm,
        real.geometry,
        (assessment.GEOMETRY_UNVERIFIED,),
        real.mask,
    )

    with patch.object(preprocessing, "rectify", return_value=forced):
        metrics = fixture_metrics.measure_image(image, 63.0, 88.0)

    scored = [k for k in metrics if k.endswith(".raw_score")]
    assert scored == [], f"these still scored off an unverified boundary: {scored}"

    for category in ("centering", "corners", "edges", "surface"):
        assert metrics[f"{category}.unmeasurable"] == 1.0, f"{category} did not decline"


def test_a_clean_fit_still_scores(sample_scan_paths):
    """The guard against over-correcting: a fixture that fits must be
    unaffected, or the change trades one wrongness for another."""
    import cv2

    image = cv2.imread(str(sample_scan_paths["pokemon_front"]))
    metrics = fixture_metrics.measure_image(image, 63.0, 88.0)

    assert metrics["geometry.fitted"] == 1.0
    assert metrics["geometry.limitation_count"] == 0.0
    assert "corners.raw_score" in metrics
    assert "edges.raw_score" in metrics
