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
