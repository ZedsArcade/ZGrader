import datetime
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from zgrader import entitlements, images
from zgrader.api.deps import require_operator
from zgrader.api.ratelimit import rate_limit
from zgrader.config import config
from zgrader.db import get_db
from zgrader.email.notifications import send_test_email
from zgrader.models import (
    AuditLog,
    ContactMessage,
    PhysicalPriceTier,
    PlanEntitlement,
    Report,
    ReportStatus,
    Settings,
    Submission,
    User,
)
from zgrader.models.grading_comparison import GradingCompany, GradingCompanyToleranceRule
from zgrader.models.settings import get_or_create_settings
from zgrader.schemas.admin import (
    AuditLogOut,
    ContactMessageOut,
    ContactMessageUpdate,
    GradingCompanyOut,
    GradingCompanyUpdate,
    PhysicalPriceTierOut,
    PhysicalPriceTierUpdate,
    PlanEntitlementOut,
    PlanEntitlementUpdate,
    SettingsOut,
    SettingsUpdate,
    StatsOut,
    TestEmailRequest,
    TestEmailResponse,
    UserQuotaOut,
    UserQuotaUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/settings", response_model=SettingsOut)
def get_settings(
    _operator: User = Depends(require_operator), db: Session = Depends(get_db)
) -> Settings:
    return get_or_create_settings(db)


@router.patch("/settings", response_model=SettingsOut)
def update_settings(
    payload: SettingsUpdate, _operator: User = Depends(require_operator), db: Session = Depends(get_db)
) -> Settings:
    settings = get_or_create_settings(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings


@router.get("/stats", response_model=StatsOut)
def get_stats(_operator: User = Depends(require_operator), db: Session = Depends(get_db)) -> StatsOut:
    total = db.query(Submission).count()
    status_counts = dict(
        db.query(Submission.status, func.count(Submission.id)).group_by(Submission.status).all()
    )
    published_reports = db.query(Report).filter(Report.status == ReportStatus.published).count()
    return StatsOut(
        total_submissions=total,
        by_status={status.value: count for status, count in status_counts.items()},
        published_reports=published_reports,
    )


@router.get("/audit-log", response_model=list[AuditLogOut])
def list_audit_log(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
) -> list[AuditLogOut]:
    entries = (
        db.query(AuditLog)
        .options(joinedload(AuditLog.submission), joinedload(AuditLog.user))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [
        AuditLogOut(
            id=entry.id,
            created_at=entry.created_at,
            action=entry.action,
            detail=entry.detail,
            submission_code=entry.submission.submission_code if entry.submission else None,
            user_email=entry.user.email if entry.user else None,
        )
        for entry in entries
    ]


def _service_image_path(slug: str):
    """Resolve a tier slug to its file, 404ing on anything unrecognised.

    The slug is matched against a fixed tuple rather than a pattern, so the
    path below is always built from a constant -- there is no way for a
    request to steer it anywhere else on disk.
    """
    if slug not in images.SERVICE_TIER_SLUGS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown service")
    return images.service_image_path(config.public_media_dir, slug)


@router.put("/service-images/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def upload_service_image(
    slug: str,
    file: UploadFile = File(...),
    _operator: User = Depends(require_operator),
) -> None:
    """Set the banner shown for a service tier on the public /services page.

    Idempotent by slug: uploading again replaces the existing image, which is
    why this is a PUT. The stored file is re-encoded rather than saved as
    received (see images.store_service_image).
    """
    path = _service_image_path(slug)
    # One byte past the cap, so the limit doesn't depend on Content-Length.
    content = await file.read(images.MAX_UPLOAD_BYTES + 1)
    try:
        images.store_service_image(content, path)
    except images.ImageTooLarge:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image is too large"
        ) from None
    except images.UnsupportedImage:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Unsupported image format -- use JPEG, PNG, or TIFF"
        ) from None


@router.delete("/service-images/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service_image(slug: str, _operator: User = Depends(require_operator)) -> None:
    """Remove a tier's banner. The card then renders without one, as it did
    before any image was set."""
    _service_image_path(slug).unlink(missing_ok=True)


def _brand_logo_path(slug: str):
    """Resolve a brand slug to its logo file, 404ing on anything else.

    Matched against a fixed tuple, same as _service_image_path, so the path is
    always built from a constant and a request can't steer it elsewhere.
    """
    if slug not in images.BRAND_LOGO_SLUGS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown brand")
    return images.brand_logo_path(config.public_media_dir, slug)


@router.put("/brand-logos/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def upload_brand_logo(
    slug: str,
    file: UploadFile = File(...),
    _operator: User = Depends(require_operator),
) -> None:
    """Set the logo shown in the header for one of the two brands.

    Idempotent by slug, hence PUT. Stored as PNG rather than JPEG so a
    transparent logo stays transparent -- see images.store_brand_logo.
    """
    path = _brand_logo_path(slug)
    content = await file.read(images.MAX_UPLOAD_BYTES + 1)
    try:
        images.store_brand_logo(content, path)
    except images.ImageTooLarge:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image is too large"
        ) from None
    except images.UnsupportedImage:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Unsupported image format -- use JPEG, PNG, or TIFF"
        ) from None


@router.delete("/brand-logos/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brand_logo(slug: str, _operator: User = Depends(require_operator)) -> None:
    """Remove a brand's logo. The header then shows just the section switch,
    which is how it looks before any logo is set."""
    _brand_logo_path(slug).unlink(missing_ok=True)


def _quota_out(db: Session, user: User) -> UserQuotaOut:
    quota = entitlements.get_quota(db, user)
    return UserQuotaOut(
        user_id=user.id,
        email=user.email,
        plan=quota.plan,
        unlimited=quota.unlimited,
        limit=quota.limit,
        used=quota.used,
        remaining=quota.remaining,
        resets_at=quota.resets_at,
    )


@router.get("/users/quota", response_model=list[UserQuotaOut])
def list_user_quotas(
    email: str = Query(min_length=2, description="Case-insensitive substring of the address"),
    _operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
) -> list[UserQuotaOut]:
    """Look up customers by email to see what they have left.

    Requires a search term rather than listing everyone: this is a support
    tool for helping a specific person, not a way to page through the
    customer base. Addresses are stored lowercased (see _find_by_email in
    the auth router), so the term is lowered to match.
    """
    users = (
        db.query(User)
        .filter(User.email.contains(email.strip().lower()))
        .order_by(User.email)
        .limit(25)
        .all()
    )
    result = [_quota_out(db, user) for user in users]
    # get_quota rolls a lapsed window forward, which mutates the row.
    db.commit()
    return result


@router.patch("/users/{user_id}/quota", response_model=UserQuotaOut)
def update_user_quota(
    user_id: uuid.UUID,
    payload: UserQuotaUpdate,
    _operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
) -> UserQuotaOut:
    """Give a customer credits back after something went wrong for them.

    Audited, because this changes what someone is entitled to. Without a trail
    there would be no way to tell a support gesture from someone quietly
    handing themselves submissions.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    before = entitlements.get_quota(db, user)
    if payload.remaining is not None and before.unlimited:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"'{before.plan}' has no submission limit, so there is nothing to top up. "
            "Change the plan's limit instead if it should be capped.",
        )

    if payload.reset_period:
        # Clearing the anchor rather than setting it to now returns them to
        # the pre-first-submission state: full allowance, and no countdown
        # running until they next submit.
        user.quota_period_started_at = None
        user.quota_used = 0

    if payload.remaining is not None:
        limit = before.limit or 0
        user.quota_used = max(0, limit - payload.remaining)
        if user.quota_used > 0 and user.quota_period_started_at is None:
            # Something has been spent, so there has to be a window for it to
            # be spent in -- otherwise the UI would show a partial allowance
            # with nothing counting down to its return.
            user.quota_period_started_at = datetime.datetime.now(datetime.timezone.utc)

    db.flush()
    after = entitlements.get_quota(db, user)
    db.add(
        AuditLog(
            submission_id=None,
            user_id=_operator.id,
            action="user_quota_adjusted",
            detail={
                "target_user_id": str(user.id),
                "target_email": user.email,
                "plan": after.plan,
                "reset_period": payload.reset_period,
                "remaining_before": before.remaining,
                "remaining_after": after.remaining,
            },
        )
    )
    db.commit()
    db.refresh(user)
    return _quota_out(db, user)


@router.get("/plans", response_model=list[PlanEntitlementOut])
def list_plans(
    _operator: User = Depends(require_operator), db: Session = Depends(get_db)
) -> list[PlanEntitlement]:
    """Every plan's submission cap and cooldown, free tier included."""
    return db.query(PlanEntitlement).order_by(PlanEntitlement.plan).all()


@router.patch("/plans/{plan}", response_model=PlanEntitlementOut)
def update_plan(
    plan: str,
    payload: PlanEntitlementUpdate,
    _operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
) -> PlanEntitlement:
    """Retune a plan's cap or cooldown.

    Takes effect on the next quota read for every user on that plan -- windows
    already open keep their anchor, so raising a limit hands out the extra
    checks immediately rather than making people wait for a reset.

    submission_limit is nullable and null means unlimited, so exclude_unset is
    what distinguishes "make this unlimited" from "leave the limit alone".
    """
    row = db.query(PlanEntitlement).filter(PlanEntitlement.plan == plan).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No entitlement configured for plan '{plan}'")

    updates = payload.model_dump(exclude_unset=True)
    if "submission_limit" in updates:
        row.submission_limit = updates["submission_limit"]
    if updates.get("period_days") is not None:
        row.period_days = updates["period_days"]
    # Nullable like submission_limit, and for the same reason: clearing the
    # price is how a plan stops being offered, so presence in `updates` is what
    # separates "not for sale" from "leave it alone".
    if "price_pence" in updates:
        row.price_pence = updates["price_pence"]
    if "billing_period" in updates:
        row.billing_period = updates["billing_period"]

    db.commit()
    db.refresh(row)
    return row


@router.get("/physical-tiers", response_model=list[PhysicalPriceTierOut])
def list_physical_tiers(
    _operator: User = Depends(require_operator), db: Session = Depends(get_db)
) -> list[PhysicalPriceTier]:
    """The in-hand pre-grading volume table, cheapest band last."""
    return db.query(PhysicalPriceTier).order_by(PhysicalPriceTier.min_qty).all()


@router.patch("/physical-tiers/{min_qty}", response_model=PhysicalPriceTierOut)
def update_physical_tier(
    min_qty: int,
    payload: PhysicalPriceTierUpdate,
    _operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
) -> PhysicalPriceTier:
    """Retune one band of the volume table.

    Keyed by `min_qty` rather than an opaque id: the bands are a short, stable
    list an operator thinks of as "the 10-24 row", and a URL they can reason
    about beats one they have to look up.

    Nothing is enforced by these figures -- physical work is quoted and
    fulfilled by hand -- so this only changes what the pricing page publishes.
    """
    row = db.query(PhysicalPriceTier).filter(PhysicalPriceTier.min_qty == min_qty).first()
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"No volume band starting at {min_qty} cards"
        )

    updates = payload.model_dump(exclude_unset=True)
    if "max_qty" in updates:
        row.max_qty = updates["max_qty"]
    if updates.get("price_pence") is not None:
        row.price_pence = updates["price_pence"]

    if row.max_qty is not None and row.max_qty < row.min_qty:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"A band cannot end ({row.max_qty}) before it starts ({row.min_qty}).",
        )

    db.commit()
    db.refresh(row)
    return row


@router.get("/grading-companies", response_model=list[GradingCompanyOut])
def list_grading_companies(
    _operator: User = Depends(require_operator), db: Session = Depends(get_db)
) -> list[GradingCompanyOut]:
    """Which companies take part in the multi-company comparison.

    Returned in enum order rather than query order so the admin list doesn't
    reshuffle between loads.
    """
    rules = db.query(GradingCompanyToleranceRule).all()
    return [
        GradingCompanyOut(
            company=company.value,
            active=all(r.active for r in company_rules),
            rule_count=len(company_rules),
        )
        for company in GradingCompany
        if (company_rules := [r for r in rules if r.company == company])
    ]


@router.patch("/grading-companies/{company}", response_model=GradingCompanyOut)
def set_grading_company_active(
    company: str,
    payload: GradingCompanyUpdate,
    operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
) -> GradingCompanyOut:
    """Enable or disable a whole company.

    `active` lives on each tolerance rule, so this updates every rule for the
    company at once -- there's no unique key to target a company by.

    Disabling takes effect for future analyses. Comparisons already stored on
    a submission stay as they are until something re-runs the rules engine for
    it, which includes a client dismissing a finding.
    """
    try:
        target = GradingCompany(company)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown grading company") from None

    rules = (
        db.query(GradingCompanyToleranceRule)
        .filter(GradingCompanyToleranceRule.company == target)
        .all()
    )
    if not rules:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No tolerance rules for that company")

    for rule in rules:
        rule.active = payload.active

    # This changes what every future report says, so it's worth a trail --
    # the first audited action in this router.
    db.add(
        AuditLog(
            submission_id=None,
            user_id=operator.id,
            action="grading_company_enabled" if payload.active else "grading_company_disabled",
            detail={"company": target.value, "rules_updated": len(rules)},
        )
    )
    db.commit()
    return GradingCompanyOut(company=target.value, active=payload.active, rule_count=len(rules))


@router.get("/contact-messages", response_model=list[ContactMessageOut])
def list_contact_messages(
    unhandled_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
) -> list[ContactMessage]:
    """The operator's contact-form inbox.

    Not a convenience: while SMTP is unconfigured the stored row is the only
    copy of an enquiry, so without this endpoint the form accepts messages
    nobody can read. Newest first, matching ix_contact_messages_created_at.
    """
    query = db.query(ContactMessage)
    if unhandled_only:
        query = query.filter(ContactMessage.handled.is_(False))
    return (
        query.order_by(ContactMessage.created_at.desc()).limit(limit).offset(offset).all()
    )


@router.patch("/contact-messages/{message_id}", response_model=ContactMessageOut)
def update_contact_message(
    message_id: uuid.UUID,
    payload: ContactMessageUpdate,
    _operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
) -> ContactMessage:
    """Mark an enquiry dealt with. The message itself is not editable."""
    message = db.get(ContactMessage, message_id)
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact message not found.")
    message.handled = payload.handled
    db.commit()
    db.refresh(message)
    return message


@router.post(
    "/test-email",
    response_model=TestEmailResponse,
    dependencies=[Depends(rate_limit("test_email", limit=10, window_seconds=3600))],
)
def send_test_email_endpoint(
    payload: TestEmailRequest,
    _operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
) -> TestEmailResponse:
    """Send a diagnostic email and report what SMTP actually did.

    Rate limited despite being operator-only: it is an authenticated endpoint
    that makes the server send mail to an arbitrary address, and a stolen
    operator token should not turn the relay into an open one.

    Returns 200 with sent=false rather than an error status when delivery
    fails. A failed test is a successful test -- it answered the question --
    and a 500 here would be indistinguishable from the endpoint itself being
    broken, which is the one thing the operator is trying to rule out.
    """
    settings = get_or_create_settings(db)
    sent = send_test_email(payload.to, settings)
    if sent:
        detail = (
            f"Accepted by {config.smtp_host}:{config.smtp_port}. "
            "If it does not arrive, check the spam folder and the sending domain's "
            "SPF/DKIM/DMARC records -- the relay took it, so the rest is deliverability."
        )
    else:
        detail = (
            f"{config.smtp_host}:{config.smtp_port} refused it or was unreachable. "
            "The server log has the SMTP error. Check the host, port and TLS mode "
            "(587 wants STARTTLS, 465 wants implicit TLS)."
        )
    return TestEmailResponse(sent=sent, detail=detail)
