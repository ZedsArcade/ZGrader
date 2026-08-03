"""Google sign-in.

Google itself is stubbed at the one seam that talks to it
(`exchange_code_for_profile`), so these cover our decisions -- who gets an
account, who is refused, what the callback does with the token -- rather than
re-testing Google's OAuth implementation.
"""

import pytest
from fastapi.testclient import TestClient

from zgrader.api.main import app
from zgrader.auth import google as google_oauth
from zgrader.auth.security import hash_password
from zgrader.config import config
from zgrader.models import GOOGLE, AuditLog, Identity, User, UserRole

from tests.conftest import register_and_verify

client = TestClient(app)

SUBJECT = "google-subject-12345"


@pytest.fixture()
def google_enabled(monkeypatch):
    monkeypatch.setattr(config, "google_client_id", "test-client-id")
    monkeypatch.setattr(config, "google_client_secret", "test-client-secret")
    yield


@pytest.fixture()
def google_returns(monkeypatch):
    """Stub the one function that talks to Google."""

    def _set(subject: str, email: str):
        monkeypatch.setattr(
            google_oauth, "exchange_code_for_profile", lambda code: (subject, email)
        )

    return _set


def _callback(state: str | None = None, code: str = "auth-code"):
    return client.get(
        "/auth/google/callback",
        params={"code": code, "state": state or google_oauth.issue_state("/dashboard")},
        follow_redirects=False,
    )


def test_status_reports_disabled_when_unconfigured(db_session):
    assert client.get("/auth/google/status").json() == {"enabled": False}


def test_status_reports_enabled_once_configured(db_session, google_enabled):
    assert client.get("/auth/google/status").json() == {"enabled": True}


def test_start_is_404_when_unconfigured(db_session):
    """An install without an OAuth client shouldn't offer a route that can
    only fail once the user reaches Google."""
    assert client.get("/auth/google/start", follow_redirects=False).status_code == 404


def test_start_redirects_to_google_with_our_state(db_session, google_enabled):
    resp = client.get("/auth/google/start", follow_redirects=False)
    assert resp.status_code == 307
    location = resp.headers["location"]
    assert location.startswith(google_oauth.AUTHORIZE_URL)
    assert "client_id=test-client-id" in location
    assert "state=" in location


def test_first_sign_in_creates_a_verified_account(db_session, google_enabled, google_returns):
    google_returns(SUBJECT, "newperson@example.com")

    resp = _callback()
    assert resp.status_code == 307
    # The token rides in the fragment, never the query string, so it stays out
    # of server logs and the Referer header.
    location = resp.headers["location"]
    assert "#token=" in location
    assert "?token=" not in location

    user = db_session.query(User).filter(User.email == "newperson@example.com").one()
    assert user.role == UserRole.client
    # Google states the address is verified, which is the same proof our own
    # emailed link provides -- so the account isn't stranded behind SMTP.
    assert user.is_verified is True
    assert user.hashed_password is None

    identity = db_session.query(Identity).one()
    assert identity.provider == GOOGLE
    assert identity.provider_user_id == SUBJECT
    assert identity.user_id == user.id


def test_returning_user_is_matched_on_subject_not_email(
    db_session, google_enabled, google_returns
):
    """Someone can change their address at Google without becoming a
    different person, so the stable subject id is what identifies them."""
    google_returns(SUBJECT, "original@example.com")
    _callback()
    user_id = db_session.query(User).one().id

    google_returns(SUBJECT, "changed-at-google@example.com")
    _callback()

    assert db_session.query(User).count() == 1
    assert db_session.query(Identity).count() == 1
    assert db_session.query(User).one().id == user_id


def test_an_existing_password_account_is_refused_not_linked(
    db_session, google_enabled, google_returns
):
    """The account-takeover guard.

    Linking on a matching address means anyone who can obtain a provider
    account bearing someone else's address inherits their account.
    """
    register_and_verify(client, "taken@example.com")
    google_returns(SUBJECT, "taken@example.com")

    resp = _callback()

    assert resp.status_code == 307
    assert "oauth_error=" in resp.headers["location"]
    assert "already exists" in resp.headers["location"].replace("+", " ").replace("%20", " ")
    # No identity was attached to the existing account.
    assert db_session.query(Identity).count() == 0
    assert db_session.query(User).count() == 1


def test_a_forged_state_is_refused(db_session, google_enabled, google_returns):
    """State is the CSRF defence: without it an attacker can feed a victim a
    callback carrying the attacker's own code and silently sign them into the
    attacker's account."""
    google_returns(SUBJECT, "csrf@example.com")

    resp = _callback(state="not-a-state-we-issued")

    assert resp.status_code == 307
    assert "oauth_error=" in resp.headers["location"]
    assert db_session.query(User).count() == 0


def test_cancelling_at_google_returns_without_an_account(db_session, google_enabled):
    resp = client.get(
        "/auth/google/callback", params={"error": "access_denied"}, follow_redirects=False
    )
    assert resp.status_code == 307
    assert "oauth_error=" in resp.headers["location"]
    assert db_session.query(User).count() == 0


def test_google_account_creation_is_audited(db_session, google_enabled, google_returns):
    google_returns(SUBJECT, "audited-google@example.com")
    _callback()

    entry = db_session.query(AuditLog).filter(
        AuditLog.action == "account_created_via_google"
    ).one()
    assert entry.detail["email"] == "audited-google@example.com"


def test_password_login_against_a_google_only_account_is_indistinguishable(
    db_session, google_enabled, google_returns
):
    """It must not reveal that the address exists but has no password --
    that confirms registration to anyone who guesses an address."""
    google_returns(SUBJECT, "googleonly@example.com")
    _callback()

    resp = client.post(
        "/auth/login", data={"username": "googleonly@example.com", "password": "anything123"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect email or password"


def test_change_password_explains_itself_on_a_google_only_account(
    db_session, google_enabled, google_returns
):
    google_returns(SUBJECT, "nopassword@example.com")
    resp = _callback()
    token = resp.headers["location"].split("#token=")[1].split("&")[0]

    changed = client.post(
        "/auth/change-password",
        json={"current_password": "whatever", "new_password": "newpassword123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert changed.status_code == 400
    assert "Google" in changed.json()["detail"]


def test_deleting_a_google_account_removes_its_identity(
    db_session, google_enabled, google_returns
):
    google_returns(SUBJECT, "deleteme-google@example.com")
    resp = _callback()
    token = resp.headers["location"].split("#token=")[1].split("&")[0]

    assert (
        client.delete("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 204
    )
    assert db_session.query(Identity).count() == 0


def test_an_operator_signing_in_with_google_keeps_their_role(
    db_session, google_enabled, google_returns
):
    """A pre-existing Google identity on an operator account must still sign
    in as an operator, not be downgraded to a client."""
    user = User(
        email="op-google@example.com",
        hashed_password=hash_password("hunter2pass"),
        role=UserRole.operator,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(Identity(user_id=user.id, provider=GOOGLE, provider_user_id=SUBJECT))
    db_session.commit()

    google_returns(SUBJECT, "op-google@example.com")
    resp = _callback()

    token = resp.headers["location"].split("#token=")[1].split("&")[0]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["role"] == "operator"
