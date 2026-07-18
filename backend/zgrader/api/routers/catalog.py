"""Public, unauthenticated read-only reference data the frontend needs (e.g.
the new-submission form's game dropdown) -- kept as an endpoint rather than
duplicated client-side so it can't drift from zgrader/seed/card_dimensions_seed.py.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from zgrader.db import get_db
from zgrader.models import CardDimensionReference
from zgrader.schemas.catalog import GameOut

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/games", response_model=list[GameOut])
def list_games(db: Session = Depends(get_db)) -> list[CardDimensionReference]:
    return db.query(CardDimensionReference).order_by(CardDimensionReference.game).all()
