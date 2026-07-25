import tempfile

import cv2

from tests.fixtures.generate_samples import make_card_scan
from zgrader.analysis import creases, preprocessing, regions


def _deskewed(**kwargs):
    scan = make_card_scan(63.0, 88.0, **kwargs)
    path = tempfile.mktemp(suffix=".png")
    cv2.imwrite(path, scan)
    card, _info = preprocessing.locate_and_deskew(preprocessing.load_image(path))
    return card


def test_clean_card_has_no_creases():
    # A pristine synthetic card (uniform interior) must not false-positive.
    assert creases.detect_creases(_deskewed(), dpi=600) == []


def test_drawn_crease_is_detected():
    card = _deskewed()
    h, w = card.shape[:2]
    cv2.line(card, (int(w * 0.2), int(h * 0.25)), (int(w * 0.8), int(h * 0.72)), (70, 70, 70), 2)

    lines = creases.detect_creases(card, dpi=600)

    assert len(lines) >= 1
    assert lines[0]["length_mm"] > 5


def test_crease_regions_are_flagged_low_confidence_and_normalized():
    card = _deskewed()
    h, w = card.shape[:2]
    cv2.line(card, (int(w * 0.2), int(h * 0.25)), (int(w * 0.8), int(h * 0.72)), (70, 70, 70), 2)
    lines = creases.detect_creases(card, dpi=600)

    region_list = regions.build_crease_regions((h, w), 600, "en", lines)

    assert region_list
    r = region_list[0]
    assert r["kind"] == "crease"
    assert r["severity"] == "flag"
    assert r["low_confidence"] is True
    assert "crease" in r["note"].lower()
    assert all(0.0 <= v <= 1.0 for v in r["bbox_norm"])
    assert all(0.0 <= v <= 1.0 for v in r["anchor_norm"])


def test_crease_note_localized_for_spanish():
    card = _deskewed()
    h, w = card.shape[:2]
    cv2.line(card, (int(w * 0.2), int(h * 0.25)), (int(w * 0.8), int(h * 0.72)), (70, 70, 70), 2)
    lines = creases.detect_creases(card, dpi=600)

    region_list = regions.build_crease_regions((h, w), 600, "es", lines)
    assert "pliegue" in region_list[0]["note"].lower()
