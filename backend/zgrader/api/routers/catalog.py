"""Public, unauthenticated read-only reference data the frontend needs (e.g.
the new-submission form's game dropdown, and the business name/contact shown
in the nav and landing page) -- kept as endpoints rather than duplicated
client-side so they can't drift from the DB (seed data or operator-edited
Settings).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from zgrader import images
from zgrader.config import config
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


@router.get("/service-images", response_model=dict[str, int])
def list_service_images() -> dict[str, int]:
    """Which service tiers have a banner, and a version for each.

    The version is the file's mtime, which the frontend appends as a query
    string. Without it a replaced image would sit behind whatever the
    browser already cached and the operator would think the upload failed.
    """
    versions: dict[str, int] = {}
    for slug in images.SERVICE_TIER_SLUGS:
        path = images.service_image_path(config.public_media_dir, slug)
        if path.is_file():
            versions[slug] = int(path.stat().st_mtime)
    return versions


@router.get("/service-images/{slug}")
def get_service_image(slug: str) -> FileResponse:
    """Public: these are marketing images on a page anonymous visitors see.

    Every other image route in this API needs a Bearer token because it
    serves a customer's card; this one deliberately does not.
    """
    if slug not in images.SERVICE_TIER_SLUGS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown service")
    path = images.service_image_path(config.public_media_dir, slug)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No image set for this service")
    # Cached hard, because the URL carries an mtime version: a new upload is
    # a new URL, so a stale cache entry can never be served.
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
