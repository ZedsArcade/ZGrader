from fastapi.testclient import TestClient

from zgrader.api.main import app

client = TestClient(app)


def test_register_then_login_then_me(db_session):
    resp = client.post("/auth/register", json={"email": "alice@example.com", "password": "hunter2pass"})
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


def test_duplicate_email_rejected(db_session):
    client.post("/auth/register", json={"email": "bob@example.com", "password": "hunter2pass"})
    resp = client.post("/auth/register", json={"email": "bob@example.com", "password": "different1"})
    assert resp.status_code == 409


def test_wrong_password_rejected(db_session):
    client.post("/auth/register", json={"email": "carol@example.com", "password": "hunter2pass"})
    resp = client.post("/auth/login", data={"username": "carol@example.com", "password": "wrongpass"})
    assert resp.status_code == 401


def test_me_requires_token(db_session):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_email_verification_flow(db_session):
    resp = client.post("/auth/register", json={"email": "dave@example.com", "password": "hunter2pass"})
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
