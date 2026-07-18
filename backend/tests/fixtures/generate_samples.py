"""Generates synthetic flatbed-scan-like sample images for tests and manual
dev_trigger runs. Not photorealistic, but structurally faithful to a real
scanned card: printed border reaches the physical edge, sits on a dark
scanner backing, and can carry a controlled centering offset, a whitened
corner, a whitened edge run, and a surface scratch -- so it exercises every
analysis module meaningfully.
"""

from pathlib import Path

import cv2
import numpy as np

DPI = 600
MM_PER_INCH = 25.4


def _mm_to_px(mm: float) -> int:
    return int(round(mm * DPI / MM_PER_INCH))


def make_card_scan(
    width_mm: float,
    height_mm: float,
    *,
    border_color: tuple[int, int, int] = (160, 60, 30),  # BGR
    inner_color: tuple[int, int, int] = (80, 180, 200),
    border_frac: float = 0.06,
    lr_offset_frac: float = 0.0,
    tb_offset_frac: float = 0.0,
    whiten_top_left_corner: bool = False,
    clip_top_left_corner: bool = False,
    whiten_right_edge: bool = False,
    add_surface_scratch: bool = False,
    rotation_deg: float = 0.0,
) -> np.ndarray:
    card_w, card_h = _mm_to_px(width_mm), _mm_to_px(height_mm)
    card = np.full((card_h, card_w, 3), border_color, dtype=np.uint8)

    base_border_w = int(card_w * border_frac)
    base_border_h = int(card_h * border_frac)
    lr_shift = int(base_border_w * lr_offset_frac)
    tb_shift = int(base_border_h * tb_offset_frac)

    left = base_border_w + lr_shift
    right = base_border_w - lr_shift
    top = base_border_h + tb_shift
    bottom = base_border_h - tb_shift

    cv2.rectangle(card, (left, top), (card_w - right, card_h - bottom), inner_color, thickness=-1)

    if whiten_top_left_corner:
        wc = max(6, int(min(card_w, card_h) * 0.03))
        card[0:wc, 0:wc] = (235, 235, 235)

    if clip_top_left_corner:
        # Same color as the canvas backing below -- simulates a corner
        # physically missing material (chipped/rounded), which after
        # deskew shows as backing color right at the ideal tip position.
        nc = max(6, int(min(card_w, card_h) * 0.025))
        card[0:nc, 0:nc] = (0, 0, 0)

    if whiten_right_edge:
        strip_h0, strip_h1 = int(card_h * 0.35), int(card_h * 0.55)
        strip_w = max(4, int(card_w * 0.015))
        card[strip_h0:strip_h1, card_w - strip_w : card_w] = (235, 235, 235)

    if add_surface_scratch:
        cv2.line(
            card,
            (int(card_w * 0.3), int(card_h * 0.4)),
            (int(card_w * 0.6), int(card_h * 0.5)),
            (255, 255, 255),
            thickness=3,
        )

    # Place on a dark scanner-backing canvas with a comfortable margin.
    margin = int(min(card_w, card_h) * 0.08)
    canvas_w, canvas_h = card_w + margin * 2, card_h + margin * 2
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    canvas[margin : margin + card_h, margin : margin + card_w] = card

    if rotation_deg:
        matrix = cv2.getRotationMatrix2D((canvas_w / 2, canvas_h / 2), rotation_deg, 1.0)
        canvas = cv2.warpAffine(canvas, matrix, (canvas_w, canvas_h), borderValue=(0, 0, 0))

    return canvas


def write_sample_set(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}

    pokemon_front = make_card_scan(
        63.0,
        88.0,
        lr_offset_frac=0.3,
        whiten_top_left_corner=True,
        whiten_right_edge=True,
        add_surface_scratch=True,
        rotation_deg=1.5,
    )
    p = output_dir / "pokemon_front.png"
    cv2.imwrite(str(p), pokemon_front, [cv2.IMWRITE_PNG_COMPRESSION, 1])
    paths["pokemon_front"] = p

    pokemon_back = make_card_scan(63.0, 88.0, rotation_deg=-0.8)
    p = output_dir / "pokemon_back.png"
    cv2.imwrite(str(p), pokemon_back, [cv2.IMWRITE_PNG_COMPRESSION, 1])
    paths["pokemon_back"] = p

    yugioh_front = make_card_scan(59.0, 86.0, lr_offset_frac=-0.15, tb_offset_frac=0.1)
    p = output_dir / "yugioh_front.png"
    cv2.imwrite(str(p), yugioh_front, [cv2.IMWRITE_PNG_COMPRESSION, 1])
    paths["yugioh_front"] = p

    yugioh_back = make_card_scan(59.0, 86.0)
    p = output_dir / "yugioh_back.png"
    cv2.imwrite(str(p), yugioh_back, [cv2.IMWRITE_PNG_COMPRESSION, 1])
    paths["yugioh_back"] = p

    return paths


if __name__ == "__main__":
    written = write_sample_set(Path(__file__).parent / "sample_scans")
    for name, path in written.items():
        print(f"{name}: {path}")
