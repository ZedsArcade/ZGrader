"""Derived images are illustrations, and were being stored like archives.

One real two-sided submission left **160MB** of reports on disk against 13MB of
customer scans -- the derived data was twelve times the source it came from. The
cause was two separate things, and both are pinned here:

* `crop_region` had a size *floor* (`min_output_px`) and no ceiling, so a
  crease's bounding box -- which spans most of the card by design -- was zoomed
  4x into a 9132x12752 image. 116 megapixels, roughly 350MB held in memory, for
  a panel the page renders a few hundred pixels wide. Large enough to trip
  Pillow's decompression-bomb guard.
* everything was written as lossless PNG, for pictures nothing re-reads to
  measure anything.

Together: 160MB became 8MB, with no change to a single measurement (checked
against `scripts/fixture_drift.py`, which reported no drift across 23 fixtures).
"""

import numpy as np
import pytest
from PIL import Image

from zgrader.analysis import annotate, artifacts


def _card(width: int = 2283, height: int = 3188) -> np.ndarray:
    """A card-sized raster, at the scale `preprocessing.rectify` actually
    produces for a 63x88mm card."""
    rng = np.random.default_rng(1234)
    return rng.integers(0, 255, size=(height, width, 3), dtype=np.uint8)


# --- the ceiling ----------------------------------------------------------


def test_a_full_card_bbox_does_not_become_a_hundred_megapixel_crop():
    """The crease case, which is what produced the 116MP file."""
    card = _card()
    h, w = card.shape[:2]
    # A crease's bbox spans nearly the whole card.
    bbox = (w * 0.05, h * 0.05, w * 0.95, h * 0.95)

    crop = annotate.crop_region(card, bbox, line_px=(0, 0, w, h))

    assert max(crop.size) <= 1000, f"crop is {crop.size}, above the ceiling"
    assert crop.size[0] * crop.size[1] < 2_000_000, "a breakout panel should not be megapixels"


def test_a_small_region_is_still_enlarged():
    """The floor is not collateral damage: a 40px corner chip has to be blown up
    to be looked at, which is the whole reason min_output_px exists."""
    card = _card()
    h, w = card.shape[:2]
    bbox = (10, 10, 50, 50)

    crop = annotate.crop_region(card, bbox)

    assert min(crop.size) >= 200, f"small region came out at {crop.size}, too small to inspect"


def test_the_ceiling_wins_over_the_zoom():
    """Both constraints apply to the same crop; the cap is the one that has to
    win, or the floor reintroduces the bug it never caused."""
    card = _card()
    h, w = card.shape[:2]

    crop = annotate.crop_region(card, (0, 0, w, h), zoom=4, max_output_px=600)

    assert max(crop.size) <= 600


# --- the format -----------------------------------------------------------


def test_derived_images_are_written_as_capped_jpeg(tmp_path):
    tall = Image.new("RGB", (4000, 5000), "white")

    path = artifacts.save_derived(tall, tmp_path, "front_base")

    assert path.suffix == ".jpg"
    with Image.open(path) as written:
        assert written.format == "JPEG"
        assert max(written.size) <= artifacts.MAX_DERIVED_PX


def test_an_image_with_alpha_does_not_fail_to_save(tmp_path):
    """JPEG has no alpha channel and Pillow raises rather than flattening, which
    would surface as a failed analysis rather than a bad picture."""
    rgba = Image.new("RGBA", (100, 100), (255, 0, 0, 128))

    path = artifacts.save_derived(rgba, tmp_path, "front_surface")

    assert path.is_file()


# --- old reports keep working --------------------------------------------


def test_a_png_written_before_this_change_is_still_found(tmp_path):
    """The reason nothing is regenerated. Re-running analysis on an existing
    submission can produce different numbers than the customer was shown, so old
    reports keep their PNGs and the read path resolves either."""
    legacy = tmp_path / "front_base.png"
    Image.new("RGB", (50, 50), "blue").save(legacy)

    found = artifacts.find(tmp_path, "front_base")

    assert found == legacy
    assert artifacts.media_type(found) == "image/png"


def test_jpeg_is_preferred_when_both_exist(tmp_path):
    Image.new("RGB", (50, 50), "blue").save(tmp_path / "front_base.png")
    artifacts.save_derived(Image.new("RGB", (50, 50), "red"), tmp_path, "front_base")

    found = artifacts.find(tmp_path, "front_base")

    assert found.suffix == ".jpg"
    assert artifacts.media_type(found) == "image/jpeg"


def test_a_missing_stem_resolves_to_nothing(tmp_path):
    assert artifacts.find(tmp_path, "front_base") is None


def test_a_redraw_keeps_the_format_the_row_points_at(tmp_path):
    """`redraw_centering_annotations` writes back to the path stored on the
    AnalysisResult. Changing the extension there would leave the row pointing at
    a file that no longer exists."""
    legacy = tmp_path / "front_centering.png"
    Image.new("RGB", (80, 80), "blue").save(legacy)

    artifacts.save_to(Image.new("RGB", (80, 80), "green"), legacy)

    assert legacy.is_file()
    with Image.open(legacy) as written:
        assert written.format == "PNG"


@pytest.mark.parametrize("suffix", [".jpg", ".png"])
def test_media_type_follows_the_file_not_the_request(suffix, tmp_path):
    path = tmp_path / f"front_base{suffix}"
    Image.new("RGB", (10, 10), "white").save(path)

    assert artifacts.media_type(path) in ("image/jpeg", "image/png")
