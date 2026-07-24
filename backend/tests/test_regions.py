import tempfile

import cv2
import numpy as np

from tests.fixtures.generate_samples import make_card_scan
from zgrader.analysis import centering, corners, edges, preprocessing, regions, surface
from zgrader.models import AnalysisCategory

_DPI = 600


def _deskewed(**kwargs):
    scan = make_card_scan(63.0, 88.0, **kwargs)
    fd, path = tempfile.mkstemp(suffix=".png")
    cv2.imwrite(path, scan)
    image = preprocessing.load_image(path)
    card_image, _info = preprocessing.locate_and_deskew(image)
    return card_image


def _regions_for(category, card_image, result, extra, language="en"):
    return regions.build_regions(category, card_image.shape[:2], _DPI, language, result, extra)


def test_pristine_corners_are_all_ok_with_no_notes():
    card = _deskewed()
    result = corners.measure_corners(card)
    region_list = _regions_for(AnalysisCategory.corners, card, result, None)

    assert {r["id"] for r in region_list} == {"top_left", "top_right", "bottom_left", "bottom_right"}
    for region in region_list:
        assert region["severity"] == "ok"
        assert region["note"] is None
        assert region["kind"] == "corner"
        # bbox/anchor must be normalized, not raw pixels
        assert all(0.0 <= v <= 1.0 for v in region["bbox_norm"])
        assert all(0.0 <= v <= 1.0 for v in region["anchor_norm"])


def test_whitened_corner_produces_flag_with_note():
    card = _deskewed(whiten_top_left_corner=True)
    result = corners.measure_corners(card)
    region_list = _regions_for(AnalysisCategory.corners, card, result, None)

    top_left = next(r for r in region_list if r["id"] == "top_left")
    assert top_left["severity"] == "flag"
    assert top_left["note"] is not None
    assert "top-left" in top_left["note"]
    # anchor should sit near the actual card corner (top-left => near (0,0))
    assert top_left["anchor_norm"][0] < 0.3
    assert top_left["anchor_norm"][1] < 0.3


def test_whitened_corner_note_is_localized_for_spanish():
    card = _deskewed(whiten_top_left_corner=True)
    result = corners.measure_corners(card)
    region_list = _regions_for(AnalysisCategory.corners, card, result, None, language="es")

    top_left = next(r for r in region_list if r["id"] == "top_left")
    assert "esquina superior izquierda" in top_left["note"]


def test_pristine_edges_are_all_ok():
    card = _deskewed()
    result = edges.measure_edges(card)
    region_list = _regions_for(AnalysisCategory.edges, card, result, None)

    assert {r["id"] for r in region_list} == {"top", "bottom", "left", "right"}
    assert all(r["severity"] == "ok" and r["note"] is None for r in region_list)


def test_whitened_edge_produces_flag_with_note():
    card = _deskewed(whiten_right_edge=True)
    result = edges.measure_edges(card)
    region_list = _regions_for(AnalysisCategory.edges, card, result, None)

    right = next(r for r in region_list if r["id"] == "right")
    assert right["severity"] == "flag"
    assert "right edge" in right["note"]


def test_centered_card_has_no_centering_region():
    card = _deskewed()
    result = centering.measure_centering(card, _DPI)
    region_list = _regions_for(AnalysisCategory.centering, card, result, None)

    assert region_list == []


def test_off_center_card_produces_one_frame_region():
    card = _deskewed(lr_offset_frac=0.4)
    result = centering.measure_centering(card, _DPI)
    region_list = _regions_for(AnalysisCategory.centering, card, result, None)

    assert len(region_list) == 1
    frame = region_list[0]
    assert frame["id"] == "frame"
    assert frame["kind"] == "frame"
    assert frame["severity"] == "flag"
    assert frame["note"] is not None


def test_clean_surface_has_no_blob_regions():
    card = _deskewed()
    result, mask = surface.measure_surface(card)
    region_list = _regions_for(AnalysisCategory.surface, card, result, mask)

    assert region_list == []


def test_scratch_produces_surface_blob_region_with_length():
    card = _deskewed(add_surface_scratch=True)
    result, mask = surface.measure_surface(card)
    region_list = _regions_for(AnalysisCategory.surface, card, result, mask)

    assert len(region_list) >= 1
    blob = region_list[0]
    assert blob["kind"] == "blob"
    assert blob["severity"] == "flag"
    assert "mm" in blob["note"]
    assert all(0.0 <= v <= 1.0 for v in blob["bbox_norm"])


def test_surface_regions_capped_at_max():
    card = _deskewed()
    h, w = card.shape[:2]
    ex_h, ex_w = int(h * 0.12), int(w * 0.12)
    face_h, face_w = h - 2 * ex_h, w - 2 * ex_w

    # Ten well-separated, comfortably-above-threshold blobs -- more than
    # MAX_SURFACE_REGIONS -- synthesized directly rather than relying on
    # measure_surface's real detector, so this test is about build_regions's
    # own capping/sorting logic, not surface.py's texture heuristic.
    mask = np.zeros((face_h, face_w), dtype=bool)
    blob_size = 30
    for i in range(10):
        y = 10 + i * (blob_size + 5)
        if y + blob_size >= face_h:
            break
        mask[y : y + blob_size, 10 : 10 + blob_size] = True

    fake_result = {"raw_score": 5.0, "measurements": {"corner_exclusion_fraction": 0.12}}
    region_list = regions.build_regions(AnalysisCategory.surface, (h, w), _DPI, "en", fake_result, mask)

    assert len(region_list) == regions.MAX_SURFACE_REGIONS
