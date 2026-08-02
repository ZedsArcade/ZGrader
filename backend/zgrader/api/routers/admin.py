from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from zgrader import images
from zgrader.api.deps import require_operator
from zgrader.config import config
from zgrader.db import get_db
from zgrader.models import AuditLog, PlanEntitlement, Report, ReportStatus, Settings, Submission, User
from zgrader.models.grading_comparison import GradingCompany, GradingCompanyToleranceRule
from zgrader.models.settings import get_or_create_settings
from zgrader.schemas.admin import (
    AuditLogOut,
    GradingCompanyOut,
    GradingCompanyUpdate,
    PlanEntitlementOut,
    PlanEntitlementUpdate,
    SettingsOut,
    SettingsUpdate,
    StatsOut,
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
