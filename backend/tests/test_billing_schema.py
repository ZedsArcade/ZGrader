"""The shapes billing depends on, in the create_all schema the suite uses.

The partial unique index is declared on the model (not in raw SQL) precisely
so it exists here; tests/test_migrations.py checks the migrated schema has it
too."""

import pytest
from sqlalchemy.exc import IntegrityError

from zgrader.models import Subscription, User, UserRole


def _user(db, email="schema@example.com") -> User:
    user = User(email=email, hashed_password="x", role=UserRole.client, is_verified=True)
    db.add(user)
    db.flush()
    return user


def test_two_live_subscriptions_for_one_user_are_refused(db_session):
    user = _user(db_session)
    db_session.add(Subscription(user_id=user.id, stripe_subscription_id="sub_a", plan="monthly", status="active"))
    db_session.add(Subscription(user_id=user.id, stripe_subscription_id="sub_b", plan="annual", status="past_due"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_an_ended_subscription_does_not_block_a_new_one(db_session):
    user = _user(db_session)
    db_session.add(Subscription(user_id=user.id, stripe_subscription_id="sub_a", plan="monthly", status="canceled"))
    db_session.add(Subscription(user_id=user.id, stripe_subscription_id="sub_b", plan="monthly", status="active"))
    db_session.flush()


def test_status_accepts_stripe_statuses_the_old_enum_lacked(db_session):
    user = _user(db_session)
    row = Subscription(user_id=user.id, stripe_subscription_id="sub_u", plan="monthly", status="unpaid")
    db_session.add(row)
    db_session.flush()
    db_session.refresh(row)
    assert row.status == "unpaid"
