"""Logging out ends the session on the server, not just in the browser.

`logout()` in the frontend cleared localStorage and told the server nothing, so
the token it discarded stayed valid for the rest of its 24-hour life. Anyone
holding a copy -- a shared machine, a synced browser profile, an extension --
kept the session the user believed they had just ended. `token_version` existed
and was bumped only by a password change, reset, or Google unlink, so the sole
way to kill a live session was to change your password.

Revocation is global by design: `token_version` is one integer on the user, so
logging out anywhere ends every session everywhere. That is the trade-off taken
deliberately -- it makes "sign out on the device I lost" work from the device
still in your hand, at the cost of signing out the laptop too.
"""

from fastapi.testclient import TestClient

from tests.conftest import register_and_verify
from zgrader.api.main import app
from zgrader.db import SessionLocal
from zgrader.models import User

client = TestClient(app)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_logout_ends_the_callers_own_session(db_session):
    token = register_and_verify(client, "bye@example.com")
    assert client.get("/auth/me", headers=_auth(token)).status_code == 200

    assert client.post("/auth/logout", headers=_auth(token)).status_code == 204

    assert client.get("/auth/me", headers=_auth(token)).status_code == 401, (
        "the token survived the logout that discarded it"
    )


def test_logout_ends_a_session_the_caller_never_held(db_session):
    """Proves revocation rather than local clearing.

    A second token is minted directly, standing in for a session on another
    device, and logout is called with the *first*. The second is then rejected
    -- so the refusal comes from server state and not from anything the client
    discarded. An implementation that returned 204 and did nothing would pass
    the caller's-own-token test above, because that token is the one the client
    throws away regardless.

    The two tokens can be byte-identical, and that is not a flaw in the test.
    A token is {sub, iat, exp, ver} with second granularity and no random
    component, so two sessions started in the same second *are* the same
    string: this design has no per-session identity, which is precisely why
    revocation is all-or-nothing. That trade-off was taken deliberately -- see
    the endpoint's docstring.
    """
    from zgrader.auth.security import create_access_token

    token = register_and_verify(client, "twodevices@example.com")
    with SessionLocal() as session:
        user = session.query(User).filter(User.email == "twodevices@example.com").one()
        other_device = create_access_token(str(user.id), user.token_version)

    assert client.get("/auth/me", headers=_auth(other_device)).status_code == 200

    client.post("/auth/logout", headers=_auth(token))

    assert client.get("/auth/me", headers=_auth(other_device)).status_code == 401, (
        "a session the caller never held outlived the sign-out"
    )


def test_logout_bumps_the_version_rather_than_deleting_anything(db_session):
    """Revocation must not be destructive: the account is untouched."""
    token = register_and_verify(client, "intact@example.com", "hunter2pass")
    with SessionLocal() as session:
        before = session.query(User).filter(User.email == "intact@example.com").one().token_version

    client.post("/auth/logout", headers=_auth(token))

    with SessionLocal() as session:
        user = session.query(User).filter(User.email == "intact@example.com").one()
        assert user.token_version == before + 1
        assert user.is_verified, "logout disturbed the account"
        assert user.hashed_password, "logout cleared the password"


def test_logging_back_in_works_afterwards(db_session):
    """The obvious way to get revocation wrong is to make it permanent."""
    password = "hunter2pass"
    token = register_and_verify(client, "again@example.com", password)
    client.post("/auth/logout", headers=_auth(token))

    resp = client.post(
        "/auth/login", data={"username": "again@example.com", "password": password}
    )

    assert resp.status_code == 200
    assert client.get("/auth/me", headers=_auth(resp.json()["access_token"])).status_code == 200


def test_logout_requires_a_valid_session(db_session):
    assert client.post("/auth/logout").status_code == 401
    assert client.post("/auth/logout", headers=_auth("not-a-token")).status_code == 401


def test_logging_out_twice_is_not_an_error_for_the_first_call(db_session):
    """The second call uses a token the first one retired, so it is a 401 --
    not a 500, and not a silent success that suggests something happened."""
    token = register_and_verify(client, "twice-out@example.com")

    assert client.post("/auth/logout", headers=_auth(token)).status_code == 204
    assert client.post("/auth/logout", headers=_auth(token)).status_code == 401
