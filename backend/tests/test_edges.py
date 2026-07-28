import tempfile

import numpy as np
import cv2
import pytest

from tests.fixtures.generate_samples import make_card_scan
from zgrader.analysis import edges, preprocessing


def _deskewed(**kwargs):
    scan = make_card_scan(63.0, 88.0, **kwargs)
    fd, path = tempfile.mkstemp(suffix=".png")
    cv2.imwrite(path, scan)
    image = preprocessing.load_image(path)
    card_image, _info = preprocessing.locate_and_deskew(image)
    return card_image


def test_clean_edges_score_near_perfect():
    result = edges.measure_edges(_deskewed())
    for edge in result["measurements"]["per_edge"].values():
        assert edge["score"] >= 9.0


def test_whitened_right_edge_is_flagged():
    result = edges.measure_edges(_deskewed(whiten_right_edge=True))
    per_edge = result["measurements"]["per_edge"]
    assert per_edge["right"]["whitened_fraction"] > 0.05
    assert per_edge["right"]["score"] < per_edge["left"]["score"]
    assert per_edge["top"]["score"] >= 9.0


def test_an_empty_strip_is_reported_unmeasured_not_perfect():
    """An empty strip used to return a hardcoded 10.0 -- absence of data
    scored as a perfect edge."""
    empty = np.empty((0, 0), dtype=np.uint8)
    inner = np.full((4, 4), 200, dtype=np.uint8)

    result = edges._analyze_strip(empty, inner, along_axis=0)

    assert result["score"] is None
    assert result["measured"] is False


def test_no_measurable_edge_raises_rather_than_scoring():
    """With every strip empty there is nothing to report. Previously each one
    returned 10.0 and the card scored a flawless 10.0 on zero evidence; now
    the pipeline turns this into an operator-visible error.

    A corner exclusion above 0.5 collapses every strip to zero width, which is
    the only way to reach this branch -- with the shipped 0.12 the integer
    flooring keeps the exclusion below half the card on both axes, so it is
    otherwise unreachable and the guard is defensive against retuning.
    """
    card = _deskewed()
    with pytest.raises(ValueError, match="degenerate"):
        edges.measure_edges(card, corner_exclusion_fraction=0.6)
