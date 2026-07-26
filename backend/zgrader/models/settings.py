from sqlalchemy import Boolean, Integer, String, Text
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
    business_name: Mapped[str] = mapped_column(String(200), default="Card Care Center", nullable=False)
    business_logo_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    business_contact: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # The disclaimer printed on generated reports. The public site carries an
    # equivalent statement in the frontend i18n dictionaries (t.terms.*) rather
    # than reading this one, because operator-typed text can only exist in a
    # single language and the site is bilingual. Keep the two in step.
    disclaimer_text: Mapped[str] = mapped_column(
        Text,
        default=(
            "This report is an independent pre-grade estimate produced by Card Care Center. "
            "It is not affiliated with, endorsed by, or a guarantee of the outcome from "
            "PSA, Beckett Grading Services (BGS), CGC, TAG, or any other third-party "
            "grading company."
        ),
        nullable=False,
    )

    # Public contact details, shown on the site's contact page and footer.
    # contact_response_days and contact_in_person are structured rather than
    # free text on purpose: they feed translated sentences, so the operator can
    # edit them without the copy dropping out of Spanish.
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    contact_location: Mapped[str | None] = mapped_column(
        String(200), default="Gibraltar", nullable=True
    )
    contact_response_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contact_in_person: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Social profiles. Each renders only when set, so an operator who doesn't
    # use a network simply leaves it blank rather than shipping a dead link.
    # WhatsApp is a phone number, not a URL -- the frontend builds the wa.me
    # link -- which keeps an operator-supplied scheme out of an href entirely.
    social_instagram: Mapped[str | None] = mapped_column(String(500), nullable=True)
    social_facebook: Mapped[str | None] = mapped_column(String(500), nullable=True)
    social_x: Mapped[str | None] = mapped_column(String(500), nullable=True)
    social_whatsapp: Mapped[str | None] = mapped_column(String(32), nullable=True)


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
