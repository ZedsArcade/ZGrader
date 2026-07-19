from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Settings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Singleton table (always exactly one row) for operator-editable,
    runtime-tunable business settings -- as opposed to zgrader.config,
    which holds env-only infrastructure config.
    """

    __tablename__ = "settings"

    auto_publish_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    business_name: Mapped[str] = mapped_column(String(200), default="ZGrader", nullable=False)
    business_logo_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    business_contact: Mapped[str | None] = mapped_column(String(500), nullable=True)
    disclaimer_text: Mapped[str] = mapped_column(
        Text,
        default=(
            "This report is an independent pre-grade estimate produced by ZGrader. "
            "It is not affiliated with, endorsed by, or a guarantee of the outcome from "
            "PSA, Beckett Grading Services (BGS), CGC, TAG, or any other third-party "
            "grading company."
        ),
        nullable=False,
    )


def get_or_create_settings(db: Session) -> "Settings":
    """The Settings singleton is normally seeded by zgrader.seed.seed_all()
    at startup; this fallback avoids a 500 if that hasn't run yet."""
    settings = db.query(Settings).first()
    if settings is None:
        settings = Settings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings
