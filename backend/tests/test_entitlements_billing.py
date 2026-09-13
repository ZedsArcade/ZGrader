"""What a subscription status grants, and what a plan change does to quota.

The grace-period tests pin the anchor, not just the length: when a renewal
fails, Stripe has already moved the subscription into the new period, so an
end-anchored grace would hand out a month -- or a year -- of unpaid access.
"""

import datetime

from zgrader import entitlements
from zgrader.models import Subscription, User, UserRole

NOW = datetime.datetime.now(datetime.timezone.utc)
DAY = datetime.timedelta(days=1)


def _user(db, **kw) -> User:
    user = User(email=kw.pop("email", "ent@example.com"), hashed_password="x", role=UserRole.client, is_verified=True, **kw)
    db.add(user)
    db.flush()
    return user


def _sub(db, user, status, *, start=NOW - DAY, end=NOW + 29 * DAY, plan="monthly", sid="sub_1"):
    row = Subscription(
        user_id=user.id, stripe_subscription_id=sid, plan=plan, status=status,
        current_period_start=start, current_period_end=end,
    )
    db.add(row)
    db.flush()
    return row


def test_active_and_trialing_are_entitled(db_session):
    user = _user(db_session)
    _sub(db_session, user, "trialing")
    assert entitlements.active_plan(db_session, user) == "monthly"


def test_past_due_is_entitled_inside_the_grace(db_session):
    user = _user(db_session)
    _sub(db_session, user, "past_due", start=NOW - 10 * DAY)
    assert entitlements.active_plan(db_session, user) == "monthly"


def test_past_due_grace_counts_from_the_failed_renewal_not_the_period_end(db_session):
    # 30 days since the renewal failed; the new period still has a day to run.
    # End-anchored, this would still be entitled for 22 more days.
    user = _user(db_session)
    _sub(db_session, user, "past_due", start=NOW - 30 * DAY, end=NOW + DAY)
    assert entitlements.active_plan(db_session, user) == "free"


def test_unpaid_and_canceled_are_not_entitled(db_session):
    user = _user(db_session)
    _sub(db_session, user, "unpaid", sid="sub_u")
    _sub(db_session, user, "canceled", sid="sub_c")
    assert entitlements.active_plan(db_session, user) == "free"


def test_subscribing_starts_a_fresh_window(db_session):
    user = _user(db_session, quota_used=3, quota_period_started_at=NOW - DAY)
    _sub(db_session, user, "active")
    quota = entitlements.get_quota(db_session, user)
    assert (quota.plan, quota.used) == ("monthly", 0)
    assert user.quota_period_started_at is None
    assert user.quota_plan == "monthly"


def test_a_grace_running_out_resets_the_window_with_no_write_in_between(db_session):
    """Nothing writes when a grace period expires -- the plan changes because
    time passed. Only a reset derived on read can catch that."""
    user = _user(db_session, quota_used=40, quota_period_started_at=NOW - 5 * DAY, quota_plan="monthly")
    _sub(db_session, user, "past_due", start=NOW - 22 * DAY)
    quota = entitlements.get_quota(db_session, user)
    assert (quota.plan, quota.used, quota.can_submit) == ("free", 0, True)
    assert user.quota_plan == "free"


def test_an_unchanged_plan_keeps_its_window(db_session):
    started = NOW - DAY
    user = _user(db_session, quota_used=2, quota_period_started_at=started)
    quota = entitlements.get_quota(db_session, user)
    assert quota.used == 2
    assert user.quota_period_started_at == started
