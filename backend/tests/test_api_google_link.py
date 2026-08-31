"""Connecting a Google account to an account that already exists.

Sign-in refuses to attach Google to an address that already has a password
account, deliberately -- linking on a matching address is an account-takeover
route (see test_api_google_auth.py). This is the safe way to do the same
thing: the person proves both sides, a password session to mint the state and
Google to complete it, so nothing is inferred from the address matching.

Which is why these tests care most about the two things that could undo that
proof: a state from the sign-in flow being accepted here, and an unlink that
leaves somebody locked out or leaves a stolen session alive.
"""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import register_and_verify
from zgrader.api.main import app
from zgrader.auth import google as google_oauth
from zgrader.config import config
from zgrader.db import SessionLocal
from zgrader.models import GOOGLE, AuditLog, Identity, User

client = TestClient(app)

SUBJECT = "google-subject-link-1"
OTHER_SUBJECT = "google-subject-link-2"


@pytest.fixture()
def google_enabled(monkeypatch):
    monkeypatch.setattr(config, "google_client_id", "test-client-id")
    monkeypatch.setattr(config, "google_client_secret", "test-client-secret")
    yield


@pytest.fixture()
def google_returns(monkeypatch):
    def _set(subject: str, email: str):
        monkeypatch.setattr(
            google_oauth, "exchange_code_for_profile", lambda code: (subject, email)
        )

    return _set


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _callback(state: str, code: str = "auth-code"):
    return client.get(
        "/auth/google/callback",
        params={"code": code, "state": state},
        follow_redirects=False,
    )


def _link_state_for(email: str) -> str:
    with SessionLocal() as session:
        user = session.query(User).filter(User.email == email).one()
        return google_oauth.issue_link_state(str(user.id))


def test_link_start_hands_back_a_url_for_the_signed_in_account(db_session, google_enabled):
    token = register_and_verify(client, "linker@example.com")

    resp = client.post("/auth/google/link/start", headers=_auth(token))

    assert resp.status_code == 200, resp.text
    url = resp.json()["url"]
    assert url.startswith(google_oauth.AUTHORIZE_URL)
    # The state names the account, so the callback needs nothing from the
    # navigation that a navigation could not carry.
    state = url.split("state=")[1].split("&")[0]
    with SessionLocal() as session:
        user = session.query(User).filter(User.email == "linker@example.com").one()
        assert google_oauth.verify_link_state(state) == str(user.id)


def test_link_start_needs_authentication(db_session, google_enabled):
    assert client.post("/auth/google/link/start").status_code == 401


def test_link_start_is_404_when_google_is_unconfigured(db_session):
    token = register_and_verify(client, "nolink@example.com")
    assert client.post("/auth/google/link/start", headers=_auth(token)).status_code == 404


def test_linking_attaches_the_identity_to_the_existing_account(
    db_session, google_enabled, google_returns
):
    register_and_verify(client, "connect@example.com")
    google_returns(SUBJECT, "personal@gmail.com")

    resp = _callback(_link_state_for("connect@example.com"))

    assert resp.status_code == 307
    assert "google_linked=1" in resp.headers["location"]
    with SessionLocal() as session:
        user = session.query(User).filter(User.email == "connect@example.com").one()
        identity = session.query(Identity).filter(Identity.provider == GOOGLE).one()
        assert identity.user_id == user.id
        assert identity.provider_user_id == SUBJECT
        # The password account keeps its password -- linking adds a way in, it
        # does not replace one.
        assert user.has_usable_password


def test_a_different_google_address_is_allowed_and_does_not_rename_the_account(
    db_session, google_enabled, google_returns
):
    """Work and personal Google accounts are ordinary.

    Both sides are already proven -- a password session minted the state and
    Google completed it -- so a mismatch carries no information. `users.email`
    is the address we send mail to and is left alone.
    """
    register_and_verify(client, "work@example.com")
    google_returns(SUBJECT, "entirely-different@gmail.com")

    _callback(_link_state_for("work@example.com"))

    with SessionLocal() as session:
        assert session.query(User).filter(User.email == "work@example.com").one_or_none()
        assert (
            session.query(User).filter(User.email == "entirely-different@gmail.com").one_or_none()
            is None
        ), "linking created a second account instead of attaching to the first"


def test_linking_twice_is_idempotent(db_session, google_enabled, google_returns):
    register_and_verify(client, "twice@example.com")
    google_returns(SUBJECT, "twice@example.com")

    first = _callback(_link_state_for("twice@example.com"))
    second = _callback(_link_state_for("twice@example.com"))

    assert "google_linked=1" in first.headers["location"]
    assert "google_linked=1" in second.headers["location"], "a repeat read as a failure"
    with SessionLocal() as session:
        assert session.query(Identity).count() == 1


def test_a_google_account_already_attached_elsewhere_is_refused(
    db_session, google_enabled, google_returns
):
    """The mirror of sign-in's takeover guard, from the other direction."""
    register_and_verify(client, "owner@example.com")
    register_and_verify(client, "thief@example.com")
    google_returns(SUBJECT, "shared@gmail.com")

    _callback(_link_state_for("owner@example.com"))
    resp = _callback(_link_state_for("thief@example.com"))

    assert "google_error=" in resp.headers["location"]
    assert "different account" in resp.headers["location"].replace("+", " ").replace("%20", " ")
    with SessionLocal() as session:
        owner = session.query(User).filter(User.email == "owner@example.com").one()
        identity = session.query(Identity).filter(Identity.provider == GOOGLE).one()
        assert identity.user_id == owner.id


def test_a_sign_in_state_cannot_drive_the_link_branch(db_session, google_enabled, google_returns):
    """The separation that makes the whole flow safe.

    Both states are signed with the same secret and arrive at the same URI, so
    the declared type is the only thing telling them apart. A sign-in state
    reaching the link branch would attach a Google account on the strength of
    a state anyone can mint by visiting /auth/google/start.
    """
    register_and_verify(client, "victim@example.com")
    google_returns(SUBJECT, "victim@example.com")

    # A sign-in state routes to sign-in, which refuses an existing address.
    resp = _callback(google_oauth.issue_state("/dashboard"))

    assert "oauth_error=" in resp.headers["location"]
    assert "already exists" in resp.headers["location"].replace("+", " ").replace("%20", " ")
    with SessionLocal() as session:
        assert session.query(Identity).count() == 0, "a sign-in state attached an identity"


def test_a_link_state_cannot_be_used_as_a_sign_in(db_session, google_enabled, google_returns):
    """And the reverse: a link state must not mint a session on its own."""
    register_and_verify(client, "linkonly@example.com")
    state = _link_state_for("linkonly@example.com")
    google_returns(SUBJECT, "linkonly@example.com")

    resp = _callback(state)

    # It routed to the link branch, so it produced a redirect to the account
    # page and never to the token-bearing /auth/google fragment.
    assert "#token=" not in resp.headers["location"]
    assert "/account" in resp.headers["location"]


def test_verify_link_state_refuses_a_sign_in_state(db_session):
    with pytest.raises(google_oauth.GoogleAuthError):
        google_oauth.verify_link_state(google_oauth.issue_state("/dashboard"))


def test_verify_state_refuses_a_link_state(db_session):
    with pytest.raises(google_oauth.GoogleAuthError):
        google_oauth.verify_state(google_oauth.issue_link_state("some-user-id"))


def test_state_type_refuses_anything_we_did_not_sign(db_session):
    assert google_oauth.state_type("not-a-jwt") is None


def test_unlink_removes_the_identity_and_retires_old_sessions(
    db_session, google_enabled, google_returns
):
    """Unlinking removes a credential, so it ends existing sessions.

    If somebody had attached their own Google account to this one, unlinking
    is the remediation -- and a session they already hold must not outlive it.
    """
    token = register_and_verify(client, "unlink@example.com")
    google_returns(SUBJECT, "unlink@example.com")
    _callback(_link_state_for("unlink@example.com"))

    resp = client.delete("/auth/google/link", headers=_auth(token))

    assert resp.status_code == 200, resp.text
    new_token = resp.json()["access_token"]
    with SessionLocal() as session:
        assert session.query(Identity).count() == 0

    # The old token is dead, the returned one works.
    assert client.get("/auth/me", headers=_auth(token)).status_code == 401
    assert client.get("/auth/me", headers=_auth(new_token)).status_code == 200


def test_unlink_is_refused_when_it_would_lock_the_account_out(
    db_session, google_enabled, google_returns
):
    """A Google-only account removing Google has no way back in."""
    google_returns(OTHER_SUBJECT, "googleonly@example.com")
    resp = _callback(google_oauth.issue_state("/dashboard"))
    token = resp.headers["location"].split("#token=")[1].split("&")[0]

    with SessionLocal() as session:
        user = session.query(User).filter(User.email == "googleonly@example.com").one()
        assert not user.has_usable_password

    resp = client.delete("/auth/google/link", headers=_auth(token))

    assert resp.status_code == 409
    assert "password" in resp.json()["detail"].lower()
    with SessionLocal() as session:
        assert session.query(Identity).count() == 1, "the last way in was removed"


def test_unlink_is_404_when_nothing_is_connected(db_session):
    token = register_and_verify(client, "nothing@example.com")
    assert client.delete("/auth/google/link", headers=_auth(token)).status_code == 404


def test_the_account_payload_reports_the_connection(db_session, google_enabled, google_returns):
    """What the account page renders its Google section from."""
    token = register_and_verify(client, "payload@example.com")

    before = client.get("/auth/me", headers=_auth(token)).json()
    assert before["google_connected"] is False
    assert before["has_usable_password"] is True

    google_returns(SUBJECT, "payload@example.com")
    _callback(_link_state_for("payload@example.com"))

    after = client.get("/auth/me", headers=_auth(token)).json()
    assert after["google_connected"] is True


def test_linking_and_unlinking_are_audited_without_an_address(
    db_session, google_enabled, google_returns
):
    """delete_account scrubs the keys `email` and `target_email` by name, so a
    new entry carrying an address in its body would slip past an erasure."""
    token = register_and_verify(client, "audited-link@example.com")
    google_returns(SUBJECT, "audited-link@example.com")
    _callback(_link_state_for("audited-link@example.com"))
    client.delete("/auth/google/link", headers=_auth(token))

    with SessionLocal() as session:
        actions = {
            row.action: row.detail
            for row in session.query(AuditLog).filter(
                AuditLog.action.in_(["google_linked", "google_unlinked"])
            )
        }
        assert set(actions) == {"google_linked", "google_unlinked"}
        for action, detail in actions.items():
            assert "audited-link@example.com" not in str(detail), (
                f"{action} carries an address that erasure would not find"
            )
