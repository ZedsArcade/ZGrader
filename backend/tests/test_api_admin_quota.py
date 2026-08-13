"""Operator support tools for a customer's quota.

Giving credits back is a privileged action that changes what someone is
entitled to, so the audit trail is part of the behaviour under test, not an
afterthought.
"""

from fastapi.testclient import TestClient

from zgrader.api.main import app
from zgrader.auth.security import hash_password
from zgrader.models import AuditLog, PlanEntitlement, User, UserRole
from zgrader.models.subscription import Subscription, SubscriptionStatus

from tests.conftest import register_and_verify

client = TestClient(app)


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _operator(db_session, email: str = "op-quota@example.com") -> str:
    db_session.add(
        User(
            email=email,
            hashed_password=hash_password("hunter2pass"),
            role=UserRole.operator,
            is_verified=True,
        )
    )
    db_session.commit()
    return client.post(
        "/auth/login", data={"username": email, "password": "hunter2pass"}
    ).json()["access_token"]


def _set_free_limit(db_session, limit, period_days: int = 7) -> None:
    row = db_session.query(PlanEntitlement).filter(PlanEntitlement.plan == "free").one()
    row.submission_limit = limit
    row.period_days = period_days
    db_session.commit()


def _create(token: str, name: str = "Pikachu"):
    return client.post(
        "/submissions", json={"game": "Pokemon", "card_name": name}, headers=_headers(token)
    )


def test_operator_can_look_up_a_customer_by_email(db_session):
    _set_free_limit(db_session, 3)
    op = _operator(db_session)
    customer = register_and_verify(client, "findme@example.com")
    assert _create(customer).status_code == 201

    resp = client.get("/admin/users/quota", params={"email": "findme"}, headers=_headers(op))
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["email"] == "findme@example.com"
    assert rows[0]["remaining"] == 2


def test_lookup_requires_a_search_term(db_session):
    """A support tool for helping one person, not a way to page through the
    whole customer base."""
    op = _operator(db_session)
    assert client.get("/admin/users/quota", headers=_headers(op)).status_code == 422


def test_a_client_cannot_reach_the_operator_tools(db_session):
    _set_free_limit(db_session, 3)
    token = register_and_verify(client, "notoperator@example.com")
    assert (
        client.get("/admin/users/quota", params={"email": "a"}, headers=_headers(token)).status_code
        == 403
    )


def test_operator_restores_credits_after_something_went_wrong(db_session):
    """The point of the whole feature: a customer wasted a check on a problem
    that wasn't theirs, and gets it back."""
    _set_free_limit(db_session, 2)
    op = _operator(db_session)
    customer = register_and_verify(client, "wasted@example.com")

    assert _create(customer, "one").status_code == 201
    assert _create(customer, "two").status_code == 201
    assert _create(customer, "three").status_code == 402

    user = db_session.query(User).filter(User.email == "wasted@example.com").one()
    resp = client.patch(
        f"/admin/users/{user.id}/quota", json={"remaining": 2}, headers=_headers(op)
    )
    assert resp.status_code == 200
    assert resp.json()["remaining"] == 2

    # And they can actually submit again.
    assert _create(customer, "four").status_code == 201


def test_adjustment_is_audited(db_session):
    _set_free_limit(db_session, 3)
    op = _operator(db_session)
    register_and_verify(client, "audited@example.com")
    user = db_session.query(User).filter(User.email == "audited@example.com").one()

    client.patch(f"/admin/users/{user.id}/quota", json={"remaining": 1}, headers=_headers(op))

    entry = (
        db_session.query(AuditLog).filter(AuditLog.action == "user_quota_adjusted").one()
    )
    assert entry.detail["target_email"] == "audited@example.com"
    assert entry.detail["remaining_before"] == 3
    assert entry.detail["remaining_after"] == 1
    # The actor is the operator, not the customer -- otherwise the trail
    # would read as though the customer topped themselves up.
    operator = db_session.query(User).filter(User.role == UserRole.operator).one()
    assert entry.user_id == operator.id


def test_resetting_the_period_returns_them_to_a_clean_slate(db_session):
    _set_free_limit(db_session, 2)
    op = _operator(db_session)
    customer = register_and_verify(client, "resetme@example.com")
    assert _create(customer).status_code == 201

    user = db_session.query(User).filter(User.email == "resetme@example.com").one()
    resp = client.patch(
        f"/admin/users/{user.id}/quota", json={"reset_period": True}, headers=_headers(op)
    )

    body = resp.json()
    assert body["used"] == 0
    assert body["remaining"] == 2
    # Back to the pre-first-submission state: nothing counting down until
    # they next submit.
    assert body["resets_at"] is None


def test_topping_up_opens_a_window_so_the_countdown_is_not_lost(db_session):
    """If credits are spent there must be a window for them to return in --
    otherwise the UI shows a partial allowance with no reset time."""
    _set_free_limit(db_session, 5)
    op = _operator(db_session)
    register_and_verify(client, "partial@example.com")
    user = db_session.query(User).filter(User.email == "partial@example.com").one()

    body = client.patch(
        f"/admin/users/{user.id}/quota", json={"remaining": 2}, headers=_headers(op)
    ).json()

    assert body["used"] == 3
    assert body["remaining"] == 2
    assert body["resets_at"] is not None


def test_topping_up_an_unlimited_plan_is_refused_with_an_explanation(db_session):
    op = _operator(db_session)
    register_and_verify(client, "unlimited-topup@example.com")
    user = db_session.query(User).filter(User.email == "unlimited-topup@example.com").one()
    # The unlimited plan this test needs, created here rather than borrowed
    # from the seed. What is seeded is a commercial decision that moves with
    # pricing -- it stopped shipping an unlimited tier and took these tests
    # with it. The behaviour under test is "a null limit means unlimited",
    # so the test states that condition itself.
    db_session.add(PlanEntitlement(plan="tier1", submission_limit=None, period_days=7))
    db_session.add(Subscription(user_id=user.id, plan="tier1", status=SubscriptionStatus.active))
    db_session.commit()

    resp = client.patch(
        f"/admin/users/{user.id}/quota", json={"remaining": 3}, headers=_headers(op)
    )
    assert resp.status_code == 400
    assert "no submission limit" in resp.json()["detail"]


def test_unknown_user_is_404(db_session):
    op = _operator(db_session)
    resp = client.patch(
        "/admin/users/00000000-0000-0000-0000-000000000000/quota",
        json={"remaining": 1},
        headers=_headers(op),
    )
    assert resp.status_code == 404
