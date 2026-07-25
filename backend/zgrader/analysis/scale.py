"""Pixel-to-millimetre scale for the analysis pipeline.

Derived from the card's *physical* size, not the image file's DPI metadata.
The deskewed card image produced by preprocessing maps exactly onto the card
(edge to edge), so the true scale is simply pixels-per-card divided by
millimetres-per-card.

This replaces an earlier `dpi / 25.4` conversion, which silently produced
nonsense on photos: a phone image's EXIF DPI has no relationship to how many
pixels cover the card, so measurements came out wildly wrong (a crease on an
88mm-tall card was reported as 244mm). ScanImage.dpi is still recorded as
scan metadata -- it just no longer drives measurement.

Dimension lookups go through CardDimensionReference, per that model's own
contract ("never hardcode a game's size in Python").
"""

from sqlalchemy.orm import Session

from zgrader.models.card_dimensions import CardDimensionReference

# Standard modern TCG card size, used only when a submission's game has no
# CardDimensionReference row (see zgrader/seed/card_dimensions_seed.py --
# Yu-Gi-Oh! is the notable exception and is seeded explicitly).
DEFAULT_CARD_WIDTH_MM = 63.0
DEFAULT_CARD_HEIGHT_MM = 88.0


def dimensions_for(db: Session, game: str | None) -> tuple[float, float]:
    """(width_mm, height_mm) for a game, falling back to the standard size."""
    if game:
        row = db.query(CardDimensionReference).filter(CardDimensionReference.game == game).first()
        if row is not None:
            return float(row.width_mm), float(row.height_mm)
    return DEFAULT_CARD_WIDTH_MM, DEFAULT_CARD_HEIGHT_MM


def px_per_mm(card_shape: tuple[int, int], width_mm: float, height_mm: float) -> float:
    """Pixels per millimetre for a deskewed card image.

    card_shape is (height, width), matching np.ndarray.shape[:2]. Both axes
    should agree on a correctly deskewed card; averaging them keeps the
    result stable when the crop is slightly loose on one side.
    """
    h, w = card_shape
    if height_mm <= 0 or width_mm <= 0:
        raise ValueError("Card dimensions must be positive")
    return ((h / height_mm) + (w / width_mm)) / 2.0
