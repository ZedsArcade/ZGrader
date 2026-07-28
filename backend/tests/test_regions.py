import tempfile

import cv2
import numpy as np

from tests.fixtures.generate_samples import make_card_scan
from zgrader.analysis import centering, corners, edges, preprocessing, regions, surface
from zgrader.models import AnalysisCategory

# The synthetic fixtures are rendered at 600 DPI, so this is their true
# pixels-per-mm (see analysis/scale.py -- measurement no longer reads DPI).
_PX_PER_MM = 600 / 25.4


def _deskewed(**kwargs):
    scan = make_card_scan(63.0, 88.0, **kwargs)
    fd, path = tempfile.mkstemp(suffix=".png")
    cv2.imwrite(path, scan)
    image = preprocessing.load_image(path)
    card_image, _info = preprocessing.locate_and_deskew(image)
    return card_image


def _regions_for(category, card_image, result, extra, language="en"):
    return regions.build_regions(category, card_image.shape[:2], _PX_PER_MM, language, result, extra)


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
    result = centering.measure_centering(card, _PX_PER_MM)
    region_list = _regions_for(AnalysisCategory.centering, card, result, None)

    assert region_list == []


def test_off_center_card_produces_one_frame_region():
    card = _deskewed(lr_offset_frac=0.4)
    result = centering.measure_centering(card, _PX_PER_MM)
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

    # Ten well-separated thin scratch-shaped bars -- more than
    # MAX_SURFACE_REGIONS, each comfortably passing the thin+elongated
    # filter -- synthesized directly rather than via measure_surface's real
    # detector, so this test is about build_regions's own capping/sorting
    # logic, not surface.py's texture heuristic.
    mask = np.zeros((face_h, face_w), dtype=bool)
    for i in range(10):
        y = 10 + i * 12
        if y + 4 >= face_h:
            break
        mask[y : y + 4, 10:110] = True  # 100px x 4px -> thin, high aspect

    fake_result = {"raw_score": 5.0, "measurements": {"corner_exclusion_fraction": 0.12}}
    region_list = regions.build_regions(AnalysisCategory.surface, (h, w), _PX_PER_MM, "en", fake_result, mask)

    assert len(region_list) == regions.MAX_SURFACE_REGIONS


def test_each_surface_blob_carries_its_own_score_not_the_whole_card_score():
    """Every blob used to be stamped with result["raw_score"], so a card with
    six defects showed one identical number six times as if each had been
    scored individually. A blob's score now comes from its own area."""
    card = _deskewed()
    h, w = card.shape[:2]
    ex_h, ex_w = int(h * 0.12), int(w * 0.12)
    face_h, face_w = h - 2 * ex_h, w - 2 * ex_w

    # Two scratch-shaped bars of deliberately different length, so their
    # areas -- and therefore their scores -- must differ.
    # Both must clear MIN_BLOB_AREA_MM2 as well as the thin+elongated filter.
    mask = np.zeros((face_h, face_w), dtype=bool)
    mask[10:14, 10:210] = True  # long bar, 4x200
    mask[40:44, 10:110] = True  # short bar, 4x100

    fake_result = {"raw_score": 5.0, "measurements": {"corner_exclusion_fraction": 0.12}}
    region_list = regions.build_regions(
        AnalysisCategory.surface, (h, w), _PX_PER_MM, "en", fake_result, mask
    )

    assert len(region_list) == 2
    scores = [r["score"] for r in region_list]
    assert len(set(scores)) == 2, "blobs of different size must not share a score"
    assert 5.0 not in scores, "the whole-card score must not be stamped onto a blob"
    # Sorted largest-area first, so the bigger defect scores worse.
    assert region_list[0]["score"] < region_list[1]["score"]
    # And each carries its own physical measurement.
    assert region_list[0]["length_mm"] > region_list[1]["length_mm"]


def test_thick_word_shaped_blob_is_filtered_out():
    card = _deskewed()
    h, w = card.shape[:2]
    ex_h, ex_w = int(h * 0.12), int(w * 0.12)
    face_h, face_w = h - 2 * ex_h, w - 2 * ex_w

    # A wide, solid bar that is elongated (high aspect) but whose mean stroke
    # thickness is far above a hairline -- the profile a whole word of card
    # text collapses to under connected-component analysis (~1mm+ mean
    # thickness measured against the real detector). Aspect alone would keep
    # it; the thickness gate is what rejects it. 120x30 -> mean thickness
    # ~1.27mm at 600 DPI.
    mask = np.zeros((face_h, face_w), dtype=bool)
    mask[20:50, 10:130] = True

    fake_result = {"raw_score": 5.0, "measurements": {"corner_exclusion_fraction": 0.12}}
    region_list = regions.build_regions(AnalysisCategory.surface, (h, w), _PX_PER_MM, "en", fake_result, mask)

    assert region_list == []


def test_glyph_shaped_blob_is_filtered_out_as_text_not_scratch():
    card = _deskewed()
    h, w = card.shape[:2]
    ex_h, ex_w = int(h * 0.12), int(w * 0.12)
    face_h, face_w = h - 2 * ex_h, w - 2 * ex_w

    # A hollow square ring -- compact (aspect ratio ~1) and mostly empty
    # space inside its own bounding box (fill ratio well under the
    # threshold), the same bounding-box profile a line of card rules text
    # produces. Comfortably above MIN_BLOB_AREA_MM2 so the area filter
    # isn't what's rejecting it -- this exercises the shape filter alone.
    mask = np.zeros((face_h, face_w), dtype=bool)
    mask[0:50, 0:5] = True
    mask[0:50, 45:50] = True
    mask[0:5, 0:50] = True
    mask[45:50, 0:50] = True

    fake_result = {"raw_score": 5.0, "measurements": {"corner_exclusion_fraction": 0.12}}
    region_list = regions.build_regions(AnalysisCategory.surface, (h, w), _PX_PER_MM, "en", fake_result, mask)

    assert region_list == []


def test_elongated_blob_is_kept_as_scratch_like():
    card = _deskewed()
    h, w = card.shape[:2]
    ex_h, ex_w = int(h * 0.12), int(w * 0.12)
    face_h, face_w = h - 2 * ex_h, w - 2 * ex_w

    # A thin (~0.2mm mean stroke), elongated blob -- the real shape
    # signature of a scratch -- must survive the filter that rejects the
    # glyph- and word-shaped blobs above.
    mask = np.zeros((face_h, face_w), dtype=bool)
    mask[20:25, 10:110] = True

    fake_result = {"raw_score": 5.0, "measurements": {"corner_exclusion_fraction": 0.12}}
    region_list = regions.build_regions(AnalysisCategory.surface, (h, w), _PX_PER_MM, "en", fake_result, mask)

    assert len(region_list) == 1
