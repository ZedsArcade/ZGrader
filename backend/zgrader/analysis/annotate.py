"""Drawing helpers that turn raw analysis measurements into the annotated
images embedded in the PDF report: centering overlay, corner zoom-ins, edge
flag boxes, and a surface anomaly heatmap.
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw

from zgrader.analysis.corners import corner_crops

_FLAG_COLOR = (220, 30, 30)
_OK_COLOR = (30, 160, 30)


def _to_pil(card_image: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(card_image, cv2.COLOR_BGR2RGB))


def to_pil(card_image: np.ndarray) -> Image.Image:
    """Public wrapper around _to_pil, for callers outside this module (e.g.
    persisting the plain base photo for the web results page)."""
    return _to_pil(card_image)


def crop_region(
    card_image: np.ndarray,
    bbox_px: tuple[float, float, float, float],
    zoom: int = 4,
    min_output_px: int = 280,
    pad_fraction: float = 0.6,
    color: tuple[int, int, int] = _FLAG_COLOR,
    line_px: tuple[float, float, float, float] | None = None,
) -> Image.Image:
    """Zoomed, bordered crop of an arbitrary defect region for a web
    breakout-box panel -- generalizes the per-corner crop+zoom+border
    pattern annotate_corners already does (for a fixed corner_fraction) to
    any bbox from any category.

    When `line_px` (x0, y0, x1, y1 in full-card pixels) is given, the segment
    is drawn instead of the bounding box -- see the comment below."""
    h, w = card_image.shape[:2]
    x0, y0, x1, y1 = bbox_px
    box_w, box_h = x1 - x0, y1 - y0
    pad_x, pad_y = box_w * pad_fraction, box_h * pad_fraction

    crop_x0 = max(0, int(x0 - pad_x))
    crop_y0 = max(0, int(y0 - pad_y))
    crop_x1 = min(w, int(x1 + pad_x))
    crop_y1 = min(h, int(y1 + pad_y))

    crop = card_image[crop_y0:crop_y1, crop_x0:crop_x1]
    crop_h, crop_w = crop.shape[:2]
    if crop_w == 0 or crop_h == 0:
        crop = card_image
        crop_h, crop_w = crop.shape[:2]
        crop_x0, crop_y0 = 0, 0

    scale = max(zoom, min_output_px / max(1, min(crop_w, crop_h)))
    out_w, out_h = max(1, int(crop_w * scale)), max(1, int(crop_h * scale))

    pil_crop = _to_pil(crop).resize((out_w, out_h), Image.NEAREST)
    draw = ImageDraw.Draw(pil_crop)

    line_width = max(2, out_w // 100)

    if line_px is not None:
        # An elongated defect (a crease) has a bounding box spanning most of
        # the card, so the box alone says "somewhere in here" -- draw the
        # segment itself instead, which is what actually locates it.
        lx0, ly0, lx1, ly1 = line_px
        draw.line(
            [
                ((lx0 - crop_x0) * scale, (ly0 - crop_y0) * scale),
                ((lx1 - crop_x0) * scale, (ly1 - crop_y0) * scale),
            ],
            fill=color,
            width=line_width,
        )
        return pil_crop

    # Draw the defect's own box within this (padded, zoomed) crop, so the
    # exact flagged region is still pinpointed, not just "somewhere in here".
    rel_box = [
        (x0 - crop_x0) * scale,
        (y0 - crop_y0) * scale,
        (x1 - crop_x0) * scale,
        (y1 - crop_y0) * scale,
    ]
    draw.rectangle(rel_box, outline=color, width=line_width)

    return pil_crop


def annotate_centering(card_image: np.ndarray, measurements: dict) -> Image.Image:
    img = _to_pil(card_image).convert("RGB")
    draw = ImageDraw.Draw(img)
    h, w = card_image.shape[:2]
    left, right = measurements["left_px"], measurements["right_px"]
    top, bottom = measurements["top_px"], measurements["bottom_px"]
    line_width = max(2, w // 300)
    draw.rectangle([left, top, w - right, h - bottom], outline=_FLAG_COLOR, width=line_width)
    lr, tb = measurements["lr_ratio"], measurements["tb_ratio"]
    label = f"L/R {lr[0]:.0f}/{lr[1]:.0f}   T/B {tb[0]:.0f}/{tb[1]:.0f}"
    draw.text((10, 10), label, fill=_FLAG_COLOR)
    return img


def annotate_corners(card_image: np.ndarray, per_corner: dict, corner_fraction: float = 0.12) -> Image.Image:
    h, w = card_image.shape[:2]
    size = max(8, int(min(h, w) * corner_fraction))
    zoom = 3
    crops = corner_crops(card_image, corner_fraction)

    tiles = {}
    for name, crop in crops.items():
        pil_crop = _to_pil(crop).resize((size * zoom, size * zoom), Image.NEAREST)
        draw = ImageDraw.Draw(pil_crop)
        info = per_corner[name]
        color = _FLAG_COLOR if info["combined_score"] < 8 else _OK_COLOR
        draw.rectangle([0, 0, size * zoom - 1, size * zoom - 1], outline=color, width=4)
        draw.text((5, 5), f"{name.replace('_', ' ')}\n{info['combined_score']:.1f}/10", fill=color)
        tiles[name] = pil_crop

    composite = Image.new("RGB", (size * zoom * 2, size * zoom * 2), (255, 255, 255))
    composite.paste(tiles["top_left"], (0, 0))
    composite.paste(tiles["top_right"], (size * zoom, 0))
    composite.paste(tiles["bottom_left"], (0, size * zoom))
    composite.paste(tiles["bottom_right"], (size * zoom, size * zoom))
    return composite


def annotate_edges(
    card_image: np.ndarray,
    per_edge: dict,
    corner_exclusion_fraction: float = 0.12,
    strip_depth_fraction: float = 0.04,
) -> Image.Image:
    img = _to_pil(card_image).convert("RGB")
    draw = ImageDraw.Draw(img)
    h, w = card_image.shape[:2]
    ex_h, ex_w = int(h * corner_exclusion_fraction), int(w * corner_exclusion_fraction)
    depth_h = max(2, int(h * strip_depth_fraction))
    depth_w = max(2, int(w * strip_depth_fraction))

    boxes = {
        "top": (ex_w, 0, w - ex_w, depth_h),
        "bottom": (ex_w, h - depth_h, w - ex_w, h),
        "left": (0, ex_h, depth_w, h - ex_h),
        "right": (w - depth_w, ex_h, w, h - ex_h),
    }
    for name, box in boxes.items():
        color = _FLAG_COLOR if per_edge[name]["score"] < 8 else _OK_COLOR
        draw.rectangle(box, outline=color, width=3)
    return img


def annotate_surface(
    card_image: np.ndarray, anomaly_mask: np.ndarray, corner_exclusion_fraction: float = 0.12
) -> Image.Image:
    h, w = card_image.shape[:2]
    ex_h, ex_w = int(h * corner_exclusion_fraction), int(w * corner_exclusion_fraction)
    rgb = cv2.cvtColor(card_image, cv2.COLOR_BGR2RGB).copy()

    face = rgb[ex_h : h - ex_h, ex_w : w - ex_w]
    overlay = face.copy()
    overlay[anomaly_mask] = [255, 0, 0]
    blended = cv2.addWeighted(face, 0.6, overlay, 0.4, 0)
    rgb[ex_h : h - ex_h, ex_w : w - ex_w] = blended
    return Image.fromarray(rgb)
