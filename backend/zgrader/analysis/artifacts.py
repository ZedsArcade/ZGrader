"""How a derived image is written, and how it is found again.

Both halves live here on purpose. The format is a write-side decision and the
lookup is a read-side one, and they are the same decision -- separating them is
how a directory ends up full of files nothing can serve.

Derived images are the pipeline's *output*: the deskewed base photo, the four
per-category overlays, and the zoomed breakout crops. They are illustrations of
a measurement, not the measurement, and nothing re-reads them to analyse
anything -- analysis always goes back to the customer's original scan. So they
are stored as JPEG rather than lossless PNG.

Measured on one real two-sided submission: 160.1MB of PNG became 7.7MB. The
same submission's scans are 13.2MB, so the *derived* data was twelve times the
source it came from, and 27 files were being written where the page shows a
handful of small pictures.

**Existing reports stay PNG and keep working.** `find` tries both suffixes, so
nothing already generated 404s. Regenerating them was the alternative and it is
worse: re-running analysis can produce different numbers than the customer was
shown, and a backup-driven size problem is no reason to quietly restate
somebody's result.
"""

from pathlib import Path

from PIL import Image

#: Longest side of a saved derived image. A report PDF prints the card at
#: 63mm wide, so 1600px is about 400 DPI there and comfortably more than the
#: results page shows. Above this the extra pixels reach nothing.
MAX_DERIVED_PX = 1600

#: High enough that the thin annotation lines drawn over these images stay
#: clean -- they are the reason this is not q75.
JPEG_QUALITY = 88

#: Written today. `find` still resolves the PNGs written before this.
SUFFIX = ".jpg"
_READ_SUFFIXES = (".jpg", ".png")

_MEDIA_TYPES = {".jpg": "image/jpeg", ".png": "image/png"}


def save_derived(image: Image.Image, directory: Path, stem: str) -> Path:
    """Write one derived image, capped and compressed, and return its path.

    The cap is applied here as well as in `annotate.crop_region` because they
    guard different things: this one bounds what reaches the disk, that one
    bounds what is built in memory first.
    """
    directory.mkdir(parents=True, exist_ok=True)
    out = image
    if max(out.size) > MAX_DERIVED_PX:
        out = out.copy()
        out.thumbnail((MAX_DERIVED_PX, MAX_DERIVED_PX), Image.Resampling.LANCZOS)
    if out.mode != "RGB":
        # JPEG has no alpha channel, and an unconverted RGBA raises rather than
        # flattening -- which would surface as a failed analysis, not a bad
        # picture.
        out = out.convert("RGB")

    path = directory / f"{stem}{SUFFIX}"
    out.save(path, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return path


def save_to(image: Image.Image, path: Path) -> Path:
    """Rewrite an image at a path that already exists, keeping its format.

    For `recompute.redraw_centering_annotations`, which writes back to the
    path stored on the AnalysisResult row. That path was chosen when the
    submission was analysed, so an old submission's overlay stays PNG and a new
    one stays JPEG -- the redraw must not change the extension out from under a
    row that still points at the old one.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in (".jpg", ".jpeg"):
        out = image if image.mode == "RGB" else image.convert("RGB")
        if max(out.size) > MAX_DERIVED_PX:
            out = out.copy()
            out.thumbnail((MAX_DERIVED_PX, MAX_DERIVED_PX), Image.Resampling.LANCZOS)
        out.save(path, "JPEG", quality=JPEG_QUALITY, optimize=True)
    else:
        image.save(path)
    return path


def find(directory: Path, stem: str) -> Path | None:
    """The derived image for `stem`, whichever format it was written in.

    JPEG first because that is what everything new writes; PNG second so a
    submission analysed before this change still serves.
    """
    for suffix in _READ_SUFFIXES:
        candidate = directory / f"{stem}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def media_type(path: Path) -> str:
    return _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
