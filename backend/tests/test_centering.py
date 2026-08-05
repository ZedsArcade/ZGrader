import tempfile

import cv2
import pytest

from tests.fixtures.generate_samples import make_card_scan
from zgrader.analysis import assessment, centering, preprocessing


def _deskewed(**kwargs):
    scan = make_card_scan(63.0, 88.0, **kwargs)
    fd, path = tempfile.mkstemp(suffix=".png")
    cv2.imwrite(path, scan)
    image = preprocessing.load_image(path)
    card_image, _info = preprocessing.locate_and_deskew(image)
    return card_image


def test_centered_card_scores_near_perfect():
    card_image = _deskewed()
    result = centering.measure_centering(card_image, px_per_mm=600 / 25.4)
    assert result["measurements"]["lr_ratio"][0] == pytest.approx(50.0, abs=1.0)
    assert result["measurements"]["tb_ratio"][0] == pytest.approx(50.0, abs=1.0)
    assert result["raw_score"] >= 9.5


def test_off_center_card_measures_expected_split():
    # lr_offset_frac=0.3 with a symmetric base border produces a
    # left:right ratio of 1.3 : 0.7 -> 65.0 / 35.0
    card_image = _deskewed(lr_offset_frac=0.3)
    result = centering.measure_centering(card_image, px_per_mm=600 / 25.4)
    lr_ratio = result["measurements"]["lr_ratio"]
    assert lr_ratio[0] == pytest.approx(65.0, rel=0.05)
    assert lr_ratio[1] == pytest.approx(35.0, rel=0.05)
    assert result["measurements"]["worse_side_pct"] == pytest.approx(65.0, rel=0.05)


def test_worse_centering_scores_lower_than_better_centering():
    mild = centering.measure_centering(_deskewed(lr_offset_frac=0.1), px_per_mm=600 / 25.4)
    severe = centering.measure_centering(_deskewed(lr_offset_frac=0.4), px_per_mm=600 / 25.4)
    assert severe["raw_score"] < mild["raw_score"]


def test_clean_card_is_measured_with_confidence():
    # A synthetic card has a crisp printed border on every side, so the
    # centering measurement must NOT be flagged lower_confidence.
    result = centering.measure_centering(_deskewed(), px_per_mm=600 / 25.4)
    assert not result["flags"].get("lower_confidence")


def test_borderless_image_is_flagged_lower_confidence():
    import numpy as np

    # Uniform noise with no printed border anywhere -- the argmax edge on
    # each side is just noise, so no side clears the significance bar and
    # the result must be flagged lower_confidence rather than asserting a
    # confident (and meaningless) split.
    rng = np.random.default_rng(0)
    noise = rng.integers(90, 160, size=(800, 600, 3), dtype=np.uint8)
    result = centering.measure_centering(noise, px_per_mm=600 / 25.4)
    assert result["flags"].get("lower_confidence") is True


# --- Phase 4: the fitted inner frame -----------------------------------------


def _rectified(name: str):
    from tests.fixtures.generate_samples import build_fixture, card_size_mm

    card = preprocessing.rectify(build_fixture(name), *card_size_mm(name))
    return centering.measure_centering(card.image, card.px_per_mm)


def test_a_diamond_cut_is_caught_even_though_the_ratio_looks_perfect():
    """The measurement a per-side median structurally cannot make.

    The fixture is printed straight and trimmed at an angle, so its border
    widens down one side and narrows down the other by the same amount. The
    left/right split therefore averages out to very nearly 50/50 -- a card
    that reads as perfectly centred while being visibly skewed. Graders
    penalise it separately, and the only way to see it is to ask whether the
    border runs *parallel* to the cut.
    """
    result = _rectified("centering_diamond_cut")
    reading = result["measurements"]

    assert max(reading["lr_ratio"]) < 52.0, "the ratio should look almost perfect"
    assert reading["tilt_mm"] > 0.5, "the tilt is the whole defect and must be seen"
    # Measured and reported, not scored -- see scoring.CENTERING_TILT_SCORED.
    # Real photographs put about 1.2mm of noise on this measurement, which is
    # wider than the whole range it was being scored over, so the score was
    # largely reporting which photograph had been taken.
    assert result["raw_score"] is not None


def test_opposite_sides_tilt_in_opposite_directions():
    """The signature of a rotation rather than a measurement artefact: if the
    print is turned relative to the cut, one side's border grows exactly as the
    facing side's shrinks."""
    per_side = _rectified("centering_diamond_cut")["measurements"]["per_side"]
    assert per_side["left"]["tilt_mm"] * per_side["right"]["tilt_mm"] < 0


def test_border_widths_agree_with_what_edges_measured_independently():
    """Both categories go through analysis/border.py, so this is a check that
    the shared routine is used consistently rather than two estimators
    coincidentally agreeing -- which is exactly why it was extracted."""
    from tests.fixtures.generate_samples import build_fixture, card_size_mm
    from zgrader.analysis import edges

    card = preprocessing.rectify(build_fixture("pokemon_front"), *card_size_mm("pokemon_front"))
    cen = centering.measure_centering(card.image, card.px_per_mm)["measurements"]
    edg = edges.measure_edges(card.image, px_per_mm=card.px_per_mm, geometry=card.geometry)

    for side in ("left", "right", "top", "bottom"):
        assert cen[f"{side}_mm"] == pytest.approx(
            edg["measurements"]["per_edge"][side]["border_width_mm"], abs=0.05
        ), f"{side} disagrees between centering and edges"


def test_a_missing_side_drops_its_axis_instead_of_reading_as_100_0():
    """The bug this nearly shipped with.

    An unmeasured side left its width at zero, so the pair read as a 100/0
    split and centering scored a confident 0.0 -- a catastrophic reading
    manufactured from a measurement that never happened, on a card whose other
    three borders were fine. An incomplete axis now contributes nothing.
    """
    result = _rectified("capture_worst_case")
    per_side = result["measurements"]["per_side"]

    assert any(not s.get("measured") for s in per_side.values()), (
        "fixture no longer exercises a missing side"
    )
    assert result["measurements"]["measured_axes"] == 1
    assert result["raw_score"] > 5.0, "a single missing side must not zero the category"
    assert (
        assessment.CENTERING_PARTIAL_FRAME
        in result["measurements"]["assessment"]["limitations"]
    )


def test_foil_still_gets_a_width_even_though_its_frame_cannot_be_fitted():
    """A holo card has a perfectly real printed border. The per-position
    transitions scatter across the pattern, so the line fit is declined -- but
    the whole-edge median still finds the border, and refusing to measure
    something measurable is as much a failure as measuring it badly."""
    result = _rectified("foil_bordered")
    per_side = result["measurements"]["per_side"]

    assert result["raw_score"] is not None
    assert all(s["measured"] for s in per_side.values())
    assert not any(s.get("fitted") for s in per_side.values())
    assert result["measurements"]["tilt_mm"] == 0.0, "no tilt claim from a scattered fit"


def test_a_full_art_foil_card_is_still_declined():
    """The awkward case the fallback must not rescue: foil texture finds a
    spurious transition at a different depth at every position, and the median
    profile finds no border at all."""
    assert _rectified("full_art_foil")["raw_score"] is None
