"""Stripe billing. Every route answers 404 while billing is off, so a
deployment with no Stripe account exposes nothing that half-works."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from zgrader import billing, billing_stripe
from zgrader.api.deps import require_verified_user
from zgrader.api.ratelimit import user_rate_limit
from zgrader.api.routers.auth import CURRENT_TERMS_VERSION
from zgrader.config import config
from zgrader.db import get_db
from zgrader.models import User
from zgrader.schemas.billing import CheckoutIn, CheckoutOut

router = APIRouter(prefix="/billing", tags=["billing"])

# User-keyed: starting a checkout needs a verified account, and the account is
# what should be bounded, not the address it happens to be on.
_checkout_limit = user_rate_limit("billing_checkout", limit=10, window_seconds=3600)


def _require_billing() -> None:
    if not config.billing_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")


@router.post("/checkout", response_model=CheckoutOut, dependencies=[Depends(_checkout_limit)])
def checkout(
    payload: CheckoutIn,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> CheckoutOut:
    _require_billing()
    if payload.terms_version != CURRENT_TERMS_VERSION or not payload.immediate_start_consent:
        # The dialog was stale or the box was unticked; it re-reads and asks again.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Please accept the current terms to continue.")
    try:
        url = billing.create_checkout(db, user, plan_name=payload.plan, terms_version=payload.terms_version)
    except billing.BillingRefused as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return CheckoutOut(url=url)


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """Stripe's event callback. Public path /api/billing/webhook -- listed in
    the maintenance Worker's BYPASS_PREFIXES, which must never lose it.

    Carries no address-keyed rate limit: it is authenticated per request by
    its HMAC signature, and Stripe sends every account's webhooks from one
    shared set of addresses, so any address-keyed limit can be exhausted by
    other Stripe accounts relaying forgeries -- refusing genuine deliveries.
    See UNLIMITED_BY_DESIGN in tests/test_rate_limit_coverage.py.

    Async only so the raw body can be read before anything parses it: the
    signature covers those exact bytes. The database work runs in the
    threadpool because the session is synchronous.
    """
    _require_billing()
    payload = await request.body()
    try:
        event = billing_stripe.construct_event(payload, request.headers.get("stripe-signature", ""))
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid signature")
    try:
        await run_in_threadpool(billing.handle_event, db, event)
    except Exception:
        db.rollback()
        raise
    return {"received": True}
