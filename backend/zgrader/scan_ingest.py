"""Shared helpers for turning a raw scan image file into ScanImage-ready
metadata. Used by both the dev CLI trigger and the watcher worker so the two
entrypoints don't drift.
"""

import hashlib
from pathlib import Path

from PIL import Image

from zgrader.config import config


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_scan_metadata(path: Path) -> tuple[int, int, int]:
    """Returns (width_px, height_px, dpi), falling back to
    config.default_scan_dpi when the image carries no DPI metadata."""
    with Image.open(path) as img:
        width, height = img.size
        dpi_info = img.info.get("dpi")
        dpi = int(round(dpi_info[0])) if dpi_info else config.default_scan_dpi
    return width, height, dpi
