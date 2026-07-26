"""Validation and storage for operator/client supplied images.

Everything that accepts an uploaded image goes through validate_upload here,
so the hardening lives in one place: a size cap that doesn't trust the
client, format detection from the bytes rather than the declared
content-type, and a filename this process chooses.
"""

import io
from pathlib import Path

from PIL import Image, UnidentifiedImageError

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


def service_image_path(media_dir: Path, slug: str) -> Path:
    """Where a service tier's banner lives. Always .jpg -- store_service_image
    re-encodes, so the extension is ours to fix rather than the upload's."""
    return Path(media_dir) / "services" / f"{slug}.jpg"


def store_service_image(content: bytes, destination: Path) -> None:
    """Re-encode an uploaded image to a bounded JPEG at `destination`.

    Re-encoding matters as much for safety as for size: the bytes that end up
    on disk (and get served to the public) are ones Pillow produced from a
    decoded image, not the ones the client sent, which also drops any EXIF
    payload riding along in the original.
    """
    validate_upload(content)

    # verify() above consumed the probe object, so reopen to actually decode.
    image = Image.open(io.BytesIO(content))
    # JPEG has no alpha channel; a transparent PNG would otherwise fail to save.
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    image.thumbnail(SERVICE_IMAGE_MAX_SIZE, Image.LANCZOS)

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="JPEG", quality=SERVICE_IMAGE_QUALITY, optimize=True)
