"""Generate the figures published on the public /methodology page.

Every figure here is real detector output. The page's whole purpose is to
show how the analysis reaches its conclusions -- including where it gets
things wrong -- so a hand-drawn diagram of what the code *ought* to do would
defeat the point. Run this script and the pictures follow the code.

Re-run it after tuning any threshold in analysis/, or the page slowly turns
into a claim the software no longer supports:

    cd backend && python scripts/generate_methodology_figures.py

The demonstration card is synthetic, and the page says so. Two reasons, both
deliberate: a real card's artwork belongs to its publisher and this is a
commercial page, and a customer's scan is their private property. A card
built here is nobody's but ours -- while still carrying the things that
actually drive the analysis: a printed border, an off-centre cut, body text
(the dominant false positive), a hairline scratch, corner whitening, an edge
whitening run, and a crease.

Output is deterministic: fixed geometry, fixed text, no randomness beyond a
seeded texture, so re-running produces no spurious diff.
"""

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from zgrader.analysis import scale  # noqa: E402
from zgrader.analysis.annotate import annotate_surface, to_pil  # noqa: E402
from zgrader.analysis.centering import measure_centering  # noqa: E402
from zgrader.analysis.corners import corner_crops, measure_corners  # noqa: E402
from zgrader.analysis.creases import detect_creases  # noqa: E402
from zgrader.analysis.edges import measure_edges  # noqa: E402
from zgrader.analysis.preprocessing import locate_and_deskew  # noqa: E402
from zgrader.analysis.regions import build_regions  # noqa: E402
from zgrader.analysis.surface import measure_surface  # noqa: E402

# Card geometry. 300 px/inch is plenty for a figure that renders ~700px wide
# on the page, and keeps the committed figures small.
CARD_W_MM, CARD_H_MM = 63.0, 88.0
RENDER_DPI = 300

FLAG = (220, 30, 30)
ACCENT = (0, 140, 200)
OK = (30, 160, 30)

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


def _mm(value: float) -> int:
    return int(round(value * RENDER_DPI / 25.4))


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = _FONT_CANDIDATES[1 if bold else 0]
    if Path(path).exists():
        return ImageFont.truetype(path, size)
    # Bitmap fallback: the figures still generate on a host without DejaVu,
    # they just look plainer. Never a crash -- this script is documentation.
    return ImageFont.load_default(size=size)


# --------------------------------------------------------------------------
# The demonstration card
# --------------------------------------------------------------------------


def build_demo_scan() -> np.ndarray:
    """A card-like image on scanner backing, carrying every feature the
    analysis reacts to. Returned in OpenCV BGR, like a real scan."""
    card_w, card_h = _mm(CARD_W_MM), _mm(CARD_H_MM)
    # Dark printed border against a light interior. The contrast is deliberate:
    # centering.py looks for the *strongest* luminance gradient within 15% of
    # each edge, so anything else printed near the edge competes with the
    # border for that measurement. On a real card the border wins comfortably;
    # this demonstration card keeps it that way rather than staging a failure
    # the figure would then misattribute.
    # Deep red rather than a near-black: corners.py and edges.py detect wear
    # as a *saturation* drop toward bare cardstock, so an unsaturated border
    # would make a whitened corner unremarkable and the figure would show a
    # perfect card. Real card borders are printed ink, and printed ink is
    # saturated.
    card = Image.new("RGB", (card_w, card_h), (122, 26, 34))
    draw = ImageDraw.Draw(card)

    # Off-centre left/right, near-square top/bottom -- a plausible bad cut.
    #
    # The border width is pinned between two constraints, because one card has
    # to demonstrate every category at once:
    #
    #   >= 8% of the width on its narrow side, so the edge sampler's local
    #        reference (outer 4%, reference the next 4% inward) stays on the
    #        printed border instead of drifting onto the card interior;
    #   <= 12%          on its wide side, so the border/interior transition
    #        stays inside the margin surface.py excludes -- otherwise the
    #        printed edge itself lights up as a surface anomaly and swamps the
    #        genuine findings the figure exists to show.
    #
    # Real card borders sit comfortably inside that range; this is a
    # constraint on the demonstration, not on the analysis.
    border = int(card_w * 0.10)
    lr_shift = int(border * 0.15)
    tb_shift = int(border * 0.05)
    frame = [border + lr_shift, border + tb_shift, card_w - border + lr_shift, card_h - border + tb_shift]
    draw.rectangle(frame, fill=(238, 232, 214))

    inner_w = frame[2] - frame[0]

    # Card name: text on the interior, not a filled title bar. A full-width
    # bar this close to the edge would out-gradient the border itself.
    draw.text(
        (frame[0] + _mm(3), frame[1] + _mm(2)),
        "DEMONSTRATION CARD",
        font=_font(int(card_h * 0.021), bold=True),
        fill=(58, 52, 44),
    )

    # Art panel: a soft gradient rather than artwork. Enough structure for the
    # surface pass to have something to look at, muted enough not to compete
    # with the border.
    art_top = frame[1] + _mm(7)
    art_bottom = art_top + int(card_h * 0.40)
    art = np.zeros((art_bottom - art_top, inner_w - _mm(6), 3), dtype=np.uint8)
    rows = np.linspace(120, 175, art.shape[0], dtype=np.uint8)[:, None]
    art[:, :, 0] = rows
    art[:, :, 1] = (rows * 0.82).astype(np.uint8)
    art[:, :, 2] = (rows * 0.70).astype(np.uint8)
    card.paste(Image.fromarray(art), (frame[0] + _mm(3), art_top))

    # Body text. This is the point of the whole exercise: printed text is the
    # dominant surface false positive, so the demonstration card has to carry
    # real glyphs rather than a grey box pretending to be text.
    text_font = _font(int(card_h * 0.019))
    text_y = art_bottom + _mm(3)
    for line in (
        "When this card is scanned, the surface pass",
        "sees printed text as local contrast, exactly",
        "as it sees a scratch. The stroke-thickness",
        "filter is what tells the two apart.",
    ):
        draw.text((frame[0] + _mm(3), text_y), line, font=text_font, fill=(40, 36, 30))
        text_y += int(card_h * 0.026)

    card_bgr = cv2.cvtColor(np.array(card), cv2.COLOR_RGB2BGR)

    # Paper texture, seeded so the committed figures don't churn.
    rng = np.random.default_rng(20260727)
    noise = rng.normal(0, 2.0, card_bgr.shape)
    card_bgr = np.clip(card_bgr.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    # A hairline scratch: thin, long, brighter than what it crosses. This is
    # the finding that should survive the filter. Drawn at ~0.25mm rather than
    # a true hairline because the deskew warp resamples the image, and a
    # single-pixel line washes out in that resample -- it would be absent from
    # the figure for a reason that has nothing to do with the detector.
    cv2.line(
        card_bgr,
        (int(card_w * 0.28), int(card_h * 0.30)),
        (int(card_w * 0.68), int(card_h * 0.46)),
        (252, 252, 252),
        thickness=max(2, _mm(0.25)),
        lineType=cv2.LINE_AA,
    )

    # A crease: a faint tonal line running across the card, ignoring the
    # design. Wider and much lower contrast than the scratch.
    crease = card_bgr.copy()
    cv2.line(
        crease,
        (int(card_w * 0.10), int(card_h * 0.66)),
        (int(card_w * 0.90), int(card_h * 0.74)),
        (150, 140, 125),
        thickness=max(2, _mm(0.35)),
        lineType=cv2.LINE_AA,
    )
    card_bgr = cv2.addWeighted(card_bgr, 0.45, crease, 0.55, 0)

    # Corner whitening (worn to the cardstock) and an edge whitening run.
    wc = int(min(card_w, card_h) * 0.035)
    card_bgr[0:wc, 0:wc] = (238, 238, 240)
    strip = max(3, int(card_w * 0.012))
    card_bgr[int(card_h * 0.36) : int(card_h * 0.56), card_w - strip : card_w] = (236, 236, 238)

    # Scanner backing, and a slight rotation so the deskew step has something
    # real to correct -- as it would on any actual scan.
    margin = int(min(card_w, card_h) * 0.08)
    canvas = np.zeros((card_h + margin * 2, card_w + margin * 2, 3), dtype=np.uint8)
    canvas[margin : margin + card_h, margin : margin + card_w] = card_bgr
    matrix = cv2.getRotationMatrix2D((canvas.shape[1] / 2, canvas.shape[0] / 2), 1.4, 1.0)
    return cv2.warpAffine(
        canvas, matrix, (canvas.shape[1], canvas.shape[0]), borderValue=(0, 0, 0)
    )


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------


def _save(image: Image.Image, path: Path, target_width: int = 720) -> None:
    """Write a figure, downscaled to something a web page wants.

    JPEG rather than PNG: these are photographic-looking images carrying paper
    grain, and PNG cannot compress noise -- the same figures came out at
    ~750KB each, over 3MB for the page. At quality 88 they're a tenth of that
    and the annotation lines still read cleanly.
    """
    if image.width > target_width:
        height = int(image.height * target_width / image.width)
        image = image.resize((target_width, height), Image.LANCZOS)
    image.convert("RGB").save(path, quality=88, subsampling=0, optimize=True)
    print(f"  {path.name}  {image.width}x{image.height}  {path.stat().st_size // 1024}KB")


def figure_centering(card: np.ndarray, result: dict, out: Path) -> None:
    """The four measured border widths, labelled in millimetres."""
    img = to_pil(card).convert("RGB")
    draw = ImageDraw.Draw(img)
    h, w = card.shape[:2]
    m = result["measurements"]
    left, right, top, bottom = m["left_px"], m["right_px"], m["top_px"], m["bottom_px"]
    line_width = max(2, w // 250)
    font = _font(max(14, w // 26), bold=True)

    draw.rectangle([left, top, w - right, h - bottom], outline=FLAG, width=line_width)

    # Each measurement drawn where it was actually taken, so the number and
    # the gap it describes are unmistakably the same thing. The vertical pair
    # sits right of centre to leave the bottom-left clear for the summary.
    mid_y, mid_x = h // 2, int(w * 0.62)
    for x0, y0, x1, y1, label, anchor in (
        (0, mid_y, left, mid_y, f"{m['left_mm']:.1f}mm", "lm"),
        (w - right, mid_y, w, mid_y, f"{m['right_mm']:.1f}mm", "rm"),
        (mid_x, 0, mid_x, top, f"{m['top_mm']:.1f}mm", "ma"),
        (mid_x, h - bottom, mid_x, h, f"{m['bottom_mm']:.1f}mm", "md"),
    ):
        draw.line([x0, y0, x1, y1], fill=ACCENT, width=line_width)
        tx, ty = (x0 + x1) / 2, (y0 + y1) / 2
        draw.text((tx, ty), label, font=font, fill=ACCENT, anchor=anchor,
                  stroke_width=3, stroke_fill=(255, 255, 255))

    # Bottom-left, clear of the top and centre labels drawn above.
    lr, tb = m["lr_ratio"], m["tb_ratio"]
    draw.text(
        (w * 0.04, h * 0.965),
        f"L/R {lr[0]:.0f}/{lr[1]:.0f}    T/B {tb[0]:.0f}/{tb[1]:.0f}",
        font=font,
        fill=FLAG,
        anchor="ld",
        stroke_width=3,
        stroke_fill=(255, 255, 255),
    )
    _save(img, out / "centering.jpg")


def figure_corner(card: np.ndarray, result: dict, out: Path) -> None:
    """The two regions a corner's score is a comparison between."""
    crops = corner_crops(card)
    crop = crops["top_left"]
    size = crop.shape[0]
    zoom = max(4, 420 // max(1, size))
    img = to_pil(crop).resize((size * zoom, size * zoom), Image.NEAREST).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = _font(max(13, size * zoom // 22), bold=True)

    # Mirrors corners.py exactly: tip is the first 25%, the reference strip
    # is the lower 40% of the outer 15%.
    tip = max(3, int(size * 0.25)) * zoom
    ref_x1 = max(2, int(size * 0.15)) * zoom
    ref_y0 = int(size * 0.6) * zoom

    draw.rectangle([0, 0, tip, tip], outline=FLAG, width=4)
    draw.text((tip + 8, 6), "tip", font=font, fill=FLAG,
              stroke_width=3, stroke_fill=(255, 255, 255))
    draw.rectangle([0, ref_y0, ref_x1, size * zoom - 1], outline=OK, width=4)
    draw.text((ref_x1 + 8, ref_y0 + 6), "reference", font=font, fill=OK,
              stroke_width=3, stroke_fill=(255, 255, 255))

    info = result["measurements"]["per_corner"]["top_left"]
    draw.text(
        (size * zoom - 8, size * zoom - 8),
        f"saturation {info['tip_saturation']:.0f} vs {info['reference_saturation']:.0f}",
        font=font,
        fill=(20, 20, 20),
        anchor="rd",
        stroke_width=3,
        stroke_fill=(255, 255, 255),
    )
    _save(img, out / "corner.jpg", target_width=520)


def figure_surface_pair(card: np.ndarray, mask: np.ndarray, regions: list[dict], out: Path) -> None:
    """The honest pair: everything the detector noticed, then what survived.

    Left-hand figure is the raw >3-sigma variance mask -- text and all. The
    right-hand one is what the stroke-thickness and elongation filters left
    behind. The gap between them is the false-positive rejection, and any
    box still sitting on text in the second image is a false positive that
    got through, which the page says out loud.
    """
    _save(annotate_surface(card, mask), out / "surface-raw.jpg")

    img = to_pil(card).convert("RGB")
    draw = ImageDraw.Draw(img)
    h, w = card.shape[:2]
    line_width = max(2, w // 250)
    for region in regions:
        x0, y0, x1, y1 = region["bbox_norm"]
        draw.rectangle([x0 * w, y0 * h, x1 * w, y1 * h], outline=FLAG, width=line_width)
    _save(img, out / "surface-filtered.jpg")


def figure_crease(card: np.ndarray, creases: list[dict], out: Path) -> None:
    img = to_pil(card).convert("RGB")
    draw = ImageDraw.Draw(img)
    w = card.shape[1]
    for crease in creases:
        draw.line(
            [crease["p1"][0], crease["p1"][1], crease["p2"][0], crease["p2"][1]],
            fill=FLAG,
            width=max(2, w // 250),
        )
    _save(img, out / "crease.jpg")


def figure_edges(card: np.ndarray, result: dict, out: Path) -> None:
    """The sampled strip and the reference immediately inside it.

    Zoomed into the right-hand edge rather than shown on the whole card: the
    strips are 4% of the width each, which at full-card scale is a sliver too
    thin to see, let alone to see whitening in.
    """
    h, w = card.shape[:2]
    depth_w = max(2, int(w * 0.04))

    # A short vertical span: enough of the whitened run to read, without a
    # figure so tall it dwarfs the text beside it on the page.
    crop_x0 = w - int(w * 0.20)
    crop_y0, crop_y1 = int(h * 0.34), int(h * 0.52)
    crop = card[crop_y0:crop_y1, crop_x0:w]
    zoom = 440 / max(1, crop.shape[1])
    img = (
        to_pil(crop)
        .resize((int(crop.shape[1] * zoom), int(crop.shape[0] * zoom)), Image.LANCZOS)
        .convert("RGB")
    )
    draw = ImageDraw.Draw(img)
    font = _font(17, bold=True)
    line_width = 3

    outer_x0 = (w - depth_w - crop_x0) * zoom
    inner_x0 = (w - 2 * depth_w - crop_x0) * zoom
    bottom = img.height - 1

    draw.rectangle([outer_x0, 0, img.width - 1, bottom], outline=FLAG, width=line_width)
    draw.rectangle([inner_x0, 0, outer_x0, bottom], outline=ACCENT, width=line_width)
    draw.text((inner_x0 - 10, img.height * 0.35), "edge strip", font=font, fill=FLAG, anchor="rm",
              stroke_width=3, stroke_fill=(255, 255, 255))
    draw.text((inner_x0 - 10, img.height * 0.5), "local reference", font=font, fill=ACCENT,
              anchor="rm", stroke_width=3, stroke_fill=(255, 255, 255))

    right = result["measurements"]["per_edge"]["right"]
    draw.text(
        (img.width - 8, bottom - 8),
        f"{right['whitened_fraction'] * 100:.0f}% whitened",
        font=font,
        fill=(20, 20, 20),
        anchor="rd",
        stroke_width=3,
        stroke_fill=(255, 255, 255),
    )
    _save(img, out / "edges.jpg", target_width=440)


FIGURE_NAMES = (
    "centering.jpg",
    "corner.jpg",
    "edges.jpg",
    "surface-raw.jpg",
    "surface-filtered.jpg",
    "crease.jpg",
)


def generate(output_dir: Path) -> dict[str, object]:
    """Write every figure. Returns the analysis it drew them from, so a test
    can assert the figures still demonstrate what the page claims."""
    output_dir.mkdir(parents=True, exist_ok=True)

    scan = build_demo_scan()
    card, _info = locate_and_deskew(scan)
    px_per_mm = scale.px_per_mm(card.shape[:2], CARD_W_MM, CARD_H_MM)

    centering = measure_centering(card, px_per_mm)
    corners = measure_corners(card)
    edges = measure_edges(card)
    surface, mask = measure_surface(card)
    creases = detect_creases(card, px_per_mm)

    surface_regions = build_regions(
        surface["category"], card.shape[:2], px_per_mm, "en", surface, mask
    )

    print(f"Writing figures to {output_dir}")
    figure_centering(card, centering, output_dir)
    figure_corner(card, corners, output_dir)
    figure_edges(card, edges, output_dir)
    figure_surface_pair(card, mask, surface_regions, output_dir)
    figure_crease(card, creases, output_dir)

    return {
        "centering": centering,
        "corners": corners,
        "edges": edges,
        "surface": surface,
        "surface_regions": surface_regions,
        "creases": creases,
        "anomaly_mask": mask,
        "px_per_mm": px_per_mm,
    }


DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "methodology"


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    analysis = generate(target)
    print(
        f"\ncentering {analysis['centering']['raw_score']:.1f}/10   "
        f"corners {analysis['corners']['raw_score']:.1f}/10   "
        f"edges {analysis['edges']['raw_score']:.1f}/10   "
        f"surface {analysis['surface']['raw_score']:.1f}/10   "
        f"creases {len(analysis['creases'])}"
    )
