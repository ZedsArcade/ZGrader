"""The controls added before this service takes personal data and payments.

Each test names the attack it forecloses, because a security control whose
purpose isn't written down tends to get "simplified" away later.
"""

import datetime
import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from tests.conftest import register_and_verify
from zgrader.api import ratelimit
from zgrader.api.main import app
from zgrader.auth.security import create_access_token, utcnow
from zgrader.config import INSECURE_SECRET_KEY, ZGraderConfig
from zgrader.db import SessionLocal
from zgrader.models import AuditLog, Submission, User

client = TestClient(app)

REAL_SECRET = "x" * 40
REAL_DB_URL = "postgresql+psycopg://real:s3cret@db:5432/zg"


def _user(email: str) -> User:
    with SessionLocal() as session:
        return session.query(User).filter(User.email == email).one()


# --- Configuration --------------------------------------------------------


def test_production_refuses_the_shipped_default_secret():
    """The default key is printed in config.py, so anyone reading the repo
    could forge an operator token. Booting on it must be impossible."""
    with pytest.raises(Exception) as exc:
        ZGraderConfig(env="production", secret_key=INSECURE_SECRET_KEY, database_url=REAL_DB_URL)
    assert "ZGRADER_SECRET_KEY" in str(exc.value)


def test_production_refuses_a_short_secret_and_default_db_credentials():
    with pytest.raises(Exception) as exc:
        ZGraderConfig(env="production", secret_key="tooshort", database_url=REAL_DB_URL)
    assert "shorter than" in str(exc.value)

    with pytest.raises(Exception) as exc:
        ZGraderConfig(
            env="production",
            secret_key=REAL_SECRET,
            database_url="postgresql+psycopg://zgrader:zgrader@db:5432/zg",
        )
    assert "default zgrader/zgrader" in str(exc.value)


def test_production_starts_with_real_secrets():
    cfg = ZGraderConfig(env="production", secret_key=REAL_SECRET, database_url=REAL_DB_URL)
    assert cfg.env == "production"


def test_development_only_warns():
    """The documented bare-uvicorn workflow and the test suite must keep
    working on defaults."""
    cfg = ZGraderConfig(env="development")
    assert cfg.secret_key == INSECURE_SECRET_KEY


def test_api_docs_are_disabled_in_production():
    """The docs publish every admin route to anyone who can reach the app,
    and Next proxies /api/* straight through to the internet."""
    from fastapi import FastAPI

    def build(env: str) -> FastAPI:
        enabled = env != "production"
        return FastAPI(
            docs_url="/docs" if enabled else None,
            redoc_url="/redoc" if enabled else None,
            openapi_url="/openapi.json" if enabled else None,
        )

    assert build("production").openapi_url is None
    assert build("development").openapi_url == "/openapi.json"
    # And the real app follows config.env, which is development under test.
    assert app.openapi_url == "/openapi.json"


# --- Rate limiting --------------------------------------------------------


def test_login_is_rate_limited(db_session):
    """Without this, an attacker can guess passwords indefinitely."""
    register_and_verify(client, "brute@example.com")
    ratelimit.reset()

    codes = [
        client.post(
            "/auth/login", data={"username": "brute@example.com", "password": "wrong"}
        ).status_code
        for _ in range(7)
    ]
    assert codes[:5] == [401] * 5
    assert codes[5] == 429

    blocked = client.post(
        "/auth/login", data={"username": "brute@example.com", "password": "hunter2pass"}
    )
    assert blocked.status_code == 429
    # A client that knows when to retry doesn't have to poll blindly.
    assert int(blocked.headers["Retry-After"]) > 0


def test_successful_logins_do_not_consume_the_login_allowance(db_session):
    """Otherwise an office or a CGNAT address locks its own users out.

    Only failed attempts count, which costs a password guesser nothing --
    they have no successes to spend.
    """
    register_and_verify(client, "busy@example.com")
    ratelimit.reset()

    for _ in range(10):
        ok = client.post(
            "/auth/login", data={"username": "busy@example.com", "password": "hunter2pass"}
        )
        assert ok.status_code == 200

    # The allowance is untouched, so a genuine typo still gets its attempts.
    assert (
        client.post(
            "/auth/login", data={"username": "busy@example.com", "password": "wrong"}
        ).status_code
        == 401
    )


def test_registration_is_rate_limited(db_session):
    ratelimit.reset()
    codes = [
        client.post(
            "/auth/register",
            json={"email": f"flood{i}@example.com", "password": "hunter2pass", "accept_terms": True},
        ).status_code
        for i in range(6)
    ]
    assert codes.count(429) == 1


def test_client_ip_ignores_spoofable_headers_outside_production(monkeypatch):
    """CF-Connecting-IP is only trustworthy when the origin can't be reached
    directly. In development anyone could set it and get a fresh bucket."""
    from starlette.requests import Request

    def make_request(headers: dict) -> Request:
        raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
        return Request({"type": "http", "headers": raw, "client": ("10.0.0.1", 1234)})

    req = make_request({"CF-Connecting-IP": "1.2.3.4", "X-Forwarded-For": "5.6.7.8"})
    assert ratelimit.client_ip(req) == "10.0.0.1"

    monkeypatch.setattr(ratelimit.config, "env", "production")
    assert ratelimit.client_ip(req) == "1.2.3.4"
    assert ratelimit.client_ip(make_request({"X-Forwarded-For": "5.6.7.8, 9.9.9.9"})) == "5.6.7.8"


# --- Enumeration ----------------------------------------------------------


def test_login_costs_the_same_whether_or_not_the_email_exists(db_session):
    """Short-circuiting on a missing user answers ~1000x faster than a real
    bcrypt check, which reveals which addresses have accounts."""
    register_and_verify(client, "timing@example.com")

    def elapsed(username: str) -> float:
        ratelimit.reset()
        start = time.perf_counter()
        client.post("/auth/login", data={"username": username, "password": "wrongpassword"})
        return time.perf_counter() - start

    known = min(elapsed("timing@example.com") for _ in range(3))
    unknown = min(elapsed("nobody-here@example.com") for _ in range(3))
    # Generous bound: this is about closing a 1000x gap, not a 2x one.
    assert 0.25 < unknown / known < 4.0, f"known={known:.4f}s unknown={unknown:.4f}s"


def test_forgot_password_never_reveals_whether_an_account_exists(db_session):
    register_and_verify(client, "known@example.com")
    ratelimit.reset()
    assert client.post("/auth/forgot-password", json={"email": "known@example.com"}).status_code == 204
    assert client.post("/auth/forgot-password", json={"email": "ghost@example.com"}).status_code == 204


# --- Email verification ---------------------------------------------------


def test_unverified_users_cannot_create_submissions_or_upload(db_session):
    """Verification gates the actions that cost storage and compute, not
    login -- but it does have to gate something."""
    client.post(
        "/auth/register",
        json={"email": "unverified@example.com", "password": "hunter2pass", "accept_terms": True},
    )
    token = client.post(
        "/auth/login", data={"username": "unverified@example.com", "password": "hunter2pass"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Signing in and reading still work.
    assert client.get("/auth/me", headers=headers).status_code == 200
    assert client.get("/submissions", headers=headers).status_code == 200

    resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "X"}, headers=headers
    )
    assert resp.status_code == 403
    assert "confirm your email" in resp.json()["detail"].lower()


def test_verification_link_expires(db_session):
    client.post(
        "/auth/register",
        json={"email": "stale@example.com", "password": "hunter2pass", "accept_terms": True},
    )
    with SessionLocal() as session:
        user = session.query(User).filter(User.email == "stale@example.com").one()
        token = user.verification_token
        user.verification_token_expires_at = utcnow() - datetime.timedelta(minutes=1)
        session.commit()

    assert client.post(f"/auth/verify/{token}").status_code == 410
    assert _user("stale@example.com").is_verified is False


def test_verification_can_be_resent_without_revealing_anything(db_session):
    client.post(
        "/auth/register",
        json={"email": "resend@example.com", "password": "hunter2pass", "accept_terms": True},
    )
    first = _user("resend@example.com").verification_token
    ratelimit.reset()

    assert client.post("/auth/verify/resend", json={"email": "resend@example.com"}).status_code == 204
    assert _user("resend@example.com").verification_token != first
    # Unknown address: same answer.
    assert client.post("/auth/verify/resend", json={"email": "ghost@example.com"}).status_code == 204


# --- Password reset and revocation ---------------------------------------


def test_reset_is_single_use_and_revokes_existing_sessions(db_session):
    """A reset exists to end a compromise. If the attacker's token survived
    it, it wouldn't."""
    old_token = register_and_verify(client, "reset@example.com")
    old_headers = {"Authorization": f"Bearer {old_token}"}
    assert client.get("/auth/me", headers=old_headers).status_code == 200

    ratelimit.reset()
    client.post("/auth/forgot-password", json={"email": "reset@example.com"})
    reset_token = _user("reset@example.com").password_reset_token
    assert reset_token

    assert client.post(
        "/auth/reset-password", json={"token": reset_token, "password": "brandnewpass"}
    ).status_code == 204

    # The session held before the reset is dead.
    assert client.get("/auth/me", headers=old_headers).status_code == 401
    # The token can't be replayed.
    assert client.post(
        "/auth/reset-password", json={"token": reset_token, "password": "another1pass"}
    ).status_code == 400
    # The new password works.
    assert client.post(
        "/auth/login", data={"username": "reset@example.com", "password": "brandnewpass"}
    ).status_code == 200


def test_expired_reset_token_is_refused(db_session):
    register_and_verify(client, "expiredreset@example.com")
    ratelimit.reset()
    client.post("/auth/forgot-password", json={"email": "expiredreset@example.com"})

    with SessionLocal() as session:
        user = session.query(User).filter(User.email == "expiredreset@example.com").one()
        token = user.password_reset_token
        user.password_reset_expires_at = utcnow() - datetime.timedelta(minutes=1)
        session.commit()

    assert client.post(
        "/auth/reset-password", json={"token": token, "password": "brandnewpass"}
    ).status_code == 400


def test_changing_password_requires_the_current_one_and_rotates_sessions(db_session):
    token = register_and_verify(client, "changepw@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    wrong = client.post(
        "/auth/change-password",
        json={"current_password": "notitatall", "new_password": "brandnewpass"},
        headers=headers,
    )
    assert wrong.status_code == 400

    resp = client.post(
        "/auth/change-password",
        json={"current_password": "hunter2pass", "new_password": "brandnewpass"},
        headers=headers,
    )
    assert resp.status_code == 200
    # The old token is retired; the response hands back a working one so the
    # tab the user is in doesn't get signed out.
    assert client.get("/auth/me", headers=headers).status_code == 401
    fresh = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    assert client.get("/auth/me", headers=fresh).status_code == 200


def test_a_token_with_a_stale_version_is_rejected(db_session):
    register_and_verify(client, "staleversion@example.com")
    user = _user("staleversion@example.com")
    forged = create_access_token(str(user.id), user.token_version + 5)
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


# --- Terms, email case, deletion -----------------------------------------


def test_registration_requires_accepting_the_terms(db_session):
    ratelimit.reset()
    resp = client.post(
        "/auth/register", json={"email": "noterms@example.com", "password": "hunter2pass"}
    )
    assert resp.status_code == 422
    resp = client.post(
        "/auth/register",
        json={"email": "noterms@example.com", "password": "hunter2pass", "accept_terms": False},
    )
    assert resp.status_code == 422


def test_terms_acceptance_is_recorded(db_session):
    register_and_verify(client, "terms@example.com")
    user = _user("terms@example.com")
    assert user.terms_accepted_at is not None
    assert user.terms_version
    assert user.marketing_consent is False


def test_email_is_case_insensitive(db_session):
    """Two accounts differing only by case is a support problem now and a
    billing problem once Stripe attaches to one of them."""
    ratelimit.reset()
    client.post(
        "/auth/register",
        json={"email": "MixedCase@Example.com", "password": "hunter2pass", "accept_terms": True},
    )
    assert _user("mixedcase@example.com") is not None
    assert client.post(
        "/auth/login", data={"username": "mixedcase@example.com", "password": "hunter2pass"}
    ).status_code == 200
    assert client.post(
        "/auth/login", data={"username": "MIXEDCASE@EXAMPLE.COM", "password": "hunter2pass"}
    ).status_code == 200


def test_account_deletion_removes_the_person_but_keeps_an_anonymised_trail(db_session):
    token = register_and_verify(client, "leaving@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    code = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Goodbye"}, headers=headers
    ).json()["submission_code"]

    user_id = _user("leaving@example.com").id
    assert client.delete("/auth/me", headers=headers).status_code == 204

    with SessionLocal() as session:
        assert session.query(User).filter(User.id == user_id).first() is None
        assert (
            session.query(Submission).filter(Submission.submission_code == code).first() is None
        )
        # The trail survives; the identity in it does not.
        deleted = session.query(AuditLog).filter(AuditLog.action == "account_deleted").all()
        assert deleted
        assert all(entry.user_id is None for entry in deleted)
        assert not session.query(AuditLog).filter(AuditLog.user_id == user_id).all()

    assert client.get("/auth/me", headers=headers).status_code == 401


def test_operators_cannot_delete_themselves(db_session):
    """Losing the last operator would make the admin panel unreachable."""
    from zgrader.auth.security import hash_password
    from zgrader.models import UserRole

    db_session.add(
        User(
            email="lastop@example.com",
            hashed_password=hash_password("hunter2pass"),
            role=UserRole.operator,
            is_verified=True,
        )
    )
    db_session.commit()
    ratelimit.reset()
    token = client.post(
        "/auth/login", data={"username": "lastop@example.com", "password": "hunter2pass"}
    ).json()["access_token"]
    assert client.delete("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 403


# --- Uploads --------------------------------------------------------------


def test_uploaded_scans_are_stripped_of_exif(db_session):
    """A handheld photo can carry the GPS coordinates of someone's home."""
    from zgrader.models import ScanImage

    token = register_and_verify(client, "exif@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    code = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Located"}, headers=headers
    ).json()["submission_code"]

    buf = io.BytesIO()
    image = Image.new("RGB", (600, 900), "white")
    exif = image.getexif()
    exif[0x010F] = "PhoneMaker"  # Make
    exif[0x0110] = "SecretModel"  # Model
    image.save(buf, format="JPEG", exif=exif)
    original = buf.getvalue()
    assert b"SecretModel" in original

    resp = client.post(
        f"/submissions/{code}/scans",
        data={"side": "front"},
        files={"file": ("phone.jpg", original, "image/jpeg")},
        headers=headers,
    )
    assert resp.status_code == 200

    with SessionLocal() as session:
        scan = (
            session.query(ScanImage)
            .join(Submission)
            .filter(Submission.submission_code == code)
            .one()
        )
        stored = open(scan.file_path, "rb").read()

    assert b"SecretModel" not in stored
    assert b"PhoneMaker" not in stored
    with Image.open(io.BytesIO(stored)) as reopened:
        assert reopened.size == (600, 900)  # pixels preserved
        assert not dict(reopened.getexif())
