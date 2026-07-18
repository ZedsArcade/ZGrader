from sqlalchemy.orm import Session

from zgrader.models.settings import Settings
from zgrader.seed.card_dimensions_seed import seed_card_dimensions
from zgrader.seed.tolerance_rules_seed import seed_tolerance_rules


def seed_settings_singleton(db: Session) -> None:
    if db.query(Settings).first() is None:
        db.add(Settings())
        db.commit()


def seed_all(db: Session) -> None:
    seed_card_dimensions(db)
    seed_tolerance_rules(db)
    seed_settings_singleton(db)
