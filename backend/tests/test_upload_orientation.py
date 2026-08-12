"""A portrait phone photo must reach the pipeline the way it was taken.

A phone does not rotate its sensor. It writes the frame the way the sensor read
it and records how the handset was held as EXIF Orientation, leaving every
viewer to rotate on the way to the screen. Every store path in `images` drops
EXIF on purpose, because the same block carries GPS -- so unless the rotation is
applied to the pixels first, dropping the tag turns an upright photograph into a
permanently sideways one.

This shipped that way. A 400x560 portrait photo was stored 560x400, with the
card lying on its side, for what is the most natural way to photograph a card.
The tests below pin each of the eight orientation values and the no-EXIF case,
because the failure is silent: nothing errors, and the only symptom is that
every measurement was taken off a rotated card.
"""

import io

import pytest
from PIL import Image, ImageOps

from zgrader.images import open_upright, store_brand_logo, store_service_image, strip_metadata

# Orientation values that involve a 90-degree turn, so width and height swap.
# 1 is "as stored"; 2/3/4 are flips and rotations that preserve the aspect.
QUARTER_TURNS = (5, 6, 7, 8)
ALL_ORIENTATIONS = (1, 2, 3, 4, 5, 6, 7, 8)


def _portrait_card(width: int = 400, height: int = 560) -> Image.Image:
    """An unmistakably portrait image with a red stripe down its left edge, so
    a rotation is visible in the pixels rather than only in the dimensions."""
    image = Image.new("RGB", (width, height), "white")
    for x in range(width // 10):
        for y in range(height):
            image.putpixel((x, y), (255, 0, 0))
    return image


def _as_phone_writes_it(upright: Image.Image, orientation: int) -> bytes:
    """Encode `upright` the way a handset would for a given orientation tag:
    pixels stored in sensor order, with EXIF describing the correction."""
    # The inverse of what a viewer will do, so that applying the tag returns
    # the original. Pillow's own table for exif_transpose is
    # {2: FLIP_LEFT_RIGHT, 3: ROTATE_180, 4: FLIP_TOP_BOTTOM, 5: TRANSPOSE,
    #  6: ROTATE_270, 7: TRANSVERSE, 8: ROTATE_90}; the flips and the two
    # diagonal transposes are their own inverses, and only the quarter turns
    # need reversing. Getting 6 and 8 the wrong way round is easy and the test
    # catches it, which is the point of covering all eight.
    inverse = {
        1: lambda im: im,
        2: lambda im: im.transpose(Image.FLIP_LEFT_RIGHT),
        3: lambda im: im.transpose(Image.ROTATE_180),
        4: lambda im: im.transpose(Image.FLIP_TOP_BOTTOM),
        5: lambda im: im.transpose(Image.TRANSPOSE),
        6: lambda im: im.transpose(Image.ROTATE_90),
        7: lambda im: im.transpose(Image.TRANSVERSE),
        8: lambda im: im.transpose(Image.ROTATE_270),
    }[orientation]
    stored = inverse(upright)
    exif = Image.Exif()
    exif[274] = orientation  # 274 == Orientation
    buffer = io.BytesIO()
    stored.save(buffer, format="JPEG", quality=95, subsampling=0, exif=exif)
    return buffer.getvalue()


def _left_edge_redness(image: Image.Image) -> float:
    width, height = image.size
    strip = image.crop((0, 0, max(1, width // 10), height)).convert("RGB")
    pixels = list(strip.getdata())
    return sum(1 for r, g, b in pixels if r > 200 and g < 80 and b < 80) / len(pixels)


@pytest.mark.parametrize("orientation", ALL_ORIENTATIONS)
def test_a_scan_upload_is_stored_the_way_it_was_taken(orientation):
    upright = _portrait_card()
    stored = Image.open(io.BytesIO(strip_metadata(_as_phone_writes_it(upright, orientation), ".jpg")))

    assert stored.size == upright.size, (
        f"orientation {orientation} stored {stored.size}, not {upright.size} -- "
        "the card is on its side"
    )
    # Dimensions alone would pass a 180-degree rotation, which keeps the aspect
    # and moves the stripe to the opposite edge.
    assert _left_edge_redness(stored) > 0.9, (
        f"orientation {orientation} kept the shape but moved the content"
    )


@pytest.mark.parametrize("orientation", QUARTER_TURNS)
def test_the_stored_scan_carries_no_orientation_tag_of_its_own(orientation):
    """Applying the rotation and *keeping* the tag would rotate it twice on the
    next viewer. The tag has to go, which is the whole reason the pixels have to
    be corrected first."""
    stored = Image.open(io.BytesIO(strip_metadata(_as_phone_writes_it(_portrait_card(), orientation), ".jpg")))
    assert stored.getexif().get(274) in (None, 1)


def test_an_image_with_no_exif_at_all_is_untouched():
    upright = _portrait_card()
    buffer = io.BytesIO()
    upright.save(buffer, format="PNG")

    stored = Image.open(io.BytesIO(strip_metadata(buffer.getvalue(), ".png")))
    assert stored.size == upright.size
    assert _left_edge_redness(stored) > 0.9


def test_open_upright_matches_what_a_viewer_would_show():
    """The reference implementation, stated as the contract: whatever
    ImageOps.exif_transpose produces is what should reach the pipeline."""
    raw = _as_phone_writes_it(_portrait_card(), 6)
    expected = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
    assert open_upright(raw).size == expected.size


@pytest.mark.parametrize("orientation", QUARTER_TURNS)
def test_operator_uploads_are_corrected_too(orientation, tmp_path):
    """The logo and banner paths decode separately, and an operator uploading
    from a phone hits exactly the same problem."""
    raw = _as_phone_writes_it(_portrait_card(120, 168), orientation)

    logo = tmp_path / "logo.png"
    store_brand_logo(raw, logo)
    with Image.open(logo) as stored:
        assert stored.height > stored.width, "logo stored sideways"

    banner = tmp_path / "banner.jpg"
    store_service_image(raw, banner)
    with Image.open(banner) as stored:
        assert stored.height > stored.width, "service banner stored sideways"
