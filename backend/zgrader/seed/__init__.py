import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from zgrader.auth.security import hash_password
from zgrader.config import config
from zgrader.models.settings import Settings
from zgrader.models.user import User, UserRole
from zgrader.seed.card_dimensions_seed import seed_card_dimensions
from zgrader.seed.plan_entitlements_seed import seed_plan_entitlements
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
    account can be upgraded). No-op when the env vars aren't both set.

    The password of an account that already exists is left alone unless
    ZGRADER_ADMIN_RESET_PASSWORD is set -- see below.
    """
    if not (config.admin_email and config.admin_password):
        return

    # Normalised the same way the auth router does (see _find_by_email in
    # api/routers/auth.py). Addresses are stored lowercased and there's a
    # unique index on lower(email), so a capitalised ZGRADER_ADMIN_EMAIL used
    # to miss the existing row, fall through to the insert below, and die on
    # that index -- silently, because startup swallows seeding errors. The
    # result was a deployment with no operator and nothing obvious in the log.
    email = config.admin_email.strip().lower()

    existing = db.query(User).filter(func.lower(User.email) == email).first()
    if existing is None:
        db.add(
            User(
                email=email,
                hashed_password=hash_password(config.admin_password),
                role=UserRole.operator,
                is_verified=True,
            )
        )
        db.commit()
        logger.info("Seeded operator account for %s", email)
        return

    changed = False
    if existing.role != UserRole.operator:
        existing.role = UserRole.operator
        existing.is_verified = True
        changed = True
        logger.info("Promoted %s to operator", email)

    if config.admin_reset_password:
        # Deliberately opt-in. Applying the env password on every boot would
        # silently undo a password changed in the app, which is a horrible
        # thing to debug; requiring a flag makes the reset an act rather than
        # a side effect. The version bump retires any token already issued,
        # matching what a password change does everywhere else.
        existing.hashed_password = hash_password(config.admin_password)
        existing.token_version += 1
        changed = True
        logger.warning(
            "ZGRADER_ADMIN_RESET_PASSWORD is set: reset the password for %s and signed out "
            "its existing sessions. Unset it and redeploy -- while it stays set, anyone who "
            "can read the environment can take this account.",
            email,
        )

    if changed:
        db.commit()
    else:
        # Without this, "the bootstrap did nothing" and "the bootstrap never
        # ran" look identical in the log, which is most of what made the
        # original failure hard to diagnose.
        logger.info(
            "Operator account %s already exists; left unchanged "
            "(set ZGRADER_ADMIN_RESET_PASSWORD=true to reset its password)",
            email,
        )


def seed_all(db: Session) -> None:
    seed_card_dimensions(db)
    seed_tolerance_rules(db)
    seed_plan_entitlements(db)
    seed_settings_singleton(db)
    seed_admin_user(db)
