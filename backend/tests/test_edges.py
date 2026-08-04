"""Edges, and the false positive that made this phase necessary.

The reference strip used to sit at a fixed depth, which assumed the printed
border was thicker than 8% of the card. Real Pokemon borders are 5-6%, so the
reference landed on artwork and the ordinary colour difference between a border
and the art it frames was read as whitening along the entire edge. An
undamaged white-bordered card scored 0.00/10.

Most of this file is about that: the border is now located rather than
assumed, and when it is too narrow to sample beside, the edge says so instead
of inventing a number.
"""

import tempfile

import cv2
import numpy as np
import pytest

from tests.fixtures.generate_samples import build_fixture, card_size_mm, make_card_scan
from zgrader.analysis import assessment, edges, preprocessing, scoring


def _deskewed(**kwargs):
    scan = make_card_scan(63.0, 88.0, **kwargs)
    fd, path = tempfile.mkstemp(suffix=".png")
    cv2.imwrite(path, scan)
    image = preprocessing.load_image(path)
    card_image, _info = preprocessing.locate_and_deskew(image)
    return card_image


def _measure(name: str) -> dict:
    card = preprocessing.rectify(build_fixture(name), *card_size_mm(name))
    return edges.measure_edges(card.image, px_per_mm=card.px_per_mm, geometry=card.geometry)


# --- The false positive ----------------------------------------------------


def test_a_clean_white_bordered_card_no_longer_scores_zero():
    """The bug this phase exists for.

    White border, nothing wrong with it, 0.00/10. The reference strip sat at a
    fixed 4-8% depth, which on a 5.6% border lands on the dark artwork behind
    it -- so every position along every edge read as having lost colour.
    """
    result = _measure("white_border_clean")

    assert result["raw_score"] == 10.0
    for name, edge in result["measurements"]["per_edge"].items():
        assert edge["score"] >= 9.5, f"{name} still penalised on a clean card"


def test_a_thin_border_no_longer_reads_as_a_full_length_defect():
    """The same bug on a second fixture, exposed when phase 3's more accurate
    boundary moved the sample strip by a pixel: a 1.2%-deep sliver running the
    whole edge, scored as a full-length defect because the reference had
    drifted onto artwork."""
    result = _measure("centering_offset_severe")
    assert result["raw_score"] >= 9.5


def test_the_border_is_measured_rather_than_assumed():
    """Each fixture's printed border is a different width, and the detected
    width is what decides where the reference comes from -- so it is worth
    asserting directly rather than only through a score."""
    widths = {
        name: _measure(name)["measurements"]["per_edge"]["top"]["border_width_mm"]
        for name in ("pokemon_front", "white_border_clean")
    }
    for name, width in widths.items():
        assert 1.0 < width < 10.0, f"{name}: implausible border width {width}mm"


def test_a_full_art_card_reports_no_border_and_still_scores():
    """Artwork runs to the cut, so there is no transition to find. That is not
    a failure: the outermost sliver compared against the artwork immediately
    behind it is still a valid local comparison."""
    result = _measure("full_art_centered")

    top = result["measurements"]["per_edge"]["top"]
    assert top["border_found"] is False
    assert top["score"] is not None
    assert result["raw_score"] >= 9.0


# --- Still detecting real damage -------------------------------------------


def test_a_whitened_edge_is_still_caught():
    """The fix must not have been achieved by making the detector blind."""
    result = _measure("damage_edge_whitened")
    per_edge = result["measurements"]["per_edge"]

    assert per_edge["right"]["score"] < 6.0
    assert per_edge["left"]["score"] >= 9.5
    assert per_edge["top"]["score"] >= 9.5


def test_whitening_reads_as_lighter_and_less_colourful():
    """Lab rather than HSV saturation, matching corners: saturation collapsed
    the two effects and was unstable where value is low."""
    per_edge = _measure("damage_edge_whitened")["measurements"]["per_edge"]
    assert per_edge["right"]["whitened_fraction"] > 0.05
    # Peak, not median: the fixture whitens about a quarter of the edge, so the
    # median position along it is untouched and a median-based assertion would
    # read the damaged edge as clean.
    assert per_edge["right"]["peak_lightness_rise"] > 20.0
    assert per_edge["right"]["peak_lightness_rise"] > per_edge["left"]["peak_lightness_rise"]


# --- The geometric channel -------------------------------------------------


def test_a_ragged_cut_is_penalised_on_shape_alone():
    """New in this phase, and nearly free: geometry.py already fits a sub-pixel
    line to each side and keeps the residuals. A nick is a physical excursion
    from a straight cut, which describes a chewed edge better than any colour
    comparison and works on a border with no colour at all."""
    clean = _measure("pokemon_back")["measurements"]["per_edge"]
    ragged = _measure("capture_worst_case")["measurements"]["per_edge"]

    clean_worst = max(e["max_excursion_mm"] for e in clean.values())
    ragged_worst = max(e["max_excursion_mm"] for e in ragged.values())
    assert ragged_worst > 10 * max(clean_worst, 0.001)


def test_the_geometric_channel_is_reported_in_millimetres():
    per_edge = _measure("capture_worst_case")["measurements"]["per_edge"]
    for edge in per_edge.values():
        assert edge["geometric_measured"] is True
        assert 0.0 <= edge["max_excursion_mm"] < 5.0
        assert 0.0 <= edge["roughness_mm"] < 5.0


def test_the_two_channels_combine_by_the_worse_of_them():
    """Not their sum. A frayed edge is usually both whitened and ragged, and
    adding the two would count one defect twice -- the same rule corners
    uses."""
    photometric = scoring.edge_photometric_penalty(0.5, 0.5)
    geometric = scoring.edge_geometric_penalty(0.0, 0.0)
    assert geometric == 0.0
    assert photometric > 0.0
    # A deep nick alone can carry an edge with no colour signal at all.
    assert scoring.edge_geometric_penalty(scoring.EDGE_NICK_DEPTH_FOR_ZERO_MM, 0.0) == 10.0


# --- Degrading honestly ----------------------------------------------------


def test_a_border_too_narrow_to_sample_says_so_rather_than_guessing():
    """Widening the reference into the artwork is exactly the bug this module
    was rewritten to remove, so the honest answer is to decline the
    photometric channel and lean on shape."""
    card = preprocessing.rectify(build_fixture("pokemon_front"), 63.0, 88.0)
    lab = cv2.cvtColor(card.image, cv2.COLOR_BGR2LAB).astype(np.float32)
    # A band only as deep as the inset leaves no room for a reference.
    shallow = edges._edge_band(lab, "top", 0.12, int(edges.REFERENCE_INSET_MM * card.px_per_mm) + 1)

    result = edges._analyze_edge(shallow, card.px_per_mm)
    assert result["score"] is None
    assert result["measured"] is False


def test_a_degenerate_band_is_reported_unmeasured_not_perfect():
    """An empty strip used to return a hardcoded 10.0 -- absence of data
    scored as a perfect edge. The API this asserts against changed in this
    phase; the property it protects did not."""
    empty = np.zeros((0, 0, 3), dtype=np.float32)
    result = edges._analyze_edge(empty, 23.6)

    assert result["score"] is None
    assert result["measured"] is False


def test_no_measurable_edge_raises_rather_than_scoring():
    """With every band collapsed there is nothing to report. Previously each
    one returned 10.0 and the card scored a flawless 10.0 on zero evidence."""
    card = _deskewed()
    with pytest.raises(ValueError, match="degenerate"):
        edges.measure_edges(card, corner_exclusion_fraction=0.6)


def test_a_capture_too_small_to_measure_still_declines_to_score():
    card = preprocessing.rectify(build_fixture("pokemon_front"), 63.0, 88.0)
    result = edges.measure_edges(card.image, px_per_mm=7.0, geometry=card.geometry)
    assert result["raw_score"] is None
    assert result["measurements"]["assessment"]["state"] == assessment.UNMEASURABLE


def test_a_thin_border_card_carries_the_limitation_code():
    """Constructed rather than taken from a fixture, because every fixture's
    border is now comfortably samplable -- which is the point, but leaves this
    branch otherwise unexercised."""
    card = preprocessing.rectify(build_fixture("pokemon_front"), 63.0, 88.0)
    # Force the search window down so no reference fits behind the inset.
    original = edges.MAX_BORDER_SEARCH_MM
    try:
        edges.MAX_BORDER_SEARCH_MM = edges.REFERENCE_INSET_MM + 0.1
        result = edges.measure_edges(
            card.image, px_per_mm=card.px_per_mm, geometry=card.geometry
        )
    finally:
        edges.MAX_BORDER_SEARCH_MM = original

    assert result["raw_score"] is not None, "shape alone should still carry the edge"
    limitations = result["measurements"]["assessment"]["limitations"]
    assert assessment.EDGES_THIN_BORDER in limitations
    assert "border" in result["flags"]["reason"]
