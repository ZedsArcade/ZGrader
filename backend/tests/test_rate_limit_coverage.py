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
        if not any("limit" in name.lower() or name == "dependency" for name in names):
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
