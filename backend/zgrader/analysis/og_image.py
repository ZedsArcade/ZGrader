"""The link-preview image for a shared report.

What most people see of a shared report is the unfurl in Discord or WhatsApp,
not the page -- so this image is the part that decides whether the channel works
at all. It carries the card, the four scores, and the framing that the page
carries above the fold, because for a lot of viewers the preview is all there is.

Drawn with PIL, in the same stack as `annotate.py`, deliberately. WeasyPrint is
the only HTML renderer here and it cannot help: `write_png` was dropped in v53
and this project is on 69, so `hasattr(html, "write_png")` is False. A second
rendering stack for one image is not worth owning.

**Nothing here is baked at analysis time.** A picture derived from the
measurements goes stale the moment a client adjusts a border or dismisses a
finding, which is the whole argument behind
`recompute.redraw_centering_annotations` being unconditional. That function stays
correct by never needing to remember what it drew last; this one gets the same
guarantee from a different direction -- the cache key *is* the state, so a change
makes the old file unreachable rather than wrongly served, and no mutation path
has to remember to regenerate anything. A path added later inherits that for
free, which matters because "something downstream forgot" is the failure mode
this codebase keeps meeting.

The card image drawn here is the plain `front_base.png`, never an annotated one.
That is a deliberate limit: an overlay would make this a fourth surface that has
to remap the centering frame from current widths, and at preview size the frame
is barely legible anyway.
"""

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from zgrader.models import AnalysisCategory, AnalysisSide, Submission
from zgrader.reports.strings import CATEGORY_LABELS

#: The size every unfurler expects. WhatsApp crops toward square on some
#: layouts, so nothing that matters sits near the left or right edge.
OG_WIDTH = 1200
OG_HEIGHT = 630
_MARGIN = 56

#: JPEG, not PNG. A 1200x630 composite containing a photograph lands around
#: 600KB-1MB as PNG, and WhatsApp has historically refused to show a preview
#: above roughly 300KB -- on the one client where size decides whether the
#: unfurl appears at all.
_JPEG_QUALITY = 85

_BACKGROUND = (17, 20, 28)
_FOREGROUND = (240, 242, 248)
_MUTED = (150, 158, 175)
_RULE = (44, 50, 64)
_ADJUSTED = (233, 74, 140)

# Same thresholds as the web scorecard's grade tiers (lib/grade-display.ts),
# compared after the same one-decimal rounding, so a score that *displays* as
# 9.5 cannot land in a different colour here than it does on the page.
_GEM = (94, 234, 212)
_MINT = (163, 230, 53)
_WARN = (251, 191, 36)

_CATEGORY_ORDER = ("centering", "corners", "edges", "surface")

#: Where a usable face might be. The container installs `fonts-dejavu-core`
#: already (backend/Dockerfile, for WeasyPrint); the repo-local copy is what
#: makes this work anywhere else.
_FONT_DIRS = (
    Path(__file__).resolve().parent.parent / "assets" / "fonts",
    Path("/usr/share/fonts/truetype/dejavu"),
)
_REGULAR = "DejaVuSans.ttf"
_BOLD = "DejaVuSans-Bold.ttf"

#: Characters this image genuinely needs and a font may quietly lack. Spanish
#: labels carry both accents, and a font missing them draws a tofu box rather
#: than failing -- so coverage has to be *checked*, not assumed from the file
#: existing. Pillow's own bundled fallback renders all three as tofu, which is
#: how this was found: a test asserting only the image's dimensions passed while
#: the Spanish preview was boxes.
_REQUIRED_GLYPHS = "áéíóúñ·"


def _renders_glyphs(font: ImageFont.FreeTypeFont) -> bool:
    """Whether `font` draws real glyphs for the characters this image needs.

    Compares each against a private-use codepoint, which no font defines: if a
    character rasterises identically to that, it is the missing-glyph box.
    """
    probe = Image.new("L", (64, 64), 0)
    ImageDraw.Draw(probe).text((4, 4), "", font=font, fill=255)
    tofu = probe.tobytes()
    for char in _REQUIRED_GLYPHS:
        candidate = Image.new("L", (64, 64), 0)
        ImageDraw.Draw(candidate).text((4, 4), char, font=font, fill=255)
        if candidate.tobytes() == tofu:
            return False
    return True


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """A scalable font at `size` that can actually draw what gets drawn.

    Falls back to Pillow's bundled face only when nothing better is present.
    That face cannot render accented Spanish, so `_renders_glyphs` is what stops
    a missing font from turning into a preview full of boxes instead of an
    error somebody notices.
    """
    name = _BOLD if bold else _REGULAR
    for directory in _FONT_DIRS:
        try:
            return ImageFont.truetype(str(directory / name), size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def fonts_cover_spanish() -> bool:
    """Whether the resolved font can draw accented text.

    Exposed so a test can assert it rather than leave it to be discovered by
    somebody looking at a Spanish unfurl.
    """
    return _renders_glyphs(_font(24))


def _tier_color(score: float) -> tuple[int, int, int]:
    rounded = round(score * 10) / 10
    if rounded >= 9.9:
        return _GEM
    if rounded >= 9.5:
        return _MINT
    return _WARN


def _combined_scores(submission: Submission) -> dict[str, float | None]:
    """The four category scores as currently assessed.

    Read from the combined rows rather than recomputed here: `toggle_region` and
    `adjust_centering` both run `recompute_submission`, so those rows already
    reflect dismissals and adjustments. Only *drawings* go stale in this
    codebase, never the numbers.
    """
    scores: dict[str, float | None] = {}
    for row in submission.analysis_results:
        if row.side != AnalysisSide.combined:
            continue
        if not isinstance(row.category, AnalysisCategory):
            continue
        scores[row.category.value] = (
            float(row.raw_score) if row.raw_score is not None else None
        )
    return scores


def fingerprint(submission: Submission) -> str:
    """A short hash of everything this image is drawn from.

    This is the invalidation mechanism, and the reason there is nothing to
    remember. Every input that can change the picture is in here, so a change
    produces a different filename *and* a different URL -- the previous image
    becomes unreachable rather than stale. Adding a new way to mutate a
    submission cannot silently leave a wrong preview behind, provided whatever
    it changes is one of these.

    Deliberately includes the *cleared* states too (an empty adjustment map
    hashes differently from a populated one), because reverting an adjustment
    has to change the fingerprint back -- that direction is the one nobody
    thinks to check, and it is exactly where the equivalent bug lived before
    `redraw_centering_annotations` became unconditional.
    """
    card = submission.card
    payload = {
        "scores": _combined_scores(submission),
        "adjusted": bool(submission.client_adjusted),
        "dismissed": sorted(submission.dismissed_regions or []),
        "centering": submission.centering_adjustments or {},
        "card": [
            card.card_name if card else None,
            card.set_name if card else None,
            card.card_number if card else None,
            card.foil if card else False,
        ],
        "language": submission.language.value,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _draw_card_photo(canvas: Image.Image, photo_path: Path, box: tuple[int, int, int, int]) -> int:
    """Fit the card into `box`, centred, and return the x its right edge reached.

    Returns the edge rather than assuming it, because a card's aspect ratio is
    not fixed -- the games this handles differ, and a Yu-Gi-Oh card is a
    different shape from a Pokemon one.
    """
    left, top, right, bottom = box
    if not photo_path.is_file():
        return left

    with Image.open(photo_path) as photo:
        card = photo.convert("RGB")
        card.thumbnail((right - left, bottom - top), Image.Resampling.LANCZOS)
        x = left
        y = top + (bottom - top - card.height) // 2
        canvas.paste(card, (x, y))
        # A hairline so a pale card does not bleed into a dark background.
        ImageDraw.Draw(canvas).rectangle(
            [x, y, x + card.width - 1, y + card.height - 1], outline=_RULE, width=2
        )
        return x + card.width


def _truncate(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text
    ellipsis = "…"
    while text and draw.textlength(text + ellipsis, font=font) > max_width:
        text = text[:-1]
    return text.rstrip() + ellipsis


def render(submission: Submission, business_name: str, dest: Path) -> Path:
    """Compose the preview and write it to `dest`."""
    language = submission.language.value
    labels = CATEGORY_LABELS.get(language, CATEGORY_LABELS["en"])
    scores = _combined_scores(submission)
    card = submission.card

    canvas = Image.new("RGB", (OG_WIDTH, OG_HEIGHT), _BACKGROUND)
    draw = ImageDraw.Draw(canvas)

    photo_right = _draw_card_photo(
        canvas,
        dest.parent / "front_base.png",
        (_MARGIN, _MARGIN, _MARGIN + 300, OG_HEIGHT - _MARGIN - 70),
    )

    text_left = (photo_right + 40) if photo_right > _MARGIN else _MARGIN
    text_width = OG_WIDTH - _MARGIN - text_left

    name = (card.card_name if card else None) or "Card"
    draw.text(
        (text_left, _MARGIN),
        _truncate(draw, name, _font(58, bold=True), text_width),
        font=_font(58, bold=True),
        fill=_FOREGROUND,
    )

    subtitle_parts = [p for p in ((card.set_name if card else None),
                                  (f"#{card.card_number}" if card and card.card_number else None))
                     if p]
    if subtitle_parts:
        draw.text(
            (text_left, _MARGIN + 74),
            _truncate(draw, " · ".join(subtitle_parts), _font(28), text_width),
            font=_font(28),
            fill=_MUTED,
        )

    # The four scores. An unmeasurable category draws an em dash and never a
    # zero -- "we could not tell" and "this is terrible" are different answers,
    # and this is the surface most likely to be shown to somebody deciding
    # whether to buy the card.
    tile_top = _MARGIN + 140
    tile_w = text_width // 4
    for i, category in enumerate(_CATEGORY_ORDER):
        x = text_left + i * tile_w
        draw.text((x, tile_top), labels[category], font=_font(22), fill=_MUTED)
        score = scores.get(category)
        if score is None:
            # Words rather than a dash. "Not measured" reads as a decision
            # somebody made; a lone mark reads as data that went missing, and
            # this is the surface most likely to be shown to a buyer. A dash
            # also has to be an em dash to look deliberate, and that is one of
            # the glyphs a fallback font turns into a box.
            draw.text(
                (x, tile_top + 46),
                _UNMEASURED.get(language, _UNMEASURED["en"]),
                font=_font(26, bold=True),
                fill=_MUTED,
            )
        else:
            draw.text(
                (x, tile_top + 34),
                f"{score:.1f}",
                font=_font(60, bold=True),
                fill=_tier_color(score),
            )

    # Non-optional whenever the flag is set. An adjusted report has to say so
    # wherever it is read, and a preview pasted into a chat is exactly where
    # omitting it would pay.
    if submission.client_adjusted:
        badge_y = tile_top + 122
        badge = _ADJUSTED_LABELS.get(language, _ADJUSTED_LABELS["en"])
        draw.text((text_left, badge_y), badge, font=_font(24, bold=True), fill=_ADJUSTED)

    # The framing, on the image itself. For a lot of viewers the unfurl is the
    # entire product, so "this is not a grade" cannot live only on the page.
    footer_y = OG_HEIGHT - _MARGIN - 34
    draw.line([(_MARGIN, footer_y - 22), (OG_WIDTH - _MARGIN, footer_y - 22)], fill=_RULE, width=2)

    # The brand is laid out first and the disclaimer is fitted to what is left.
    # `business_name` is operator-editable and unbounded, and the Spanish
    # disclaimer is the longer of the two strings -- so with both at full length
    # they meet in the middle. The disclaimer is the half that gives, but it is
    # never dropped: it is the only piece of framing on a preview somebody may
    # see entirely out of context.
    brand_font = _font(24, bold=True)
    brand = _truncate(draw, business_name, brand_font, 300)
    brand_width = draw.textlength(brand, font=brand_font)
    draw.text((OG_WIDTH - _MARGIN - brand_width, footer_y), brand, font=brand_font, fill=_FOREGROUND)

    disclaimer_font = _font(24)
    available = OG_WIDTH - (2 * _MARGIN) - brand_width - 24
    draw.text(
        (_MARGIN, footer_y),
        _truncate(draw, _DISCLAIMER.get(language, _DISCLAIMER["en"]), disclaimer_font, int(available)),
        font=disclaimer_font,
        fill=_MUTED,
    )

    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest, "JPEG", quality=_JPEG_QUALITY, optimize=True)
    return dest


_ADJUSTED_LABELS = {
    "en": "Adjusted by the card's owner",
    "es": "Ajustado por el propietario de la carta",
}

_UNMEASURED = {
    "en": "Not measured",
    "es": "Sin medir",
}

# Separated with a middot rather than an em dash: the dash is not in every
# fallback font and silently becomes a box, and this line is the one piece of
# framing that has to survive on a preview somebody sees out of context.
_DISCLAIMER = {
    "en": "Independent pre-grade estimate · not a grade",
    "es": "Estimación independiente de pre-calificación · no es una calificación",
}


def ensure(submission: Submission, business_name: str, reports_dir: Path) -> Path:
    """The current preview, rendered if this exact state has not been drawn yet.

    Named for what it guarantees rather than what it does: after this returns,
    the file on disk is the picture of *current* state. Siblings from earlier
    fingerprints are reaped, so a submission carries one preview rather than one
    per revision -- and nothing ever serves an old one, because its name is no
    longer the name anything asks for.
    """
    directory = Path(reports_dir) / submission.submission_code
    current = directory / f"og_{fingerprint(submission)}.jpg"
    if current.is_file():
        return current

    render(submission, business_name, current)
    for stale in directory.glob("og_*.jpg"):
        if stale != current:
            stale.unlink(missing_ok=True)
    return current
