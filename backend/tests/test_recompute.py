"""Unit tests for the per-side score re-aggregation that powers client
dismissals (zgrader.analysis.recompute._adjusted_side_score). The full
DB-level recompute + rules-engine rerun is exercised end-to-end through the
toggle endpoint in test_api_submissions.py."""

import tempfile

import cv2
import pytest

from tests.fixtures.generate_samples import make_card_scan
from zgrader.analysis import (
    centering,
    corners,
    edges,
    preprocessing,
    recompute,
    regions,
    scale,
    surface,
)
from zgrader.models import AnalysisCategory


@pytest.fixture(scope="module")
def analyzed_side():
    """Real analyzer output for one side, shaped the way pipeline._persist_side
    stores it -- measurements with a "regions" list injected."""
    scan = make_card_scan(63.0, 88.0, lr_offset_frac=0.3, whiten_top_left_corner=True)
    fd, path = tempfile.mkstemp(suffix=".png")
    cv2.imwrite(path, scan)
    card, _info = preprocessing.locate_and_deskew(preprocessing.load_image(path))
    ppm = scale.px_per_mm(card.shape[:2], 63.0, 88.0)

    surface_result, mask = surface.measure_surface(card)
    built = {
        AnalysisCategory.centering: (centering.measure_centering(card, ppm), None),
        AnalysisCategory.corners: (corners.measure_corners(card), None),
        AnalysisCategory.edges: (edges.measure_edges(card), None),
        AnalysisCategory.surface: (surface_result, mask),
    }
    for category, (result, extra) in built.items():
        result["measurements"]["regions"] = regions.build_regions(
            category, card.shape[:2], ppm, "en", result, extra
        )
    return {category.value: result for category, (result, _e) in built.items()}


@pytest.mark.parametrize("category", ["centering", "corners", "edges", "surface"])
def test_no_dismissals_reproduces_the_pipeline_score_exactly(analyzed_side, category):
    """Dismissing nothing, then restoring, must land back on the number the
    pipeline computed -- recompute re-derives each side's score from stored
    measurements rather than reading it back, so the two derivations have to
    agree for every category."""
    result = analyzed_side[category]
    score, _worse = recompute._adjusted_side_score(category, result["measurements"], set())
    assert score == pytest.approx(result["raw_score"], abs=0.01)


def test_corners_dismissing_the_bad_corner_raises_the_side_score():
    side_m = {
        "regions": [
            {"id": "top_left", "score": 2.0},
            {"id": "top_right", "score": 10.0},
            {"id": "bottom_left", "score": 10.0},
            {"id": "bottom_right", "score": 10.0},
        ]
    }
    before, _ = recompute._adjusted_side_score("corners", side_m, set())
    after, _ = recompute._adjusted_side_score("corners", side_m, {"top_left"})

    # Worst-anchored, not averaged: half the weight sits on the worst corner
    # and half on the mean of all four. A plain mean gave 8.0 here, letting
    # three clean corners hide a badly damaged one.
    assert before == 5.0  # 0.5*2 + 0.5*mean(2,10,10,10)
    assert after == 10.0  # the three kept corners are all 10
    assert after > before


def test_edges_all_dismissed_does_not_award_a_perfect_score():
    """Disputing every finding is a claim the detector was wrong, not evidence
    the card is flawless. This used to return 10.0 -- and the cards with every
    region flagged are the most damaged ones, so it handed perfect scores to
    exactly the worst cards. `None` means "keep the measurement"."""
    side_m = {"regions": [{"id": "top", "score": 3.0}, {"id": "left", "score": 4.0}]}
    score, _ = recompute._adjusted_side_score("edges", side_m, {"top", "left"})
    assert score is None


def test_edges_partial_dismissal_still_excludes_the_disputed_finding():
    side_m = {"regions": [{"id": "top", "score": 3.0}, {"id": "left", "score": 9.0}]}
    score, _ = recompute._adjusted_side_score("edges", side_m, {"top"})
    assert score == 9.0


def test_centering_dismissing_frame_keeps_the_measured_ratio():
    """Centering has a single region, so dismissing it leaves nothing to
    re-aggregate. It used to assert a perfect 50/50 cut on the client's say-so;
    the measured ratio now stands and the dispute is recorded separately."""
    side_m = {"worse_side_pct": 68.0, "regions": [{"id": "frame", "score": 6.4}]}
    kept_score, kept_worse = recompute._adjusted_side_score("centering", side_m, set())
    adj_score, adj_worse = recompute._adjusted_side_score("centering", side_m, {"frame"})

    assert kept_worse == 68.0 and kept_score < 8.0
    assert adj_score is None and adj_worse is None


def test_surface_dismissing_a_blob_subtracts_its_area_fraction():
    side_m = {
        "anomaly_fraction": 0.02,
        "regions": [
            {"id": "blob_0", "area_fraction": 0.01},
            {"id": "blob_1", "area_fraction": 0.005},
        ],
    }
    before, _ = recompute._adjusted_side_score("surface", side_m, set())
    after, _ = recompute._adjusted_side_score("surface", side_m, {"blob_0"})

    # score = 10 - anomaly_fraction*200
    assert before == round(10.0 - 0.02 * 200, 2)  # 6.0
    assert after == round(10.0 - (0.02 - 0.01) * 200, 2)  # 8.0
    assert after > before


def test_centering_with_nothing_measured_leaves_the_stored_score_alone():
    """Absent data used to be re-aggregated as 10.0, inventing a perfect score
    out of nothing. `None` now means "no adjustment derivable -- keep what the
    pipeline stored"."""
    score, worse = recompute._adjusted_side_score("centering", {"regions": []}, set())
    assert score is None
    assert worse is None


def test_unknown_category_leaves_the_stored_score_alone():
    score, worse = recompute._adjusted_side_score("something_new", {"regions": []}, set())
    assert score is None
    assert worse is None


def test_parse_dismissed_groups_by_side_and_category():
    parsed = recompute._parse_dismissed(
        ["front:corners:top_left", "front:corners:top_right", "back:surface:blob_0", "bad_key"]
    )
    assert parsed[("front", "corners")] == {"top_left", "top_right"}
    assert parsed[("back", "surface")] == {"blob_0"}
    assert ("bad", "key") not in parsed
