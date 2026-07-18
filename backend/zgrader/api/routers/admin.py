from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from zgrader.api.deps import require_operator
from zgrader.db import get_db
from zgrader.models import Report, ReportStatus, Settings, Submission, User
from zgrader.schemas.admin import SettingsOut, SettingsUpdate, StatsOut

router = APIRouter(prefix="/admin", tags=["admin"])


def _get_settings(db: Session) -> Settings:
    settings = db.query(Settings).first()
    if settings is None:
        # Defensive fallback -- normally seeded by zgrader.seed.seed_all() at
        # startup, but avoid a 500 if that hasn't run yet.
        settings = Settings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("/settings", response_model=SettingsOut)
def get_settings(
    _operator: User = Depends(require_operator), db: Session = Depends(get_db)
) -> Settings:
    return _get_settings(db)


@router.patch("/settings", response_model=SettingsOut)
def update_settings(
    payload: SettingsUpdate, _operator: User = Depends(require_operator), db: Session = Depends(get_db)
) -> Settings:
    settings = _get_settings(db)
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
