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
from zgrader.models import CardDimensionReference, PhysicalPriceTier, PlanEntitlement
from zgrader.models.grading_comparison import GradingCompany, GradingCompanyToleranceRule
from zgrader.models.settings import get_or_create_settings
from zgrader.schemas.catalog import BrandingOut, GameOut, PricingOut

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/games", response_model=list[GameOut])
def list_games(db: Session = Depends(get_db)) -> list[CardDimensionReference]:
    return db.query(CardDimensionReference).order_by(CardDimensionReference.game).all()


def _active_grading_companies(db: Session) -> list[str]:
    """Companies with at least one active tolerance rule, in enum order.

    Enum order rather than query order because this drives a sentence on the
    landing page -- an unordered SQL result would reshuffle the names between
    requests.
    """
    active = {
        row.company
        for row in db.query(GradingCompanyToleranceRule)
        .filter(GradingCompanyToleranceRule.active.is_(True))
        .all()
    }
    return [company.value for company in GradingCompany if company in active]


@router.get("/pricing", response_model=PricingOut)
def get_pricing(db: Session = Depends(get_db)) -> PricingOut:
    """Every published price, from the rows that define them.

    The pricing page renders entirely from this, so an operator changing a
    figure in the admin panel changes the shopfront with no deploy -- the same
    argument `plan_entitlements` already makes for quota caps, and the reason
    the site copy carries no numbers at all.

    Plans are ordered by price so the page can lay them out cheapest first
    without deciding an order of its own; unpriced plans (the free tier) sort
    ahead of the rest.
    """
    settings = get_or_create_settings(db)
    plans = (
        db.query(PlanEntitlement)
        .order_by(PlanEntitlement.price_pence.nulls_first(), PlanEntitlement.plan)
        .all()
    )
    tiers = db.query(PhysicalPriceTier).order_by(PhysicalPriceTier.min_qty).all()
    return PricingOut(
        plans=plans,
        physical_tiers=tiers,
        collection_triage_guide_pence=settings.collection_triage_guide_pence,
        founder_price_pence=settings.founder_price_pence,
        founder_seats=settings.founder_seats,
        subscriber_discount_pct=settings.subscriber_discount_pct,
    )


@router.get("/branding", response_model=BrandingOut)
def get_branding(db: Session = Depends(get_db)) -> BrandingOut:
    # Built field by field rather than returned as the ORM row: the company
    # list comes from a different table, so from_attributes can't supply it.
    settings = get_or_create_settings(db)
    return BrandingOut(
        **{
            field: getattr(settings, field)
            for field in BrandingOut.model_fields
            if field != "grading_companies"
        },
        grading_companies=_active_grading_companies(db),
    )


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


@router.get("/brand-logos", response_model=dict[str, int])
def list_brand_logos() -> dict[str, int]:
    """Which brands have a header logo, and a version for each.

    Same mtime-as-version trick as the service banners: the frontend appends
    it so a replaced logo is a new URL rather than something the browser keeps
    serving from cache while the operator wonders why the upload did nothing.
    """
    versions: dict[str, int] = {}
    for slug in images.BRAND_LOGO_SLUGS:
        path = images.brand_logo_path(config.public_media_dir, slug)
        if path.is_file():
            versions[slug] = int(path.stat().st_mtime)
    return versions


@router.get("/brand-logos/{slug}")
def get_brand_logo(slug: str) -> FileResponse:
    """Public: the logo sits in the header of every page, signed in or not."""
    if slug not in images.BRAND_LOGO_SLUGS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown brand")
    path = images.brand_logo_path(config.public_media_dir, slug)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No logo set for this brand")
    return FileResponse(
        path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
