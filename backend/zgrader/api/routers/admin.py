from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from zgrader.api.deps import require_operator
from zgrader.db import get_db
from zgrader.models import AuditLog, Report, ReportStatus, Settings, Submission, User
from zgrader.models.settings import get_or_create_settings
from zgrader.schemas.admin import AuditLogOut, SettingsOut, SettingsUpdate, StatsOut

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
