import logging

from sqlalchemy.orm import Session

from zgrader.auth.security import hash_password
from zgrader.config import config
from zgrader.models.settings import Settings
from zgrader.models.user import User, UserRole
from zgrader.seed.card_dimensions_seed import seed_card_dimensions
from zgrader.seed.tolerance_rules_seed import seed_tolerance_rules

logger = logging.getLogger(__name__)


def seed_settings_singleton(db: Session) -> None:
    if db.query(Settings).first() is None:
        db.add(Settings())
        db.commit()


def seed_admin_user(db: Session) -> None:
    """Bootstrap a first operator account from ZGRADER_ADMIN_EMAIL/PASSWORD.

    Idempotent: creates the operator if the email is new, or promotes an
    existing client of that email to operator (so an already-registered
    account can be upgraded). Never downgrades or overwrites an existing
    operator's password. No-op when the env vars aren't both set.
    """
    if not (config.admin_email and config.admin_password):
        return

    existing = db.query(User).filter(User.email == config.admin_email).first()
    if existing is None:
        db.add(
            User(
                email=config.admin_email,
                hashed_password=hash_password(config.admin_password),
                role=UserRole.operator,
                is_verified=True,
            )
        )
        db.commit()
        logger.info("Seeded operator account for %s", config.admin_email)
    elif existing.role != UserRole.operator:
        existing.role = UserRole.operator
        existing.is_verified = True
        db.commit()
        logger.info("Promoted %s to operator", config.admin_email)


def seed_all(db: Session) -> None:
    seed_card_dimensions(db)
    seed_tolerance_rules(db)
    seed_settings_singleton(db)
    seed_admin_user(db)
