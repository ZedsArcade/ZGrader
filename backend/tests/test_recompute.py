"""Unit tests for the per-side score re-aggregation that powers client
dismissals (zgrader.analysis.recompute._adjusted_side_score). The full
DB-level recompute + rules-engine rerun is exercised end-to-end through the
toggle endpoint in test_api_submissions.py."""

from zgrader.analysis import recompute


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

    assert before == 8.0  # mean(2,10,10,10)
    assert after == 10.0  # mean of the three kept 10s
    assert after > before


def test_edges_all_dismissed_falls_back_to_clean():
    side_m = {"regions": [{"id": "top", "score": 3.0}, {"id": "left", "score": 4.0}]}
    score, _ = recompute._adjusted_side_score("edges", side_m, {"top", "left"})
    assert score == 10.0


def test_centering_dismissing_frame_forces_perfect_centering():
    side_m = {"worse_side_pct": 68.0, "regions": [{"id": "frame", "score": 6.4}]}
    kept_score, kept_worse = recompute._adjusted_side_score("centering", side_m, set())
    adj_score, adj_worse = recompute._adjusted_side_score("centering", side_m, {"frame"})

    assert kept_worse == 68.0 and kept_score < 8.0
    assert adj_worse == 50.0 and adj_score == 10.0


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


def test_parse_dismissed_groups_by_side_and_category():
    parsed = recompute._parse_dismissed(
        ["front:corners:top_left", "front:corners:top_right", "back:surface:blob_0", "bad_key"]
    )
    assert parsed[("front", "corners")] == {"top_left", "top_right"}
    assert parsed[("back", "surface")] == {"blob_0"}
    assert ("bad", "key") not in parsed
