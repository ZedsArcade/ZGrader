import tempfile

import cv2

from tests.fixtures.generate_samples import make_card_scan
from zgrader.analysis import creases, preprocessing, regions, scale


def _deskewed(**kwargs):
    scan = make_card_scan(63.0, 88.0, **kwargs)
    path = tempfile.mktemp(suffix=".png")
    cv2.imwrite(path, scan)
    card, _info = preprocessing.locate_and_deskew(preprocessing.load_image(path))
    return card


def test_clean_card_has_no_creases():
    # A pristine synthetic card (uniform interior) must not false-positive.
    assert creases.detect_creases(_deskewed(), px_per_mm=600 / 25.4) == []


def test_drawn_crease_is_detected():
    card = _deskewed()
    h, w = card.shape[:2]
    cv2.line(card, (int(w * 0.2), int(h * 0.25)), (int(w * 0.8), int(h * 0.72)), (70, 70, 70), 2)

    lines = creases.detect_creases(card, px_per_mm=600 / 25.4)

    assert len(lines) >= 1
    assert lines[0]["length_mm"] > 5


def test_crease_regions_are_flagged_low_confidence_and_normalized():
    card = _deskewed()
    h, w = card.shape[:2]
    cv2.line(card, (int(w * 0.2), int(h * 0.25)), (int(w * 0.8), int(h * 0.72)), (70, 70, 70), 2)
    lines = creases.detect_creases(card, px_per_mm=600 / 25.4)

    region_list = regions.build_crease_regions((h, w), "en", lines)

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
    lines = creases.detect_creases(card, px_per_mm=600 / 25.4)

    region_list = regions.build_crease_regions((h, w), "es", lines)
    assert "pliegue" in region_list[0]["note"].lower()


def test_crease_length_is_physically_possible():
    # Regression: measurements used to be derived from the image file's DPI
    # metadata, which is meaningless for a photo -- a crease on an 88mm card
    # was reported as 244mm. Scale now comes from the card's real size, so a
    # detected crease can never exceed the card's diagonal.
    import math

    card = _deskewed()
    h, w = card.shape[:2]
    cv2.line(card, (int(w * 0.2), int(h * 0.25)), (int(w * 0.8), int(h * 0.72)), (70, 70, 70), 2)
    px_per_mm = scale.px_per_mm((h, w), 63.0, 88.0)

    lines = creases.detect_creases(card, px_per_mm=px_per_mm)

    card_diagonal_mm = math.hypot(63.0, 88.0)
    assert lines
    for line in lines:
        assert 0 < line["length_mm"] <= card_diagonal_mm


def test_parallel_fragments_of_one_crease_collapse_to_one():
    # Three near-parallel segments a few pixels apart describe a single
    # physical crease; the old endpoint-proximity dedup (fixed 40px) reported
    # them separately at photo resolution.
    card = _deskewed()
    h, w = card.shape[:2]
    for offset in (0, 6, 12):
        cv2.line(
            card,
            (int(w * 0.2), int(h * 0.30) + offset),
            (int(w * 0.8), int(h * 0.55) + offset),
            (70, 70, 70),
            2,
        )

    lines = creases.detect_creases(card, px_per_mm=scale.px_per_mm((h, w), 63.0, 88.0))

    assert len(lines) == 1


def test_crease_region_carries_line_geometry():
    card = _deskewed()
    h, w = card.shape[:2]
    cv2.line(card, (int(w * 0.2), int(h * 0.25)), (int(w * 0.8), int(h * 0.72)), (70, 70, 70), 2)
    lines = creases.detect_creases(card, px_per_mm=scale.px_per_mm((h, w), 63.0, 88.0))

    region = regions.build_crease_regions((h, w), "en", lines)[0]

    # The segment itself, normalized -- what lets the UI/crop show *where*
    # the crease runs rather than just a card-spanning box.
    assert "line_norm" in region
    assert len(region["line_norm"]) == 4
    assert all(0.0 <= v <= 1.0 for v in region["line_norm"])
