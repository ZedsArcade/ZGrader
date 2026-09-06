# Security Remediation Batch 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the seven determinate findings from the 2026-09-06 backend security audit — the ones whose fix approach is fully settled and needs no product decision.

**Architecture:** Four tasks grouped by area, not by finding. Rate limiting is one coherent change (a new user-keyed limiter plus route decoration plus a coverage test that fails on addition). Schema and token hardening are two one-line backend changes with tests. The dev entrypoint guard stands alone. Frontend consistency is mechanical and verified by typecheck, build and a browser assertion, because the frontend has no test runner.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, pytest, Next.js 16, TypeScript.

**Spec:** `docs/superpowers/plans/2026-09-06-remediation-backlog.md` — the backlog is the authority; this plan implements items S1, S3, L4, L5, L7, N2, N3 only.

## Global Constraints

- **Never add a second rate limiter.** Extend the existing `rate_limit(name, limit, window_seconds)` in `backend/zgrader/api/ratelimit.py`, or add a sibling that reuses the same `_limiter` instance. A separate limiter object multiplies silently.
- **Run pytest from Git Bash, never PowerShell.** `tests/test_backup_script.py` self-skips when `bash` is absent from PATH — 15 tests vanish behind a green exit code.
- **Never pipe pytest through `tail` or `head`.** The pipe replaces pytest's exit status with the filter's.
- **The test database name must end in `_test`.** `ZGRADER_TEST_DATABASE_URL` is already set in this environment. `127.0.0.1:5432` is an SSH tunnel to production Postgres; only `zgrader_test` on it is safe.
- **Run the backend suite with WeasyPrint's Pango on PATH**: `export PATH="$PATH:/c/msys64/mingw64/bin"` and `export WEASYPRINT_DLL_DIRECTORIES='C:\msys64\mingw64\bin'`, and invoke `./.venv/Scripts/python.exe -m pytest` from `backend/`. Without this, 12 PDF/publish tests fail for environmental reasons unrelated to the change.
- **Bump `token_version` wherever a credential changes.**
- **Audit `detail` must never carry an email address.**
- **Every setting added to `config.py` must appear in `docker-compose.yml`** or `tests/test_compose_env_coverage.py` fails.
- **One suite at a time against the shared test database.** A second concurrent pytest deletes rows out from under the first.

---

### Task 1: Rate-limit every unprotected route

**Files:**
- Modify: `backend/zgrader/api/ratelimit.py`
- Modify: `backend/zgrader/api/routers/auth.py`
- Modify: `backend/zgrader/api/routers/submissions.py`
- Modify: `backend/zgrader/api/routers/catalog.py`
- Test: `backend/tests/test_rate_limit_coverage.py` (create)

**Interfaces:**
- Consumes: existing `rate_limit(name, limit, window_seconds)` and the module-level `_limiter`.
- Produces: `user_rate_limit(name, limit, window_seconds)` — a FastAPI dependency factory keyed on the authenticated user's id rather than the client IP. Later tasks do not depend on it.

**Why user-keyed matters for `change-password`:** the attacker in scope already holds a valid token. IP-keying lets them rotate addresses; user-keying does not. Every other route stays IP-keyed.

- [ ] **Step 1: Write the failing coverage test**

Create `backend/tests/test_rate_limit_coverage.py`. This is the load-bearing test: it fails on *addition* of an unlimited route, the same way `test_public_payload_key_allowlist` fails on a new public field.

```python
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
```

- [ ] **Step 2: Run it to confirm it fails and names the real routes**

Run from `backend/`:
```
export PATH="$PATH:/c/msys64/mingw64/bin"
./.venv/Scripts/python.exe -m pytest tests/test_rate_limit_coverage.py -q
```
Expected: FAIL, listing roughly thirteen routes including `/auth/change-password`, `/auth/reset-password`, `/auth/google/callback`, the four `/catalog/*` data routes and the submission share/photo/report routes.

- [ ] **Step 3: Add the user-keyed limiter**

In `backend/zgrader/api/ratelimit.py`, below the existing `rate_limit`, reusing the same `_limiter`:

```python
def user_rate_limit(name: str, limit: int, window_seconds: int):
    """Like rate_limit, but keyed on the authenticated user rather than the IP.

    For endpoints where the attacker already holds a valid token: IP-keying
    lets them rotate addresses to refill the bucket, and the account is the
    thing being attacked, not the address.
    """
    from zgrader.api.deps import get_current_user
    from zgrader.models import User

    def dependency(user: "User" = Depends(get_current_user)) -> None:
        retry_after = _limiter.check(f"{name}:user:{user.id}", limit, window_seconds)
        if retry_after is not None:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many attempts. Please wait and try again.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
```

Add `from fastapi import Depends` to the imports if absent. The import of `get_current_user` is deferred inside the factory because `api.deps` imports from `api.ratelimit` at module load, and a top-level import would be circular.

- [ ] **Step 4: Decorate the routes**

Apply these, matching the existing `dependencies=[Depends(...)]` style on each decorator. Values chosen by cost: guessing endpoints tight, reads generous, anything generating a file or mutating in between.

`backend/zgrader/api/routers/auth.py`:
- `POST /change-password` → `user_rate_limit("change_password", limit=5, window_seconds=900)`
- `POST /reset-password` → `rate_limit("reset_password_redeem", limit=10, window_seconds=3600)`
- `POST /verify/{token}` → `rate_limit("verify_redeem", limit=10, window_seconds=3600)`
- `GET /google/start` → `rate_limit("google_start", limit=20, window_seconds=900)`
- `GET /google/callback` → `rate_limit("google_callback", limit=20, window_seconds=900)`

`backend/zgrader/api/routers/submissions.py`:
- `GET /{code}/scans/{side}/photo`, `GET /{code}/scans/{side}/raw`, `GET /{code}/scans/{side}/regions/{category}/{region_id}/crop` → one shared `rate_limit("submission_image", limit=120, window_seconds=60)`
- `GET /{code}/report` → `rate_limit("report_download", limit=20, window_seconds=900)`
- `GET /{code}/share`, `POST /{code}/share`, `POST /{code}/share/rotate`, `DELETE /{code}/share` → one shared `rate_limit("share_manage", limit=30, window_seconds=900)`
- `POST /{code}/regions/toggle`, `POST /{code}/centering-adjust` → one shared `rate_limit("submission_adjust", limit=60, window_seconds=300)`
- `POST /{code}/approve`, `PATCH /{code}/auto-publish` → one shared `rate_limit("operator_publish", limit=60, window_seconds=300)`

`backend/zgrader/api/routers/catalog.py`:
- All six routes → one shared `rate_limit("catalog", limit=120, window_seconds=60)`

Define each shared dependency once at module level (e.g. `_submission_image_limit = rate_limit(...)`) and reference it, matching how `_submission_read_limit` is already defined in `submissions.py`.

- [ ] **Step 5: Add a behavioural test for the change-password limiter**

Append to `backend/tests/test_rate_limit_coverage.py`:

```python
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
```

- [ ] **Step 6: Run both tests to verify they pass**

Run from `backend/`:
```
export PATH="$PATH:/c/msys64/mingw64/bin"
./.venv/Scripts/python.exe -m pytest tests/test_rate_limit_coverage.py -q
```
Expected: 2 passed.

- [ ] **Step 7: Run the auth and submission suites for regressions**

The `_reset_rate_limits` autouse fixture clears counters between tests, but routes that previously had no limiter now do, and existing tests may make enough calls to trip one.

```
./.venv/Scripts/python.exe -m pytest tests/test_api_auth.py tests/test_api_submissions.py tests/test_api_google_auth.py tests/test_api_google_link.py tests/test_api_catalog.py tests/test_public_share.py -q
```
Expected: all pass. If a test now trips a limiter, raise that route's limit rather than weakening the test — the limits above are first estimates, not requirements.

- [ ] **Step 8: Commit**

```bash
git add backend/zgrader/api/ratelimit.py backend/zgrader/api/routers/auth.py backend/zgrader/api/routers/submissions.py backend/zgrader/api/routers/catalog.py backend/tests/test_rate_limit_coverage.py
git commit -m "Rate-limit the routes that had no limiter, and fail on the next one that doesn't"
```

---

### Task 2: Cap submission input and reject tokens with no version claim

**Files:**
- Modify: `backend/zgrader/schemas/submission.py:32-38`
- Modify: `backend/zgrader/auth/security.py:71`
- Test: `backend/tests/test_api_submissions.py` (append), `backend/tests/test_api_auth.py` (append)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Write the failing schema test**

Append to `backend/tests/test_api_submissions.py`:

```python
def test_oversized_card_name_is_refused_not_a_500(db_session):
    """cards.card_name is String(200); without a schema cap the overflow
    reaches Postgres and surfaces as a 500 where a 422 belongs."""
    from tests.conftest import register_and_verify

    token = register_and_verify(client, "longname@example.com")
    resp = client.post(
        "/submissions",
        json={"game": "Pokemon", "card_name": "x" * 300},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422, f"expected validation error, got {resp.status_code}"
```

- [ ] **Step 2: Run it to verify it fails**

```
./.venv/Scripts/python.exe -m pytest tests/test_api_submissions.py::test_oversized_card_name_is_refused_not_a_500 -q
```
Expected: FAIL — a 500 (or a DataError) rather than 422.

- [ ] **Step 3: Add the caps**

In `backend/zgrader/schemas/submission.py`, change `SubmissionCreate` so each field matches its column width in `backend/zgrader/models/card.py` exactly:

```python
class SubmissionCreate(BaseModel):
    # Widths mirror models/card.py exactly. Without them an overlong value
    # reaches Postgres and raises StringDataRightTruncation, which surfaces as
    # a 500 where a 422 belongs -- and these strings also reach the report PDF,
    # the link-preview image and the public share page.
    game: str = Field(min_length=1, max_length=100)
    card_name: str = Field(min_length=1, max_length=200)
    set_name: str | None = Field(default=None, max_length=200)
    card_number: str | None = Field(default=None, max_length=50)
    foil: bool = False
    language: SubmissionLanguage = SubmissionLanguage.en
```

Add `Field` to the `pydantic` import if absent.

- [ ] **Step 4: Run it to verify it passes**

```
./.venv/Scripts/python.exe -m pytest tests/test_api_submissions.py -q
```
Expected: all pass, including the new test.

- [ ] **Step 5: Write the failing token test**

Append to `backend/tests/test_api_auth.py`:

```python
def test_a_token_without_a_version_claim_is_rejected(db_session):
    """`ver` is the revocation mechanism. Accepting a token that lacks it
    treats an unrevokable credential as version 1 forever -- a compatibility
    shim for tokens that expired long ago."""
    import jwt
    from zgrader.config import config
    from zgrader.db import SessionLocal
    from zgrader.models import User

    register_and_verify(client, "nover@example.com")
    with SessionLocal() as session:
        user = session.query(User).filter(User.email == "nover@example.com").one()
        user_id = str(user.id)

    import datetime

    now = datetime.datetime.now(datetime.timezone.utc)
    legacy = jwt.encode(
        {"sub": user_id, "iat": now, "exp": now + datetime.timedelta(hours=1)},
        config.secret_key,
        algorithm="HS256",
    )

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {legacy}"})
    assert resp.status_code == 401
```

- [ ] **Step 6: Run it to verify it fails**

```
./.venv/Scripts/python.exe -m pytest tests/test_api_auth.py::test_a_token_without_a_version_claim_is_rejected -q
```
Expected: FAIL with 200 — the missing claim currently defaults to 1.

- [ ] **Step 7: Reject the missing claim**

In `backend/zgrader/auth/security.py`, replace the `ver` default in `decode_access_token`:

```python
    # `ver` is the revocation mechanism, so a token without it cannot be
    # revoked. The compatibility default that accepted pre-`ver` tokens as
    # version 1 has outlived its purpose: any such token expired long ago,
    # since access tokens live 24 hours.
    version = payload.get("ver")
    if version is None:
        return None
    return user_id, int(version)
```

- [ ] **Step 8: Run the auth suite**

```
./.venv/Scripts/python.exe -m pytest tests/test_api_auth.py tests/test_api_google_auth.py tests/test_api_google_link.py tests/test_account_delete.py -q
```
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add backend/zgrader/schemas/submission.py backend/zgrader/auth/security.py backend/tests/test_api_submissions.py backend/tests/test_api_auth.py
git commit -m "Cap submission fields at their column widths, and stop honouring tokens with no version"
```

---

### Task 3: Refuse to run the dev entrypoint against production

**Files:**
- Modify: `backend/zgrader/dev_trigger.py`
- Test: `backend/tests/test_dev_trigger_guard.py` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: nothing later tasks depend on.

**Context the implementer needs:** `dev_trigger.py` is a developer entrypoint that creates a user and runs the full analysis pipeline against whatever `ZGRADER_DATABASE_URL` names. On this project's development machine, `127.0.0.1:5432` is an SSH tunnel to the *production* Postgres, so the safety property is not theoretical. `tests/conftest.py` carries the pattern to copy: it refuses unless the database name ends in `_test`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_dev_trigger_guard.py`:

```python
"""The dev entrypoint must not be able to write to production.

conftest.py refuses to run the suite unless the database name ends in
'_test', for the same reason: on the development machine 127.0.0.1:5432 is an
SSH tunnel to the deployed Postgres, so a mistyped URL is not a local mistake.
dev_trigger.py had no equivalent guard at all.
"""

import pytest

from zgrader.dev_trigger import refuse_unsafe_database


def test_a_production_looking_url_is_refused():
    with pytest.raises(RuntimeError, match="refusing"):
        refuse_unsafe_database("postgresql+psycopg://zgrader:pw@localhost:5432/zgrader")


def test_a_test_database_is_allowed():
    refuse_unsafe_database("postgresql+psycopg://zgrader:pw@localhost:5432/zgrader_test")


def test_a_dev_database_is_allowed():
    refuse_unsafe_database("postgresql+psycopg://zgrader:pw@localhost:5432/zgrader_dev")
```

- [ ] **Step 2: Run it to verify it fails**

```
./.venv/Scripts/python.exe -m pytest tests/test_dev_trigger_guard.py -q
```
Expected: FAIL with ImportError — `refuse_unsafe_database` does not exist.

- [ ] **Step 3: Add the guard and call it**

In `backend/zgrader/dev_trigger.py`, add near the top:

```python
_SAFE_DATABASE_SUFFIXES = ("_test", "_dev", "_local")


def refuse_unsafe_database(url: str) -> None:
    """Refuse to run against anything that isn't obviously a scratch database.

    This entrypoint creates users and runs the pipeline against whatever
    ZGRADER_DATABASE_URL names. On the development machine 127.0.0.1:5432 is an
    SSH tunnel to production, which looks identical to a local server, so the
    name is checked rather than the host.
    """
    from urllib.parse import urlsplit

    name = urlsplit(url).path.lstrip("/")
    if not name.endswith(_SAFE_DATABASE_SUFFIXES):
        raise RuntimeError(
            f"dev_trigger is refusing to run against database {name!r}. "
            f"Its name must end in one of {_SAFE_DATABASE_SUFFIXES}. This script creates "
            "users and runs the full pipeline, and 127.0.0.1:5432 on a development "
            "machine is often an SSH tunnel to production."
        )
```

Call it as the first statement of `main()` (or whatever function `__main__` invokes), passing `config.database_url`. Import `config` from `zgrader.config` if it is not already imported.

- [ ] **Step 4: Replace the placeholder password hash**

In the same file, `_get_or_create_user` writes `hashed_password="dev-trigger-no-auth"`, which is not a bcrypt hash and sits in a column every login path reads. Replace it with a real hash of a random value:

```python
            hashed_password=hash_password(secrets.token_urlsafe(32)),
```

Add `import secrets` and `from zgrader.auth.security import hash_password`.

- [ ] **Step 5: Run the tests to verify they pass**

```
./.venv/Scripts/python.exe -m pytest tests/test_dev_trigger_guard.py -q
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/zgrader/dev_trigger.py backend/tests/test_dev_trigger_guard.py
git commit -m "Stop the dev entrypoint from being able to write to production"
```

---

### Task 4: Format customer-facing dates in the app's locale, and stop discarding image errors

**Files:**
- Modify: `frontend/app/dashboard/[code]/detail-client.tsx:115`
- Modify: `frontend/app/dashboard/page.tsx:81`
- Modify: `frontend/app/admin/audit-log/page.tsx:116`
- Modify: `frontend/app/admin/contact/page.tsx:109`
- Modify: `frontend/app/admin/page.tsx:148`
- Modify: `frontend/app/admin/settings/page.tsx:362`
- Modify: `frontend/app/admin/[code]/admin-detail-client.tsx:130`
- Modify: `frontend/lib/api.ts` (`fetchAuthedImage`)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: nothing.

**Context the implementer needs:** `Date.toLocaleString()` and `toLocaleDateString()` with no locale argument format to the *browser's* locale, not the app's. `frontend/components/PublicReport.tsx:229` already does this correctly and carries a comment explaining why; copy that pattern. The locale comes from `useLocale()` in `frontend/lib/i18n/context.tsx`. This project has no frontend test runner, so verification is typecheck, build, and a browser assertion.

- [ ] **Step 1: Pass the locale at every call site**

In each file above, obtain `const { locale } = useLocale();` (import from `@/lib/i18n/context` — check whether the component already has it, several do) and pass it as the first argument: `new Date(x).toLocaleString(locale)` / `.toLocaleDateString(locale)`.

The two dashboard files are customer-facing and are the point of this task. The five admin files are the same bug and are fixed in the same pass; the admin pages are not otherwise translated, so if `useLocale` is not already available there, import it — do not skip them.

- [ ] **Step 2: Make the image fetch report what the server said**

In `frontend/lib/api.ts`, `fetchAuthedImage` throws `new ApiError(res.status, notFoundMessage)`, discarding the server's `detail`. `request()` extracts it via `describeDetail`. Make them consistent:

```typescript
export async function fetchAuthedImage(
  token: string,
  url: string,
  notFoundMessage = "Image not available"
): Promise<Blob> {
  const res = await fetch(url, { headers: authHeaders(token) });
  if (!res.ok) {
    // Same extraction request() uses, so an image failure explains itself
    // rather than always reporting the caller's generic default.
    let message = notFoundMessage;
    try {
      const body = await res.json();
      message = describeDetail(body.detail) ?? notFoundMessage;
    } catch {
      // not JSON -- keep the caller's default
    }
    throw new ApiError(res.status, message);
  }
  return res.blob();
}
```

- [ ] **Step 3: Typecheck**

Run from `frontend/`:
```
npx tsc --noEmit
```
Expected: exit 0, no output. This is also the translation-completeness check.

- [ ] **Step 4: Build**

```
npx next build
```
Expected: exit 0, "Compiled successfully".

- [ ] **Step 5: Verify the date renders in the app's locale**

There is no frontend test runner, so assert this in a browser. With the dev server running and signed in, on `/dashboard` with the app language set to Spanish and the browser's own locale left as English, confirm the submission date reads in Spanish format (e.g. `6/9/2026` or `6 sept 2026`) rather than US format (`9/6/2026`). The reverse check matters too: with the app in English the date must not follow a Spanish browser.

- [ ] **Step 6: Commit**

```bash
git add frontend/app frontend/lib/api.ts
git commit -m "Date customer-facing pages in the app's language, not the reader's browser"
```

---

## Self-Review

**Spec coverage.** Backlog items implemented here: S1 (Task 1, Steps 3-5), S3 (Task 1, Step 4), L5 (Task 2, Steps 1-4), N3 (Task 2, Steps 5-7), L4 (Task 3), L7 (Task 4, Step 1), N2 (Task 4, Step 2). All seven determinate items are covered. Items deliberately excluded — S2, S4, L1, L2, L3, L6 — each need a decision that is the project owner's, not an implementer's, and are named in the dispatch notes.

**Placeholders.** No "TBD", no "add appropriate error handling", no step without either exact code or an exact command. Task 4 Step 1 describes a repeated edit across seven files rather than printing seven near-identical snippets; the pattern to copy is named by file and line.

**Type consistency.** `user_rate_limit(name, limit, window_seconds)` matches `rate_limit`'s signature and is referenced with that name in Task 1 Steps 3, 4 and the self-review. `refuse_unsafe_database(url)` is defined in Task 3 Step 3 and imported under that exact name in Step 1's test. `describeDetail` and `ApiError` in Task 4 Step 2 are existing symbols in `frontend/lib/api.ts`.

**Known risk.** Task 1's limit values are first estimates. Step 7 says explicitly to raise a limit rather than weaken a test if an existing test trips one — that is the intended resolution, not a workaround.
