"""Seed data for CardDimensionReference.

Standard trading-card size across most modern TCGs is 63x88mm (2.5x3.5in).
Yu-Gi-Oh! is a notable exception at 59x86mm. Final Fantasy TCG and Union
Arena dimensions were not confirmed against a physical card during research
-- seeded as unverified best-guess standard size; verify with calipers
before trusting centering results for those two games.
"""

from sqlalchemy.orm import Session

from zgrader.models.card_dimensions import CardDimensionReference

CARD_DIMENSIONS_SEED: list[dict] = [
    {"game": "Pokemon", "width_mm": 63.0, "height_mm": 88.0, "verified": True},
    {"game": "Magic: The Gathering", "width_mm": 63.0, "height_mm": 88.0, "verified": True},
    {
        "game": "Yu-Gi-Oh!",
        "width_mm": 59.0,
        "height_mm": 86.0,
        "verified": True,
        "notes": "Smaller than standard -- do not fall back to the 63x88 default.",
    },
    {"game": "Riftbound", "width_mm": 63.0, "height_mm": 88.0, "verified": True},
    {"game": "One Piece Card Game", "width_mm": 63.5, "height_mm": 88.9, "verified": True},
    {"game": "Dragon Ball Super Card Game", "width_mm": 63.0, "height_mm": 88.0, "verified": True},
    {"game": "Disney Lorcana", "width_mm": 63.5, "height_mm": 88.9, "verified": True},
    {
        "game": "Final Fantasy TCG",
        "width_mm": 63.0,
        "height_mm": 88.0,
        "verified": False,
        "notes": "Assumed standard size -- not confirmed against a physical card. Verify with calipers.",
    },
    {
        "game": "Union Arena",
        "width_mm": 63.0,
        "height_mm": 88.0,
        "verified": False,
        "notes": "Assumed standard size -- not confirmed against a physical card. Verify with calipers.",
    },
]


def seed_card_dimensions(db: Session) -> None:
    existing = {row.game for row in db.query(CardDimensionReference).all()}
    for entry in CARD_DIMENSIONS_SEED:
        if entry["game"] in existing:
            continue
        db.add(CardDimensionReference(**entry))
    db.commit()
