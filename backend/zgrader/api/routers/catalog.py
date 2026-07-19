"""Public, unauthenticated read-only reference data the frontend needs (e.g.
the new-submission form's game dropdown, and the business name/contact shown
in the nav and landing page) -- kept as endpoints rather than duplicated
client-side so they can't drift from the DB (seed data or operator-edited
Settings).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from zgrader.db import get_db
from zgrader.models import CardDimensionReference, Settings
from zgrader.models.settings import get_or_create_settings
from zgrader.schemas.catalog import BrandingOut, GameOut

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/games", response_model=list[GameOut])
def list_games(db: Session = Depends(get_db)) -> list[CardDimensionReference]:
    return db.query(CardDimensionReference).order_by(CardDimensionReference.game).all()


@router.get("/branding", response_model=BrandingOut)
def get_branding(db: Session = Depends(get_db)) -> Settings:
    return get_or_create_settings(db)
