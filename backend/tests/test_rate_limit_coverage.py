"""Every route is rate limited, or is named here as a deliberate exception.

Fails on addition rather than on a list of things somebody already worried
about: add a route with no limiter and this test names it. The audit that
prompted this found thirteen unlimited routes behind a paragraph in AGENTS.md
claiming limiting was already applied to "the authenticated submission
endpoints".
"""

from zgrader.api.main import app

#: Routes that deliberately carry no limiter, with the reason.
UNLIMITED_BY_DESIGN = {
    "/health",  # liveness probe; must answer under load, carries nothing
}


def _walk(routes):
    for route in routes:
        original = getattr(route, "original_router", None)
        if original is not None:
            yield from _walk(original.routes)
        else:
            yield route


#: The exact __name__s of the rate-limit dependency factories' inner
#: closures (see zgrader/api/ratelimit.py). Matched literally rather than
#: via a generic fallback like `name == "dependency"` -- that fallback used
#: to be the only thing actually detecting these routes (both closures were
#: named `dependency`), which meant any *other* FastAPI dependency factory
#: written with that same idiomatic inner name would satisfy this test
#: without ever calling the limiter. Keep these names in sync with
#: ratelimit.py; a rename on either side without the other silently makes a
#: real route look protected when it isn't.
_RATE_LIMIT_DEPENDENCY_NAMES = {
    "_ip_rate_limit_dependency",
    "_user_rate_limit_dependency",
}


def _dependency_names(dependant, acc=None):
    acc = acc if acc is not None else []
    call = getattr(dependant, "call", None)
    if call is not None:
        acc.append(getattr(call, "__name__", repr(call)))
    for sub in getattr(dependant, "dependencies", []):
        _dependency_names(sub, acc)
    return acc


def test_every_route_is_rate_limited_or_explicitly_excepted():
    unlimited = []
    for route in _walk(app.routes):
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        path = route.path
        if path in UNLIMITED_BY_DESIGN:
            continue
        names = _dependency_names(dependant)
        # Primary check is the explicit closure-name set above. The
        # substring fallback stays only for standalone, distinctly-named
        # limiter functions that predate the factories -- e.g. login's
        # `login_rate_limit` -- which are not generic idiomatic names and so
        # don't reintroduce the collision risk a bare `dependency` had.
        if not any(
            name in _RATE_LIMIT_DEPENDENCY_NAMES or "limit" in name.lower() for name in names
        ):
            unlimited.append(f"{sorted(route.methods or [])} {path}")

    assert not unlimited, (
        "these routes have no rate limiter, so a caller can hit them without bound: "
        f"{sorted(unlimited)}. Add one via rate_limit()/user_rate_limit(), or list the "
        "path in UNLIMITED_BY_DESIGN with the reason it needs none."
    )


def test_change_password_throttles_wrong_current_password(db_session):
    """The takeover path the audit found.

    change-password verifies `current_password`, which makes it a password
    oracle for anyone holding a stolen token -- and unlike login it had no
    limiter, so the guesses were free.
    """
    from fastapi.testclient import TestClient
    from zgrader.api.main import app
    from tests.conftest import register_and_verify

    client = TestClient(app)
    token = register_and_verify(client, "throttled@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    body = {"current_password": "wrong-password", "new_password": "brandnewpass"}

    statuses = [
        client.post("/auth/change-password", json=body, headers=headers).status_code
        for _ in range(8)
    ]

    assert 429 in statuses, f"unlimited password guesses via change-password: {statuses}"
    assert statuses.index(429) <= 6, "limiter allowed too many guesses before refusing"


def test_change_password_limit_is_keyed_by_user_not_ip(db_session):
    """change-password's limiter must survive IP rotation, not just exist.

    The other test above proves *a* limiter is attached, but it only ever
    drives requests from one TestClient -- one IP, one user -- so it would
    pass identically against a plain IP-keyed `rate_limit(...)`. That would
    not close the gap this task exists to close: the attacker in scope
    already holds a valid token, so IP-keying does nothing to stop them.

    Here two different users hit the endpoint from the *same* client (so the
    same IP) in the same test. If `user_rate_limit` were swapped back for an
    IP-keyed `rate_limit` -- i.e. if the bucket key stopped including the
    user id -- user A's exhausted attempts would also throttle user B, and
    this test would fail on the `assert first not 429` line below.
    """
    from fastapi.testclient import TestClient
    from zgrader.api.main import app
    from tests.conftest import register_and_verify

    client = TestClient(app)
    token_a = register_and_verify(client, "throttled-a@example.com")
    token_b = register_and_verify(client, "throttled-b@example.com")
    body = {"current_password": "wrong-password", "new_password": "brandnewpass"}

    headers_a = {"Authorization": f"Bearer {token_a}"}
    statuses_a = [
        client.post("/auth/change-password", json=body, headers=headers_a).status_code
        for _ in range(8)
    ]
    assert 429 in statuses_a, f"user A's own limiter never tripped: {statuses_a}"

    # Same TestClient -> same client IP as user A's exhausted requests above.
    headers_b = {"Authorization": f"Bearer {token_b}"}
    response_b = client.post("/auth/change-password", json=body, headers=headers_b)
    assert response_b.status_code != 429, (
        "user B was throttled by user A's attempts from the same IP -- the "
        "limiter is keyed by address instead of by user, which is exactly "
        "the bypass user_rate_limit exists to close"
    )
