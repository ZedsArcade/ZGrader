"""Validation and storage for operator/client supplied images.

Everything that accepts an uploaded image goes through validate_upload here,
so the hardening lives in one place: a size cap that doesn't trust the
client, format detection from the bytes rather than the declared
content-type, and a filename this process chooses.
"""

import io
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 20 * 1024 * 1024

# Formats we accept, mapped to the suffix we store them under. Detection comes
# from PIL reading the actual bytes -- a client's Content-Type header is
# unverified input and is deliberately never consulted.
PIL_FORMAT_TO_SUFFIX = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "TIFF": ".tiff",
}

# The six service tiers shown on the public /services page. A fixed tuple
# rather than a pattern: every filesystem path built for a service image
# joins one of these constants, so there is no traversal surface at all.
# Must stay in step with the `slug` values in
# frontend/app/services/services-client.tsx.
SERVICE_TIER_SLUGS = (
    "analysis",
    "subscription",
    "personalised",
    "restoration",
    "packaging",
    "collection",
)

# Bounds for a service banner. The card renders it 16:9, and anything larger
# is wasted bytes on a marketing page.
SERVICE_IMAGE_MAX_SIZE = (1200, 675)
SERVICE_IMAGE_QUALITY = 82

# The two public brands, each with its own header logo. Must stay in step with
# the Brand type in frontend/lib/brand.ts.
BRAND_LOGO_SLUGS = ("lab", "care")

# Bounds for a header logo. It renders at roughly 36px tall, so this is
# generous enough for a 2x display without carrying a print-sized asset.
BRAND_LOGO_MAX_SIZE = (600, 200)


class ImageTooLarge(Exception):
    """Upload exceeded MAX_UPLOAD_BYTES."""


class UnsupportedImage(Exception):
    """Upload was not a readable image, or not one of PIL_FORMAT_TO_SUFFIX."""


def validate_upload(content: bytes) -> str:
    """Check `content` is an image we accept and return its storage suffix.

    Raises ImageTooLarge or UnsupportedImage; callers translate those into
    HTTP status codes.
    """
    if len(content) > MAX_UPLOAD_BYTES:
        raise ImageTooLarge

    try:
        probe = Image.open(io.BytesIO(content))
        image_format = probe.format
        probe.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise UnsupportedImage from exc

    suffix = PIL_FORMAT_TO_SUFFIX.get(image_format or "")
    if suffix is None:
        raise UnsupportedImage
    return suffix


def open_upright(content: bytes) -> Image.Image:
    """Decode an upload with its EXIF orientation already applied to the pixels.

    A phone does not rotate its sensor. It stores the frame the way the sensor
    read it and records how the handset was held as EXIF Orientation, leaving
    every viewer to rotate on the way to the screen. Every re-encode in this
    module drops EXIF on purpose -- the same block carries GPS coordinates --
    so unless the rotation is baked into the pixels first, dropping the tag
    turns an upright photograph into a permanently sideways one.

    That is worse here than it would be almost anywhere else. The input to this
    product is a handheld photo of a trading card, and portrait is the natural
    way to hold a phone to photograph one, so the common case was the broken
    one: a 400x560 photo was stored 560x400 with the card lying on its side.

    Every decode path goes through this, including the operator's logo and
    service-banner uploads -- those can come off a phone too.
    """
    image = Image.open(io.BytesIO(content))
    image.load()
    # Returns a transposed copy, or the image unchanged when there is no
    # orientation tag to apply. The `or` guards Pillow versions that return
    # None rather than the original.
    return ImageOps.exif_transpose(image) or image


def strip_metadata(content: bytes, suffix: str) -> bytes:
    """Re-encode an uploaded scan so it carries no embedded metadata.

    Handheld phone photos routinely carry GPS coordinates and device
    identifiers in EXIF. Storing them verbatim means holding location data
    about a customer that the service has no use for. Pillow only copies
    metadata across when explicitly asked, so a decode/encode round-trip
    drops it.

    Pixel *values* are preserved -- PNG and TIFF re-encode losslessly, and JPEG
    is written at quality 95 with subsampling disabled, so the analysis pipeline
    sees effectively the same image. Their arrangement is not, and must not be:
    `open_upright` bakes in the EXIF rotation first, because this function is
    about to throw that tag away.
    """
    image = open_upright(content)

    out = io.BytesIO()
    if suffix == ".jpg":
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        image.save(out, format="JPEG", quality=95, subsampling=0)
    elif suffix == ".png":
        image.save(out, format="PNG", optimize=True)
    else:
        image.save(out, format="TIFF")
    return out.getvalue()


def service_image_path(media_dir: Path, slug: str) -> Path:
    """Where a service tier's banner lives. Always .jpg -- store_service_image
    re-encodes, so the extension is ours to fix rather than the upload's."""
    return Path(media_dir) / "services" / f"{slug}.jpg"


def brand_logo_path(media_dir: Path, slug: str) -> Path:
    """Where a brand's header logo lives. Always .png -- see
    store_brand_logo for why this one isn't JPEG like the service banners."""
    return Path(media_dir) / "brands" / f"{slug}.png"


def store_brand_logo(content: bytes, destination: Path) -> None:
    """Re-encode an uploaded logo to a bounded PNG at `destination`.

    Deliberately *not* store_service_image. That re-encodes to JPEG, which has
    no alpha channel, so it converts anything non-RGB to RGB -- and a logo is
    exactly the kind of image that arrives as a transparent PNG. Sending it
    through the banner path would silently paste a solid rectangle behind
    every logo, against a header background it was meant to sit on cleanly.

    Re-encoding still happens, for the same reason it does for banners: what
    lands on disk and gets served publicly is bytes Pillow produced from a
    decoded image, not bytes the client supplied, which also drops any EXIF
    payload riding along.
    """
    validate_upload(content)

    # verify() consumed the probe object, so reopen to actually decode.
    image = open_upright(content)
    # Keep alpha where it exists; palette images can carry transparency too,
    # so those convert to RGBA rather than RGB.
    if image.mode not in ("RGBA", "RGB", "L"):
        image = image.convert("RGBA" if "transparency" in image.info or image.mode == "P" else "RGB")
    image.thumbnail(BRAND_LOGO_MAX_SIZE, Image.LANCZOS)

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=True)


def store_service_image(content: bytes, destination: Path) -> None:
    """Re-encode an uploaded image to a bounded JPEG at `destination`.

    Re-encoding matters as much for safety as for size: the bytes that end up
    on disk (and get served to the public) are ones Pillow produced from a
    decoded image, not the ones the client sent, which also drops any EXIF
    payload riding along in the original.
    """
    validate_upload(content)

    # verify() above consumed the probe object, so reopen to actually decode.
    image = open_upright(content)
    # JPEG has no alpha channel; a transparent PNG would otherwise fail to save.
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    image.thumbnail(SERVICE_IMAGE_MAX_SIZE, Image.LANCZOS)

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="JPEG", quality=SERVICE_IMAGE_QUALITY, optimize=True)
