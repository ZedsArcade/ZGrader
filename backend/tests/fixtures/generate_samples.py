"""Synthetic flatbed-scan-like card images for tests and the drift harness.

Not photorealistic, but structurally faithful to a real scan: printed border
reaches the physical edge, sits on dark scanner backing, and carries whatever
controlled defect the caller asks for. That is the point -- a synthetic fixture
has *exact* ground truth, so a test can assert "this card is 65/35" rather than
"this card looks about right", which no real photograph can support.

**Everything here must stay deterministic.** The drift harness compares each
fixture's metrics against a committed baseline, so a fixture that changes
between runs would report drift that isn't there and train everyone to ignore
the alarm. Any noise, sparkle or grain therefore draws from a seeded generator
rather than the global numpy RNG.

What synthetics deliberately cannot do: real paper texture, genuine holo
interference, actual corner wear, and the lighting of a hand-held phone. The
real photographs in `real_scans/` cover that; see its README. Synthetics carry
the numeric assertions, real photos guard against tuning the pipeline to
synthetic quirks.
"""

from pathlib import Path

import cv2
import numpy as np

DPI = 600
MM_PER_INCH = 25.4

# Palettes, kept as named constants so a fixture reads as its intent rather
# than a tuple of numbers.
_CLASSIC_BORDER = (160, 60, 30)  # BGR -- a blue-heavy border
_CLASSIC_INNER = (80, 180, 200)
_WHITE_BORDER = (238, 240, 242)
_DARK_ART = (48, 40, 66)
_WHITENING = (235, 235, 235)


def _mm_to_px(mm: float) -> int:
    return int(round(mm * DPI / MM_PER_INCH))


def _rng(seed: int) -> np.random.Generator:
    """A fixture's own generator. Never the global RNG -- see the module
    docstring on why determinism is load-bearing here."""
    return np.random.default_rng(seed)


#: Die-cut corner radius of a real trading card, in millimetres -- about a 3mm
#: diameter. Kept here rather than imported from the analysis package on
#: purpose: a fixture that derives its ground truth from the code under test
#: cannot contradict it, which is the one thing a fixture is for.
_CORNER_RADIUS_MM = 1.5


def _round_corners(card: np.ndarray, radius_px: int) -> np.ndarray:
    """Cut the card's four corners to a radius, leaving backing behind them.

    Anti-aliased, because a real die cut crossing a sensor pixel produces an
    intermediate value and the sub-pixel edge fitting downstream is built to
    read exactly that. A hard binary cut would hand it a cleaner signal than
    any real photograph contains.
    """
    h, w = card.shape[:2]
    supersample = 4
    big = np.zeros((h * supersample, w * supersample), dtype=np.uint8)
    r = radius_px * supersample
    cv2.rectangle(big, (r, 0), (w * supersample - r, h * supersample), 255, -1)
    cv2.rectangle(big, (0, r), (w * supersample, h * supersample - r), 255, -1)
    for cx, cy in (
        (r, r),
        (w * supersample - r, r),
        (r, h * supersample - r),
        (w * supersample - r, h * supersample - r),
    ):
        cv2.circle(big, (cx, cy), r, 255, -1)
    alpha = cv2.resize(big, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0

    backing = np.zeros_like(card, dtype=np.float32)
    return (card.astype(np.float32) * alpha[:, :, None] + backing * (1 - alpha[:, :, None])).astype(
        np.uint8
    )


def _add_foil_texture(card: np.ndarray, seed: int) -> None:
    """Approximate holo: bright, high-local-variance speckle in broad bands.

    Enough to exercise the surface detector's false-positive behaviour and any
    future foil mask, without pretending to be real interference patterning.
    """
    rng = _rng(seed)
    h, w = card.shape[:2]
    # Diagonal banding, the coarse structure holo actually has.
    yy, xx = np.mgrid[0:h, 0:w]
    bands = (np.sin((xx + yy) / (w * 0.03)) + 1.0) / 2.0
    sparkle = rng.random((h, w))
    mask = (bands * sparkle) > 0.72
    boost = np.zeros((h, w, 3), dtype=np.int16)
    boost[mask] = (70, 55, 90)
    np.clip(card.astype(np.int16) + boost, 0, 255, out=boost)
    card[:] = boost.astype(np.uint8)


def _add_grain(image: np.ndarray, seed: int, sigma: float) -> np.ndarray:
    rng = _rng(seed)
    noise = rng.normal(0.0, sigma, image.shape)
    return np.clip(image.astype(np.float64) + noise, 0, 255).astype(np.uint8)


def _add_glare(image: np.ndarray, strength: float = 0.85) -> np.ndarray:
    """A blown-out specular patch, as a phone flash produces on a sleeve.

    Clipped highlights are exactly what the planned capture-QC gate measures,
    and what makes surface analysis meaningless over the affected area.
    """
    h, w = image.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h * 0.35, w * 0.6
    radius = min(h, w) * 0.28
    falloff = np.exp(-(((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * radius**2)))
    lifted = image.astype(np.float64) + (255.0 - image) * (falloff[..., None] * strength)
    return np.clip(lifted, 0, 255).astype(np.uint8)


def _keystone(image: np.ndarray, amount: float) -> np.ndarray:
    """Perspective distortion, i.e. a card photographed off-square.

    Distinct from `rotation_deg`, which is in-plane and harmless: keystone is
    what makes a card's near edge read wider than its far edge, which is how a
    tilt silently corrupts a centering measurement.
    """
    h, w = image.shape[:2]
    inset = w * amount
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[inset, 0], [w - inset * 0.2, 0], [w, h], [0, h]])
    matrix = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(image, matrix, (w, h), borderValue=(0, 0, 0))


def make_card_scan(
    width_mm: float,
    height_mm: float,
    *,
    border_color: tuple[int, int, int] = _CLASSIC_BORDER,
    inner_color: tuple[int, int, int] = _CLASSIC_INNER,
    border_frac: float = 0.06,
    lr_offset_frac: float = 0.0,
    tb_offset_frac: float = 0.0,
    frame_tilt_frac: float = 0.0,
    whiten_top_left_corner: bool = False,
    clip_top_left_corner: bool = False,
    whiten_right_edge: bool = False,
    add_surface_scratch: bool = False,
    rotation_deg: float = 0.0,
    # --- added for the phase-1 fixture set -------------------------------
    full_art: bool = False,
    foil: bool = False,
    seed: int = 0,
    grain_sigma: float = 0.0,
    blur_sigma: float = 0.0,
    glare: bool = False,
    keystone_amount: float = 0.0,
    scale: float = 1.0,
) -> np.ndarray:
    """Build one synthetic scan.

    Every keyword above the divider predates the fixture set and is relied on
    by test_corners, test_edges, test_surface and test_regions -- their
    defaults must not change or those tests start measuring a different card.
    """
    card_w, card_h = _mm_to_px(width_mm), _mm_to_px(height_mm)
    card = np.full((card_h, card_w, 3), border_color, dtype=np.uint8)

    if not full_art:
        base_border_w = int(card_w * border_frac)
        base_border_h = int(card_h * border_frac)
        lr_shift = int(base_border_w * lr_offset_frac)
        tb_shift = int(base_border_h * tb_offset_frac)

        left = base_border_w + lr_shift
        right = base_border_w - lr_shift
        top = base_border_h + tb_shift
        bottom = base_border_h - tb_shift

        if frame_tilt_frac:
            # A diamond cut: the card trimmed at an angle to its own printing,
            # so the border widens steadily down one side and narrows down the
            # other. Its *average* width is unchanged, which is the point --
            # a card like this reads as perfectly centred to any measurement
            # that takes one number per side, and graders penalise it anyway.
            shift = int(base_border_w * frame_tilt_frac)
            quad = np.array(
                [
                    [left - shift, top],
                    [card_w - right - shift, top],
                    [card_w - right + shift, card_h - bottom],
                    [left + shift, card_h - bottom],
                ],
                dtype=np.int32,
            )
            cv2.fillPoly(card, [quad], inner_color)
        else:
            cv2.rectangle(
                card, (left, top), (card_w - right, card_h - bottom), inner_color, thickness=-1
            )
    else:
        # Borderless: artwork runs to the cut edge, so there is no inner frame
        # to find. This is the case centering genuinely cannot measure without
        # a reference image, and the fixture exists to prove the pipeline says
        # so rather than inventing a ratio.
        cv2.rectangle(card, (0, 0), (card_w, card_h), inner_color, thickness=-1)
        cv2.circle(card, (card_w // 2, card_h // 3), int(card_w * 0.3), border_color, thickness=-1)

    if foil:
        _add_foil_texture(card, seed)

    if whiten_top_left_corner:
        wc = max(6, int(min(card_w, card_h) * 0.03))
        card[0:wc, 0:wc] = _WHITENING

    if clip_top_left_corner:
        # Same colour as the backing below -- simulates a corner physically
        # missing material, which after deskew shows as backing at the ideal
        # tip position.
        nc = max(6, int(min(card_w, card_h) * 0.025))
        card[0:nc, 0:nc] = (0, 0, 0)

    if whiten_right_edge:
        strip_h0, strip_h1 = int(card_h * 0.35), int(card_h * 0.55)
        strip_w = max(4, int(card_w * 0.015))
        card[strip_h0:strip_h1, card_w - strip_w : card_w] = _WHITENING

    if add_surface_scratch:
        cv2.line(
            card,
            (int(card_w * 0.3), int(card_h * 0.4)),
            (int(card_w * 0.6), int(card_h * 0.5)),
            (255, 255, 255),
            thickness=3,
        )

    # Place on a dark scanner-backing canvas with a comfortable margin.
    # Real cards are die-cut to a rounded corner, roughly 1.5mm radius. Every
    # fixture used to have perfect square corners, which made them the easiest
    # possible input for corner analysis: the measurement that matters there is
    # material missing *beyond* the factory rounding, and a square-cornered
    # card has no factory rounding to forgive. The nominal subtraction was
    # therefore never exercised, and a clean corner's small area deficit was
    # contour-tracing noise being read as if it were a corner radius.
    #
    # Applied after every card feature so damage painted at a corner is cut by
    # the same curve the real card would have been.
    corner_radius_px = max(2, int(round(_CORNER_RADIUS_MM * card_h / height_mm)))
    card = _round_corners(card, corner_radius_px)

    margin = int(min(card_w, card_h) * 0.08)
    canvas_w, canvas_h = card_w + margin * 2, card_h + margin * 2
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    canvas[margin : margin + card_h, margin : margin + card_w] = card

    if rotation_deg:
        matrix = cv2.getRotationMatrix2D((canvas_w / 2, canvas_h / 2), rotation_deg, 1.0)
        canvas = cv2.warpAffine(canvas, matrix, (canvas_w, canvas_h), borderValue=(0, 0, 0))

    # --- capture degradation, applied last so it affects the whole frame ---
    if keystone_amount:
        canvas = _keystone(canvas, keystone_amount)
    if blur_sigma:
        canvas = cv2.GaussianBlur(canvas, (0, 0), blur_sigma)
    if glare:
        canvas = _add_glare(canvas)
    if grain_sigma:
        canvas = _add_grain(canvas, seed + 1, grain_sigma)
    if scale != 1.0:
        # Downscaling is how a low-resolution capture is simulated: the card
        # ends up spanning fewer pixels per millimetre, which is the thing that
        # actually makes corner wear invisible.
        canvas = cv2.resize(
            canvas, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA
        )

    return canvas


# ---------------------------------------------------------------------------
# The fixture catalogue.
#
# Each entry is (name, card size, kwargs). Names are stable identifiers -- the
# drift baseline is keyed on them, so renaming one reads as "old fixture gone,
# new fixture appeared" rather than a rename.
# ---------------------------------------------------------------------------

_POKEMON = (63.0, 88.0)
_YUGIOH = (59.0, 86.0)

FIXTURES: tuple[tuple[str, tuple[float, float], dict], ...] = (
    # --- the original four, unchanged: existing tests depend on these ---
    (
        "pokemon_front",
        _POKEMON,
        dict(
            lr_offset_frac=0.3,
            whiten_top_left_corner=True,
            whiten_right_edge=True,
            add_surface_scratch=True,
            rotation_deg=1.5,
        ),
    ),
    ("pokemon_back", _POKEMON, dict(rotation_deg=-0.8)),
    ("yugioh_front", _YUGIOH, dict(lr_offset_frac=-0.15, tb_offset_frac=0.1)),
    ("yugioh_back", _YUGIOH, dict()),
    # --- card stock the pipeline handles differently ---
    (
        "full_art_centered",
        _POKEMON,
        dict(full_art=True, seed=11),
    ),
    (
        "full_art_foil",
        _POKEMON,
        dict(full_art=True, foil=True, seed=12),
    ),
    (
        "foil_bordered",
        _POKEMON,
        dict(foil=True, seed=13),
    ),
    (
        # Corner whitening on a white border is near-undetectable by a
        # saturation drop, because there is barely any saturation to lose.
        # The fixture exists so that limitation is measured, not assumed.
        "white_border_worn_corner",
        _POKEMON,
        dict(border_color=_WHITE_BORDER, inner_color=_DARK_ART, whiten_top_left_corner=True),
    ),
    ("white_border_clean", _POKEMON, dict(border_color=_WHITE_BORDER, inner_color=_DARK_ART)),
    # --- damage, isolated so a change can be attributed ---
    ("damage_corner_clipped", _POKEMON, dict(clip_top_left_corner=True)),
    ("damage_edge_whitened", _POKEMON, dict(whiten_right_edge=True)),
    # Printed straight, trimmed crooked. Averages to a centred card, so it is
    # the case a per-side median cannot see at all.
    ("centering_diamond_cut", _POKEMON, dict(frame_tilt_frac=0.14)),
    ("damage_surface_scratch", _POKEMON, dict(add_surface_scratch=True)),
    (
        "damage_all",
        _POKEMON,
        dict(
            whiten_top_left_corner=True,
            clip_top_left_corner=False,
            whiten_right_edge=True,
            add_surface_scratch=True,
        ),
    ),
    # --- centering extremes, with exact known ground truth ---
    ("centering_perfect", _POKEMON, dict()),
    ("centering_offset_mild", _POKEMON, dict(lr_offset_frac=0.2)),
    ("centering_offset_severe", _POKEMON, dict(lr_offset_frac=0.6, tb_offset_frac=0.4)),
    # --- deliberately bad captures ---
    ("capture_soft", _POKEMON, dict(blur_sigma=6.0)),
    ("capture_tilted", _POKEMON, dict(keystone_amount=0.08)),
    ("capture_glared", _POKEMON, dict(glare=True)),
    ("capture_noisy", _POKEMON, dict(grain_sigma=14.0, seed=21)),
    (
        # ~7 px/mm, far below the ~25 the brief calls the floor for seeing
        # corner wear at all.
        "capture_low_resolution",
        _POKEMON,
        dict(scale=0.3, whiten_top_left_corner=True),
    ),
    (
        # Everything a bad phone photo does at once.
        "capture_worst_case",
        _POKEMON,
        dict(blur_sigma=4.0, keystone_amount=0.06, glare=True, grain_sigma=9.0, seed=22),
    ),
)


def build_fixture(name: str) -> np.ndarray:
    for fixture_name, (w_mm, h_mm), kwargs in FIXTURES:
        if fixture_name == name:
            return make_card_scan(w_mm, h_mm, **kwargs)
    raise KeyError(f"Unknown fixture: {name}")


def fixture_names() -> tuple[str, ...]:
    return tuple(name for name, _size, _kwargs in FIXTURES)


def card_size_mm(name: str) -> tuple[float, float]:
    """The card's true physical size, which is the scale ground truth -- see
    analysis/scale.py on why image DPI is not usable for this."""
    for fixture_name, size, _kwargs in FIXTURES:
        if fixture_name == name:
            return size
    raise KeyError(f"Unknown fixture: {name}")


def write_sample_set(output_dir: Path) -> dict[str, Path]:
    """Write only the four original scans.

    Kept narrow on purpose: conftest's `sample_scan_paths` fixture and the
    dev_trigger workflow both expect exactly these, and the wider catalogue is
    built in memory by the drift harness rather than written to disk.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name in ("pokemon_front", "pokemon_back", "yugioh_front", "yugioh_back"):
        path = output_dir / f"{name}.png"
        cv2.imwrite(str(path), build_fixture(name), [cv2.IMWRITE_PNG_COMPRESSION, 1])
        paths[name] = path
    return paths


def write_all_fixtures(output_dir: Path) -> dict[str, Path]:
    """Write the whole catalogue, for eyeballing what the harness measures."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name in fixture_names():
        path = output_dir / f"{name}.png"
        cv2.imwrite(str(path), build_fixture(name), [cv2.IMWRITE_PNG_COMPRESSION, 1])
        paths[name] = path
    return paths


if __name__ == "__main__":
    written = write_sample_set(Path(__file__).parent / "sample_scans")
    for name, path in written.items():
        print(f"{name}: {path}")
