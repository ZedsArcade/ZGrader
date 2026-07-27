from fastapi.testclient import TestClient

from zgrader.api.main import app

client = TestClient(app)


def test_register_then_login_then_me(db_session):
    resp = client.post("/auth/register", json={"email": "alice@example.com", "password": "hunter2pass", "accept_terms": True})
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert body["is_verified"] is False
    assert body["role"] == "client"

    resp = client.post(
        "/auth/login", data={"username": "alice@example.com", "password": "hunter2pass"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    assert token

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@example.com"


def test_duplicate_email_does_not_reveal_itself(db_session):
    """Registering an address that already exists returns the same 201 as a
    fresh signup. A distinct 409 would let anyone test which email addresses
    have accounts here -- the inbox owner is told by email instead."""
    from zgrader.db import SessionLocal
    from zgrader.models import User

    first = client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "hunter2pass", "accept_terms": True},
    )
    assert first.status_code == 201

    second = client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "different1", "accept_terms": True},
    )
    assert second.status_code == 201

    # The body must be synthesised, not the real account: echoing the stored
    # row back would hand the caller that user's id and verification state,
    # which leaks more than the 409 this replaced.
    assert second.json()["id"] != first.json()["id"]
    assert set(second.json()) == set(first.json())

    with SessionLocal() as session:
        assert session.query(User).filter(User.email == "bob@example.com").count() == 1
        # The second attempt must not have changed the existing password.
        user = session.query(User).filter(User.email == "bob@example.com").one()
    assert client.post(
        "/auth/login", data={"username": "bob@example.com", "password": "hunter2pass"}
    ).status_code == 200
    assert client.post(
        "/auth/login", data={"username": "bob@example.com", "password": "different1"}
    ).status_code == 401
    assert user.terms_accepted_at is not None


def test_wrong_password_rejected(db_session):
    client.post("/auth/register", json={"email": "carol@example.com", "password": "hunter2pass", "accept_terms": True})
    resp = client.post("/auth/login", data={"username": "carol@example.com", "password": "wrongpass"})
    assert resp.status_code == 401


def test_me_requires_token(db_session):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_email_verification_flow(db_session):
    resp = client.post("/auth/register", json={"email": "dave@example.com", "password": "hunter2pass", "accept_terms": True})
    user_id = resp.json()["id"]

    from zgrader.db import SessionLocal
    from zgrader.models import User

    db = SessionLocal()
    token = db.query(User).filter(User.id == user_id).first().verification_token
    db.close()
    assert token is not None

    resp = client.post(f"/auth/verify/{token}")
    assert resp.status_code == 200
    assert resp.json()["is_verified"] is True

    resp = client.post("/auth/verify/not-a-real-token")
    assert resp.status_code == 404
