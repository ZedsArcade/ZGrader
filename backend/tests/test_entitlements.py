"""Quota arithmetic.

Only the parts that need no database live here; the plan lookup and the
create-submission enforcement are exercised through the API tests.
"""

import datetime

import pytest

from zgrader.entitlements import Quota, _roll_period_forward


class _FakeUser:
    """Just the two quota fields -- enough for the rollover, and it keeps
    these tests off the ORM and therefore off Postgres."""

    def __init__(self, started_at=None, used=0):
        self.quota_period_started_at = started_at
        self.quota_used = used


WEEK = datetime.timedelta(days=7)


def _utc(*args) -> datetime.datetime:
    return datetime.datetime(*args, tzinfo=datetime.timezone.utc)


def test_remaining_counts_down_and_floors_at_zero():
    q = Quota(plan="free", limit=3, used=1, period_days=7, resets_at=None)
    assert q.remaining == 2 and q.can_submit

    spent = Quota(plan="free", limit=3, used=3, period_days=7, resets_at=None)
    assert spent.remaining == 0 and not spent.can_submit

    # Defensive: a limit lowered by an operator below what someone has already
    # used must read as 0 left, never a negative allowance.
    over = Quota(plan="free", limit=3, used=5, period_days=7, resets_at=None)
    assert over.remaining == 0 and not over.can_submit


def test_unlimited_plan_never_blocks():
    q = Quota(plan="tier1", limit=None, used=999, period_days=7, resets_at=None)
    assert q.unlimited
    assert q.remaining is None
    assert q.can_submit


def test_no_window_yet_is_left_alone():
    """Before a first submission there is nothing to roll -- the window starts
    when a credit is actually spent, not when the account is created."""
    user = _FakeUser(started_at=None, used=0)
    _roll_period_forward(user, WEEK, _utc(2026, 8, 2))
    assert user.quota_period_started_at is None
    assert user.quota_used == 0


def test_within_the_window_usage_is_preserved():
    user = _FakeUser(started_at=_utc(2026, 8, 1), used=2)
    _roll_period_forward(user, WEEK, _utc(2026, 8, 5))
    assert user.quota_period_started_at == _utc(2026, 8, 1)
    assert user.quota_used == 2


def test_the_boundary_instant_starts_the_next_window():
    """anchor + period belongs to the new window, not the old one -- otherwise
    the advertised reset time would still refuse a submission."""
    user = _FakeUser(started_at=_utc(2026, 8, 1), used=3)
    _roll_period_forward(user, WEEK, _utc(2026, 8, 8))
    assert user.quota_period_started_at == _utc(2026, 8, 8)
    assert user.quota_used == 0


def test_a_long_absence_advances_in_whole_periods():
    """The anchor must land on the period grid, not on 'now'.

    Resetting to now would drag the reset time later after every visit, so a
    user who checks in on a Friday would find their allowance permanently
    resetting on Fridays. Advancing whole periods keeps the cadence stable.
    """
    user = _FakeUser(started_at=_utc(2026, 8, 1), used=3)
    # ~3.5 weeks later, deliberately not a period boundary.
    _roll_period_forward(user, WEEK, _utc(2026, 8, 25, 13, 30))
    assert user.quota_period_started_at == _utc(2026, 8, 22)
    assert user.quota_used == 0


@pytest.mark.parametrize("period_days", [1, 7, 30])
def test_reset_always_lands_within_one_period_of_now(period_days):
    period = datetime.timedelta(days=period_days)
    now = _utc(2026, 12, 25, 9, 15)
    user = _FakeUser(started_at=_utc(2026, 1, 1), used=1)
    _roll_period_forward(user, period, now)
    anchor = user.quota_period_started_at
    assert anchor <= now < anchor + period


def test_naive_anchor_is_treated_as_utc():
    """A naive timestamp round-tripped from a non-Postgres backend must not
    raise on comparison against an aware `now`."""
    user = _FakeUser(started_at=datetime.datetime(2026, 8, 1), used=3)
    _roll_period_forward(user, WEEK, _utc(2026, 8, 9))
    assert user.quota_used == 0
