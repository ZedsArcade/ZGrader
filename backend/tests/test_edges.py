import tempfile

import cv2

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
