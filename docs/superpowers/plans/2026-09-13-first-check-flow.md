# First Check Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A customer goes from "check a card" to a result on one photo-first page, and a check is charged only when an analysis first produces a score.

**Architecture:** The first upload quietly creates an uncharged draft `Submission`; every existing upload/crop endpoint is reused. `_advance_submission` charges once (conditional update on `submissions.charged_at`) after a scored `run_analysis`; `confirm-crop` refuses with 402 *before* saving the crop. The frontend replaces the details-first form with a shared `SubmissionView` whose first state is a new `CheckFlow` component, and the dashboard list gains names, scores and customer-facing status words.

**Tech Stack:** FastAPI + SQLAlchemy 2 + Alembic + Postgres (pytest against `zgrader_test`); Next.js 16 App Router, HeroUI v3, Tailwind v4, TypeScript.

**Spec:** `docs/superpowers/specs/2026-09-13-first-check-flow-design.md` — read it before Task 1. Section references below (§4.2 etc.) point into it.

## Global Constraints

- Work only in the worktree `C:/Claude/Projects/ZGrader-first-check-flow` on branch `first-check-flow`. The main checkout is on another session's branch with uncommitted work — never switch its branch.
- Tests need `ZGRADER_TEST_DATABASE_URL` pointing at a database whose name ends in `_test`. `127.0.0.1:5432` on this machine is an ssh tunnel to **production** Postgres: never point `ZGRADER_DATABASE_URL` at anything but `zgrader_test` (the preview script in Task 13 refuses otherwise).
- Run pytest from `backend/` with the worktree's own venv: `.venv/Scripts/python -m pytest ...` (Windows). Never pipe pytest through `tail`/`head` — redirect to a file. Only one pytest process at a time against the database.
- Charge rule (spec §3): charged **once**, the first time an analysis gives at least one combined `AnalysisResult` a non-null `raw_score`; errors and all-declined results are free; deleting never refunds.
- Settings: `ZGRADER_MAX_OPEN_DRAFTS` default **3**, `ZGRADER_DRAFT_RETENTION_DAYS` default **7**.
- `card_update` rate limit: `rate_limit("card_update", limit=60, window_seconds=3600)`.
- 409 draft-cap body: `{"message": "You have {n} unfinished checks. Finish or delete one to start another.", "code": "too_many_drafts"}`.
- Copy lives in `frontend/lib/i18n/en.ts` and `es.ts`; every key added to one is added to the other (`npx tsc --noEmit` enforces it). No figures in copy — counts come from `useQuota` via `{count}`. Pass `locale` explicitly to every `toLocaleDateString`.
- Frontend has no unit-test runner; frontend tasks verify with `npx tsc --noEmit`, `npx eslint <files>`, and (Task 12) a browser walk. Read `frontend/node_modules/next/dist/docs/` before using any Next API not already used in the file you are editing.
- Every page: no horizontal scroll at 320/375/768/1024/1280, and no interactive target under 24×24 (measure as `frontend/AGENTS.md` describes).
- Commit after every task with a message ending in `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. `git add` named files only — `backend/tests/fixtures/real_scans/` must never be committed.

## File map

| File | Responsibility |
|---|---|
| `backend/alembic/versions/5c1e8f3a9b27_charge_on_scored_analysis.py` (new) | `charged_at`, `mail_in`, nullable `card_name`, backfill |
| `backend/zgrader/models/submission.py` | new columns, `charged` property, `PRE_ANALYSIS_STATUSES` |
| `backend/zgrader/models/card.py` | `card_name` nullable |
| `backend/zgrader/entitlements.py` | `charge_if_scored` |
| `backend/zgrader/worker/watcher.py` | call `charge_if_scored` in `_advance_submission` |
| `backend/zgrader/api/routers/submissions.py` | create/confirm-crop gates, draft cap, `PATCH /card`, summary builder |
| `backend/zgrader/schemas/submission.py` | `SubmissionCreate`, `CardUpdate`, `CardOut`, `SubmissionSummary`, `SubmissionDetail` |
| `backend/zgrader/schemas/public_report.py` | `PublicCardOut.card_name` optional |
| `backend/zgrader/reports/builder.py`, `reports/strings.py` | "Untitled card" in the PDF |
| `backend/zgrader/worker/main.py` | `purge_stale_drafts` in the retention sweep |
| `backend/zgrader/config.py`, `docker-compose.yml` | two settings |
| `backend/tests/checkflow_helpers.py` (new) | shared create/upload/confirm/fake-analysis helpers |
| `frontend/lib/api.ts` | `ApiError.detail`, `errorCode`, new fields, `updateCard` |
| `frontend/lib/countdown.ts` (new) | `formatRemaining`, moved from `QuotaChip` |
| `frontend/lib/use-submission-poll.ts` (new) | polling hook |
| `frontend/components/StatusBadge.tsx` | customer vocabulary |
| `frontend/components/CropAdjustStep.tsx` | magnifier, keyboard handles, labels, extension props |
| `frontend/components/CardLabelFields.tsx` (new) | name/set/number fields |
| `frontend/components/OutOfChecksPanel.tsx` (new) | exhausted-quota panel |
| `frontend/components/CheckFlow.tsx` (new) | the photo-first page |
| `frontend/components/SubmissionView.tsx` (new) | every state of one submission (was `detail-client`'s body) |
| `frontend/components/UploadStep.tsx` | back photo only |
| `frontend/components/SubmissionOverview.tsx`, `ProcessingState.tsx`, `QuotaChip.tsx` | small props/copy changes |
| `frontend/app/dashboard/new/page.tsx`, `app/dashboard/[code]/detail-client.tsx`, `app/dashboard/page.tsx` | routes |

---

### Task 0: Worktree environment

**Files:** none committed.

- [ ] **Step 1: Backend venv of the worktree's own**

```bash
cd C:/Claude/Projects/ZGrader-first-check-flow/backend
py -3.11 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```

- [ ] **Step 2: Prove imports resolve to the worktree, not the main checkout**

Run: `.venv/Scripts/python -c "import zgrader, os; print(os.path.abspath(zgrader.__file__))"`
Expected: a path under `C:\Claude\Projects\ZGrader-first-check-flow\backend\zgrader`. If it names `C:\Claude\Projects\ZGrader\`, stop — every later test would be testing the wrong code.

- [ ] **Step 3: Baseline suite**

Run: `.venv/Scripts/python -m pytest -q > ../../fcf-baseline.txt 2>&1; echo exit=$?`
Expected: `exit=0`; read the last lines of `fcf-baseline.txt` and record the pass count (753 at `312c996`). Delete the file afterwards.

- [ ] **Step 4: Frontend dependencies**

```bash
cd C:/Claude/Projects/ZGrader-first-check-flow/frontend
npm ci
npx tsc --noEmit
```
Expected: no output from `tsc`.

---

### Task 1: Schema — `charged_at`, `mail_in`, nullable `card_name`

**Files:**
- Create: `backend/alembic/versions/5c1e8f3a9b27_charge_on_scored_analysis.py`
- Modify: `backend/zgrader/models/submission.py`, `backend/zgrader/models/card.py`
- Test: `backend/tests/test_migrations.py`

**Interfaces:**
- Produces: `Submission.charged_at: datetime | None`, `Submission.mail_in: bool`, `Submission.charged` (property, `charged_at is not None`), `Card.card_name: str | None`, and `PRE_ANALYSIS_STATUSES = (SubmissionStatus.created, SubmissionStatus.awaiting_scans)` in `zgrader.models.submission`.

- [ ] **Step 1: Write the failing migration test** — append to `backend/tests/test_migrations.py`:

```python
def _execute(url: str, *statements: str) -> None:
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            for sql in statements:
                conn.execute(text(sql))
    finally:
        engine.dispose()


def test_existing_submissions_are_backfilled_as_already_charged(scratch_database):
    """Every submission before this migration was charged when it was created.

    Left NULL, the next re-analysis of any of them -- a late back photo, an
    operator re-run -- would satisfy the new charge-on-score rule and bill the
    customer a second time for a check they already paid for.
    """
    _alembic(scratch_database, "upgrade", "9e3b5d1f7a24")
    _execute(
        scratch_database,
        "INSERT INTO users (id, email, is_verified, role, token_version, marketing_consent, "
        "created_at, updated_at) VALUES ('00000000-0000-0000-0000-0000000000a1', "
        "'backfill@example.com', true, 'client', 1, false, now(), now())",
        "INSERT INTO submissions (id, submission_code, user_id, status, created_at, updated_at) "
        "VALUES ('00000000-0000-0000-0000-0000000000b1', 'SUB-77777', "
        "'00000000-0000-0000-0000-0000000000a1', 'published', "
        "'2026-01-02T03:04:05+00', now())",
    )

    _alembic(scratch_database, "upgrade", "head")

    assert _query(
        scratch_database,
        "SELECT charged_at = created_at FROM submissions WHERE submission_code = 'SUB-77777'",
    ) is True
    assert _query(
        scratch_database, "SELECT mail_in FROM submissions WHERE submission_code = 'SUB-77777'"
    ) is False
    assert _query(
        scratch_database,
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_name = 'cards' AND column_name = 'card_name'",
    ) == "YES"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_migrations.py::test_existing_submissions_are_backfilled_as_already_charged -v`
Expected: FAIL — `column "charged_at" does not exist`.

- [ ] **Step 3: Write the migration** — `backend/alembic/versions/5c1e8f3a9b27_charge_on_scored_analysis.py`:

```python
"""Charge a check when an analysis scores it, not when a submission is created

A check used to be spent at "Create submission", before any photo existed, so
abandoning at the upload step -- or a photo that never cropped -- still cost
one. It is now spent the first time an analysis gives the submission a score,
and `charged_at` records that it happened, which is what keeps a re-analysis
(a late back photo) from charging twice.

Every existing row is backfilled to its `created_at`: all of them were charged
at creation under the old rule, and NULL would read as "never charged".

`mail_in` marks a submission whose card is coming by post. It has no photos
for days by design, so the draft cap and the stale-draft sweep must not treat
it as abandoned.

`cards.card_name` becomes optional: the photo-first page asks for the photo
first and the name is a label the customer may add later.

Revision ID: 5c1e8f3a9b27
Revises: 9e3b5d1f7a24
"""

import sqlalchemy as sa
from alembic import op

revision = "5c1e8f3a9b27"
down_revision = "9e3b5d1f7a24"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("charged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "submissions",
        sa.Column("mail_in", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE submissions SET charged_at = created_at")
    op.alter_column("cards", "card_name", existing_type=sa.String(200), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE cards SET card_name = 'Untitled card' WHERE card_name IS NULL")
    op.alter_column("cards", "card_name", existing_type=sa.String(200), nullable=False)
    op.drop_column("submissions", "mail_in")
    op.drop_column("submissions", "charged_at")
```

- [ ] **Step 4: Models** — in `backend/zgrader/models/submission.py`, after the `SubmissionLanguage` class add:

```python
#: Statuses a submission is in before any analysis has run on it. The draft
#: cap, the stale-draft sweep and the foil lock all mean exactly this set.
PRE_ANALYSIS_STATUSES = (SubmissionStatus.created, SubmissionStatus.awaiting_scans)
```

and inside `Submission`, after `share_enabled_at`:

```python
    # When a check was spent on this submission: the first time an analysis
    # gave it a score. NULL means nothing has been charged -- a draft, a
    # pipeline error, or a result where every category declined. Written only
    # by entitlements.charge_if_scored, as a conditional UPDATE, so two
    # analyses racing on one submission cannot charge twice.
    charged_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # The card is coming by post and the operator will scan it. Such a
    # submission has no photos for days by design, so the draft cap and the
    # stale-draft sweep leave it alone.
    mail_in: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
```

and after the `client_adjusted` property:

```python
    @property
    def charged(self) -> bool:
        return self.charged_at is not None
```

In `backend/zgrader/models/card.py` change the `card_name` line to:

```python
    # Optional since the photo-first check page: the photo comes first and the
    # name is a label the customer may add later. Every reader falls back to
    # "Untitled card" (PDF, emails and link preview already cope with None).
    card_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
```

- [ ] **Step 5: Run the migration tests**

Run: `.venv/Scripts/python -m pytest tests/test_migrations.py -v`
Expected: all PASS, including the reverse-and-reapply test (it exercises `downgrade()`).

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/5c1e8f3a9b27_charge_on_scored_analysis.py backend/zgrader/models/submission.py backend/zgrader/models/card.py backend/tests/test_migrations.py
git commit -m "Add charged_at and mail_in to submissions; card name becomes optional"
```

### Task 2: Charge when an analysis first scores

**Files:**
- Create: `backend/tests/checkflow_helpers.py`, `backend/tests/test_charge_on_score.py`
- Modify: `backend/zgrader/entitlements.py`, `backend/zgrader/worker/watcher.py`, `backend/zgrader/api/routers/submissions.py` (create stops consuming), `backend/zgrader/schemas/submission.py` (`charged` on the detail)
- Rewrite: `backend/tests/test_api_quota.py`; Modify: `backend/tests/test_api_admin_quota.py`

**Interfaces:**
- Consumes: `Submission.charged_at`, `Submission.charged` (Task 1).
- Produces: `entitlements.charge_if_scored(db: Session, submission: Submission) -> bool`; `SubmissionDetail.charged: bool`; test helpers module `tests.checkflow_helpers` with `client`, `headers(token)`, `login(email)`, `create(token, **fields)`, `create_code(token, **fields)`, `upload(token, code, side, path)`, `confirm(token, code, side)`, `detail(token, code)`, `quota(token)`, `set_free_limit(db, limit, period_days=7)`, `spend(db, email, used)`, `fake_analysis(score)`.

- [ ] **Step 1: Shared helpers** — `backend/tests/checkflow_helpers.py`:

```python
"""Shared steps for the first-check-flow tests: an account, a draft, a photo, a crop.

The charging rule is only visible end to end -- create, upload, confirm -- so
every test in this family walks that path, and doing it through one set of
helpers keeps them all walking it the same way.
"""

import datetime

from fastapi.testclient import TestClient

from zgrader.api.main import app
from zgrader.models import (
    AnalysisCategory,
    AnalysisResult,
    AnalysisSide,
    PlanEntitlement,
    SubmissionStatus,
    User,
)

from tests.conftest import register_and_verify

client = TestClient(app)

CATEGORIES = (
    AnalysisCategory.centering,
    AnalysisCategory.corners,
    AnalysisCategory.edges,
    AnalysisCategory.surface,
)


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(email: str) -> str:
    return register_and_verify(client, email)


def create(token: str, **fields):
    return client.post("/submissions", json={"game": "Pokemon", **fields}, headers=headers(token))


def create_code(token: str, **fields) -> str:
    resp = create(token, **fields)
    assert resp.status_code == 201, resp.text
    return resp.json()["submission_code"]


def upload(token: str, code: str, side: str, path):
    with open(path, "rb") as f:
        return client.post(
            f"/submissions/{code}/scans",
            files={"file": (f"{side}.png", f, "image/png")},
            data={"side": side},
            headers=headers(token),
        )


def confirm(token: str, code: str, side: str):
    """Accept the suggested crop verbatim, as a customer who changes nothing would."""
    suggestion = client.get(
        f"/submissions/{code}/scans/{side}/suggest-crop", headers=headers(token)
    ).json()
    return client.post(
        f"/submissions/{code}/scans/{side}/confirm-crop",
        json={"points": suggestion["points"]},
        headers=headers(token),
    )


def detail(token: str, code: str) -> dict:
    return client.get(f"/submissions/{code}", headers=headers(token)).json()


def quota(token: str) -> dict:
    return client.get("/submissions/quota", headers=headers(token)).json()


def set_free_limit(db_session, limit, period_days: int = 7) -> None:
    row = db_session.query(PlanEntitlement).filter(PlanEntitlement.plan == "free").one()
    row.submission_limit = limit
    row.period_days = period_days
    db_session.commit()


def spend(db_session, email: str, used: int) -> None:
    """Stand in for `used` scored checks already spent this window."""
    user = db_session.query(User).filter(User.email == email).one()
    user.quota_used = used
    user.quota_period_started_at = datetime.datetime.now(datetime.timezone.utc)
    db_session.commit()


def fake_analysis(score: float | None):
    """A stand-in for pipeline.run_analysis writing four combined rows at `score`.

    None reproduces the all-declined result a failed geometry fit produces,
    which the sample fixtures never do -- all 23 fit cleanly, see AGENTS.md.
    Patch it in with monkeypatch.setattr(pipeline, "run_analysis", ...).
    """

    def run(db, submission):
        db.query(AnalysisResult).filter(AnalysisResult.submission_id == submission.id).delete(
            synchronize_session=False
        )
        for category in CATEGORIES:
            db.add(
                AnalysisResult(
                    submission_id=submission.id,
                    category=category,
                    side=AnalysisSide.combined,
                    raw_score=score,
                    measurements={},
                    flags={},
                )
            )
        submission.status = SubmissionStatus.draft_ready
        db.flush()
        db.expire(submission, ["analysis_results"])

    return run
```

- [ ] **Step 2: Write the failing tests** — `backend/tests/test_charge_on_score.py`:

```python
"""A check is charged when an analysis first scores the card, and only then.

It used to be charged at "Create submission", before any photo existed, so an
abandoned draft or a photo that never cropped still cost one. These pin the
rule from both directions: what charges, and everything that must not.
"""

import datetime
import shutil
from pathlib import Path

from zgrader import entitlements
from zgrader.analysis import pipeline
from zgrader.auth.security import hash_password
from zgrader.config import config
from zgrader.models import (
    AnalysisCategory,
    AnalysisResult,
    AnalysisSide,
    AuditLog,
    Card,
    Submission,
    SubmissionStatus,
    User,
)
from zgrader.worker.watcher import process_submission_folder

from tests import checkflow_helpers as h


def test_creating_and_uploading_does_not_charge(db_session, sample_scan_paths):
    h.set_free_limit(db_session, 3)
    token = h.login("charge-none@example.com")
    code = h.create_code(token)
    assert h.upload(token, code, "front", sample_scan_paths["pokemon_front"]).status_code == 200

    assert h.quota(token)["remaining"] == 3
    assert h.quota(token)["resets_at"] is None
    assert h.detail(token, code)["charged"] is False


def test_a_scored_analysis_charges_once_and_opens_the_window(db_session, sample_scan_paths):
    h.set_free_limit(db_session, 3)
    token = h.login("charge-scored@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])

    resp = h.confirm(token, code, "front")

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "draft_ready"
    assert resp.json()["charged"] is True
    body = h.quota(token)
    assert body["used"] == 1
    assert body["resets_at"] is not None
    assert db_session.query(AuditLog).filter(AuditLog.action == "check_charged").count() == 1


def test_adding_the_back_does_not_charge_again(db_session, sample_scan_paths):
    h.set_free_limit(db_session, 3)
    token = h.login("charge-back@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])
    h.confirm(token, code, "front")
    h.upload(token, code, "back", sample_scan_paths["pokemon_back"])

    assert h.confirm(token, code, "back").status_code == 200
    assert h.quota(token)["used"] == 1


def test_an_all_declined_result_is_free_and_a_later_scored_run_charges(
    db_session, sample_scan_paths, monkeypatch
):
    h.set_free_limit(db_session, 3)
    token = h.login("charge-declined@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])

    monkeypatch.setattr(pipeline, "run_analysis", h.fake_analysis(None))
    front = h.confirm(token, code, "front")
    assert front.status_code == 200
    assert front.json()["charged"] is False
    assert h.quota(token)["remaining"] == 3

    h.upload(token, code, "back", sample_scan_paths["pokemon_back"])
    monkeypatch.setattr(pipeline, "run_analysis", h.fake_analysis(9.0))
    back = h.confirm(token, code, "back")
    assert back.json()["charged"] is True
    assert h.quota(token)["remaining"] == 2


def test_a_pipeline_error_is_free(db_session, sample_scan_paths, monkeypatch):
    h.set_free_limit(db_session, 3)
    token = h.login("charge-error@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])

    def boom(db, submission):
        raise pipeline.PipelineError("boom")

    monkeypatch.setattr(pipeline, "run_analysis", boom)
    resp = h.confirm(token, code, "front")

    assert resp.json()["status"] == "error"
    assert resp.json()["charged"] is False
    assert h.quota(token)["remaining"] == 3


def test_the_charge_is_claimed_once_even_when_asked_twice(db_session):
    """The API and the worker can both finish an analysis of one submission.
    The conditional UPDATE is what makes the second one a no-op."""
    user = User(email="charge-twice@example.com", hashed_password=hash_password("hunter2pass"), is_verified=True)
    db_session.add(user)
    db_session.flush()
    submission = Submission(submission_code="SUB-90901", user_id=user.id, status=SubmissionStatus.draft_ready)
    db_session.add(submission)
    db_session.flush()
    db_session.add(
        AnalysisResult(
            submission_id=submission.id,
            category=AnalysisCategory.corners,
            side=AnalysisSide.combined,
            raw_score=9.0,
            measurements={},
            flags={},
        )
    )
    db_session.flush()

    assert entitlements.charge_if_scored(db_session, submission) is True
    assert entitlements.charge_if_scored(db_session, submission) is False
    db_session.commit()
    db_session.refresh(user)
    assert user.quota_used == 1


def test_the_worker_charges_and_never_refuses(db_session, sample_scan_paths):
    """An operator drop has nowhere to send a 402, so it runs and charges even
    on an account that is already out of checks."""
    h.set_free_limit(db_session, 1)
    user = User(email="charge-worker@example.com", hashed_password=hash_password("hunter2pass"), is_verified=True)
    user.quota_used = 1
    user.quota_period_started_at = datetime.datetime.now(datetime.timezone.utc)
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code="SUB-90902", user_id=user.id, status=SubmissionStatus.created, mail_in=True
    )
    db_session.add(submission)
    db_session.flush()
    db_session.add(Card(submission_id=submission.id, game="Pokemon", card_name="Posted card"))
    db_session.commit()

    folder = Path(config.scans_dir) / "SUB-90902"
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy(sample_scan_paths["pokemon_front"], folder / "front.png")
    process_submission_folder(db_session, "SUB-90902", folder)

    db_session.refresh(submission)
    db_session.refresh(user)
    assert submission.status == SubmissionStatus.draft_ready
    assert submission.charged_at is not None
    assert user.quota_used == 2
```

- [ ] **Step 3: Run them to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_charge_on_score.py -v`
Expected: FAIL — `KeyError: 'charged'` / `AttributeError: module 'zgrader.entitlements' has no attribute 'charge_if_scored'`, and the first test fails on `remaining == 3` (create still consumes).

- [ ] **Step 4: `charge_if_scored`** — in `backend/zgrader/entitlements.py` change the imports to

```python
from sqlalchemy import update
from sqlalchemy.orm import Session

from zgrader.models import AnalysisResult, AnalysisSide, AuditLog, Submission, User
```

(keeping the existing `plan_entitlement` and `subscription` imports), update the module docstring's "**Usage is counted, not derived.**" paragraph so its first sentence reads "`User.quota_used` is incremented when an analysis first gives a submission a score (`charge_if_scored`) and never decremented.", and append:

```python
def charge_if_scored(db: Session, submission: Submission) -> bool:
    """Spend one check on `submission` if analysis scored it and nothing has yet.

    "Scored" is at least one combined result with a number. A pipeline error,
    or a result where every category declined (a failed geometry fit), costs
    nothing: the customer got no answer. Read from the database rather than
    `submission.analysis_results`, which the pipeline's bulk deletes leave
    stale.

    The claim is a conditional UPDATE, so of two analyses finishing on one
    submission -- the API and the worker are not serialised -- only one sees
    a row change and only that one spends the check. Returns whether this
    call charged. The caller owns the commit, which lands the charge in the
    same transaction as the status change it accompanies.
    """
    scored = db.query(
        db.query(AnalysisResult)
        .filter(
            AnalysisResult.submission_id == submission.id,
            AnalysisResult.side == AnalysisSide.combined,
            AnalysisResult.raw_score.isnot(None),
        )
        .exists()
    ).scalar()
    if not scored:
        return False

    claimed = db.execute(
        update(Submission)
        .where(Submission.id == submission.id, Submission.charged_at.is_(None))
        .values(charged_at=_now())
        .execution_options(synchronize_session=False)
    ).rowcount
    if claimed != 1:
        return False
    db.expire(submission, ["charged_at"])

    user = submission.user
    consume_submission(db, user)
    db.add(
        AuditLog(
            submission_id=submission.id,
            user_id=user.id,
            action="check_charged",
            detail={"plan": active_plan(db, user)},
        )
    )
    db.flush()
    return True
```

Also change `consume_submission`'s docstring first line to "Spend one credit. Called only by `charge_if_scored`."

- [ ] **Step 5: Call it** — in `backend/zgrader/worker/watcher.py` add `entitlements` to the `from zgrader import images` line (`from zgrader import entitlements, images`), and in `_advance_submission` insert directly after the `try: pipeline.run_analysis(...) except ...: return submission` block and before `settings = db.query(Settings).first()`:

```python
    # Here rather than in run_analysis (which knows nothing of billing, so
    # dev_trigger stays free) or in a caller (both the API's confirm-crop and
    # the worker end here, so they charge identically).
    entitlements.charge_if_scored(db, submission)
```

- [ ] **Step 6: Create stops consuming** — in `create_submission` (`backend/zgrader/api/routers/submissions.py`) delete the three-line comment and `entitlements.consume_submission(db, user)` call, and replace the comment above the quota check with:

```python
    # Checked before anything is created, so a refused submission leaves no
    # row, no folder and no half-state behind. Nothing is spent here: a check
    # is charged when an analysis first scores the card (see
    # entitlements.charge_if_scored), so an abandoned draft costs nothing.
```

In `backend/zgrader/schemas/submission.py` add to `SubmissionDetail`, after `auto_publish`:

```python
    # Whether a check has been spent on this submission. Read from the
    # model's `charged` property (charged_at is not None).
    charged: bool = False
```

- [ ] **Step 7: Rewrite `backend/tests/test_api_quota.py`** with:

```python
"""Submission quotas, end to end.

tests/test_entitlements.py covers the rollover arithmetic in isolation. This
covers the parts that only exist once a database and a router are involved:
that the cap actually refuses, that refusing leaves nothing behind, and above
all that a spent credit stays spent.

A credit is spent when an analysis first scores a card, not at create --
tests/test_charge_on_score.py pins that rule. Here `h.spend` stands in for
checks already spent, so these tests stay about the cap itself.
"""

import datetime

from zgrader.config import config
from zgrader.models import PlanEntitlement, Submission, User
from zgrader.models.subscription import Subscription, SubscriptionStatus

from tests import checkflow_helpers as h


def test_quota_starts_full_with_no_countdown(db_session):
    """Before a first check there is no open window, so nothing is counting
    down -- the whole allowance is simply available."""
    h.set_free_limit(db_session, 3)
    token = h.login("quota-fresh@example.com")

    body = h.quota(token)
    assert body["plan"] == "free"
    assert body["unlimited"] is False
    assert body["limit"] == 3
    assert body["used"] == 0
    assert body["remaining"] == 3
    assert body["resets_at"] is None


def test_creating_a_submission_spends_nothing(db_session):
    h.set_free_limit(db_session, 3)
    token = h.login("quota-create@example.com")

    assert h.create(token).status_code == 201
    body = h.quota(token)
    assert body["used"] == 0
    assert body["resets_at"] is None


def test_an_exhausted_allowance_refuses_create_with_402(db_session):
    h.set_free_limit(db_session, 2)
    token = h.login("quota-exhaust@example.com")
    h.spend(db_session, "quota-exhaust@example.com", 2)

    refused = h.create(token)
    assert refused.status_code == 402
    assert refused.json()["detail"]["limit"] == 2
    assert h.quota(token)["remaining"] == 0


def test_a_refused_submission_leaves_nothing_behind(db_session):
    """The check runs before anything is created, so a refusal must not leave
    a half-made submission or an orphan scans folder on disk."""
    h.set_free_limit(db_session, 1)
    token = h.login("quota-nothing-behind@example.com")
    h.spend(db_session, "quota-nothing-behind@example.com", 1)

    before_rows = db_session.query(Submission).count()
    before_dirs = sorted(p.name for p in config.scans_dir.iterdir()) if config.scans_dir.exists() else []

    assert h.create(token).status_code == 402

    db_session.expire_all()
    after_dirs = sorted(p.name for p in config.scans_dir.iterdir()) if config.scans_dir.exists() else []
    assert db_session.query(Submission).count() == before_rows
    assert after_dirs == before_dirs


def test_deleting_a_submission_does_not_refund_the_credit(db_session, sample_scan_paths):
    """The reason usage is a counter rather than a COUNT(*) of live rows.

    Submissions can be deleted in any status, so deriving usage would hand the
    credit straight back -- and at zero remaining that is an unlimited-retry
    loop, available to anyone who noticed.
    """
    h.set_free_limit(db_session, 1)
    token = h.login("quota-no-refund@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])
    assert h.confirm(token, code, "front").json()["charged"] is True

    assert h.client.delete(f"/submissions/{code}", headers=h.headers(token)).status_code == 204

    assert h.client.get(f"/submissions/{code}", headers=h.headers(token)).status_code == 404
    assert h.quota(token)["remaining"] == 0
    assert h.create(token).status_code == 402


def test_an_unlimited_plan_is_never_refused(db_session):
    """How a subscription is expressed: a null limit on the plan. Three
    creates, not more: the open-draft cap is a separate limit and applies to
    every plan."""
    token = h.login("quota-unlimited@example.com")
    user = db_session.query(User).filter(User.email == "quota-unlimited@example.com").one()
    db_session.add(PlanEntitlement(plan="tier1", submission_limit=None, period_days=7))
    db_session.add(Subscription(user_id=user.id, plan="tier1", status=SubscriptionStatus.active))
    db_session.commit()

    body = h.quota(token)
    assert body["plan"] == "tier1"
    assert body["unlimited"] is True
    assert body["remaining"] is None
    assert body["resets_at"] is None

    for i in range(3):
        assert h.create(token, card_name=f"card {i}").status_code == 201
    assert h.quota(token)["unlimited"] is True


def test_a_lapsed_subscription_falls_back_to_the_free_tier(db_session):
    h.set_free_limit(db_session, 1)
    token = h.login("quota-lapsed@example.com")
    user = db_session.query(User).filter(User.email == "quota-lapsed@example.com").one()
    db_session.add(PlanEntitlement(plan="tier1", submission_limit=None, period_days=7))
    subscription = Subscription(user_id=user.id, plan="tier1", status=SubscriptionStatus.active)
    db_session.add(subscription)
    db_session.commit()

    assert h.quota(token)["unlimited"] is True

    subscription.status = SubscriptionStatus.canceled
    db_session.commit()

    body = h.quota(token)
    assert body["plan"] == "free"
    assert body["unlimited"] is False
    assert body["remaining"] == 1


def test_the_window_rolls_forward_and_restores_the_allowance(db_session):
    h.set_free_limit(db_session, 1, period_days=7)
    token = h.login("quota-rollover@example.com")
    h.spend(db_session, "quota-rollover@example.com", 1)
    assert h.create(token).status_code == 402

    user = db_session.query(User).filter(User.email == "quota-rollover@example.com").one()
    user.quota_period_started_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=8)
    db_session.commit()

    body = h.quota(token)
    assert body["used"] == 0
    assert body["remaining"] == 1
    assert h.create(token).status_code == 201


def test_an_unknown_plan_falls_back_to_free_rather_than_unlimited(db_session):
    """A Stripe price nobody has configured here yet must not silently become
    an unlimited plan."""
    h.set_free_limit(db_session, 1)
    token = h.login("quota-unknown-plan@example.com")
    user = db_session.query(User).filter(User.email == "quota-unknown-plan@example.com").one()
    db_session.add(Subscription(user_id=user.id, plan="enterprise-2027", status=SubscriptionStatus.active))
    db_session.commit()

    assert h.quota(token)["unlimited"] is False
    h.spend(db_session, "quota-unknown-plan@example.com", 1)
    assert h.create(token).status_code == 402


def test_quota_requires_authentication():
    assert h.client.get("/submissions/quota").status_code == 401
```

- [ ] **Step 8: Adjust `backend/tests/test_api_admin_quota.py`** — in `test_operator_can_look_up_a_customer_by_email` change `assert rows[0]["remaining"] == 2` to `assert rows[0]["remaining"] == 3` with the comment `# Creating a submission spends nothing; a check is charged when analysis scores it.` Replace the first six lines of the body of `test_operator_restores_credits_after_something_went_wrong` after `customer = register_and_verify(...)` with:

```python
    # Two scored checks already spent this window.
    user = db_session.query(User).filter(User.email == "wasted@example.com").one()
    user.quota_used = 2
    user.quota_period_started_at = datetime.datetime.now(datetime.timezone.utc)
    db_session.commit()
    assert _create(customer, "three").status_code == 402
```

and drop the now-duplicate `user = ...` lookup that follows; add `import datetime` at the top of the file.

- [ ] **Step 9: Run the affected tests**

Run: `.venv/Scripts/python -m pytest tests/test_charge_on_score.py tests/test_api_quota.py tests/test_api_admin_quota.py tests/test_api_submissions.py -v`
Expected: all PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/zgrader/entitlements.py backend/zgrader/worker/watcher.py backend/zgrader/api/routers/submissions.py backend/zgrader/schemas/submission.py backend/tests/checkflow_helpers.py backend/tests/test_charge_on_score.py backend/tests/test_api_quota.py backend/tests/test_api_admin_quota.py
git commit -m "Charge a check when analysis first scores the card, not at create"
```

---

### Task 3: Refuse confirm-crop with 402 before the crop is saved

**Files:**
- Modify: `backend/zgrader/api/routers/submissions.py`
- Create: `backend/tests/test_confirm_crop_quota_gate.py`

**Interfaces:**
- Consumes: `charge_if_scored` (Task 2), `tests.checkflow_helpers`.
- Produces: `_quota_exhausted(quota: entitlements.Quota) -> HTTPException` in the router, used by create and confirm-crop.

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_confirm_crop_quota_gate.py`:

```python
"""An uncharged draft cannot be analysed once the account is out of checks.

The refusal has to come before the crop is saved. confirm-crop stores the
crop points first; a 402 raised after that would leave the front confirmed,
and the worker's poll -- which never refuses -- would then analyse it anyway
and charge the account past its limit.
"""

from tests import checkflow_helpers as h


def test_confirm_is_refused_with_402_before_the_crop_is_saved(db_session, sample_scan_paths):
    h.set_free_limit(db_session, 1)
    token = h.login("gate-refused@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])
    h.spend(db_session, "gate-refused@example.com", 1)

    resp = h.confirm(token, code, "front")

    assert resp.status_code == 402
    assert resp.json()["detail"]["limit"] == 1
    body = h.detail(token, code)
    assert body["confirmed_sides"] == []
    assert body["status"] in ("created", "awaiting_scans")
    assert body["charged"] is False


def test_a_charged_submission_can_add_its_back_when_out_of_checks(db_session, sample_scan_paths):
    """The back completes a check already paid for; it is not a new one."""
    h.set_free_limit(db_session, 1)
    token = h.login("gate-back@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])
    assert h.confirm(token, code, "front").json()["charged"] is True
    assert h.quota(token)["remaining"] == 0

    h.upload(token, code, "back", sample_scan_paths["pokemon_back"])
    assert h.confirm(token, code, "back").status_code == 200
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_confirm_crop_quota_gate.py -v`
Expected: first test FAILS (status 200, not 402).

- [ ] **Step 3: Implement** — in `backend/zgrader/api/routers/submissions.py`, add after `_get_owned_submission`:

```python
def _quota_exhausted(quota: entitlements.Quota) -> HTTPException:
    return HTTPException(
        status.HTTP_402_PAYMENT_REQUIRED,
        {
            "message": (
                "You've used all your checks for this period. They reset automatically, "
                "or a subscription removes the limit."
            ),
            "limit": quota.limit,
            "used": quota.used,
            "resets_at": quota.resets_at.isoformat() if quota.resets_at else None,
        },
    )
```

In `create_submission` replace the inline `raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, {...})` with `raise _quota_exhausted(quota)`. In `confirm_crop`, directly after the `_UPLOADABLE_STATUSES` check and **before** `scan = _get_scan(...)`, insert:

```python
    # Before the crop is saved, not after: saved crop points make the front
    # "confirmed", and the worker's poll analyses confirmed fronts without
    # asking anyone -- so a refusal here that left them stored would be
    # followed by a charge past the limit anyway. A charged submission is
    # completing a check already paid for (typically adding its back).
    if submission.charged_at is None:
        quota = entitlements.get_quota(db, submission.user)
        if not quota.can_submit:
            db.commit()  # keep a rolled-forward window, as GET /quota does
            raise _quota_exhausted(quota)
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python -m pytest tests/test_confirm_crop_quota_gate.py tests/test_api_quota.py tests/test_capacity.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/zgrader/api/routers/submissions.py backend/tests/test_confirm_crop_quota_gate.py
git commit -m "Refuse confirm-crop with 402 before saving the crop when out of checks"
```

---

### Task 4: Optional name, mail-in, the draft cap, and the received email

**Files:**
- Modify: `backend/zgrader/schemas/submission.py`, `backend/zgrader/api/routers/submissions.py`, `backend/zgrader/config.py`, `docker-compose.yml`, `backend/tests/test_email.py`
- Create: `backend/tests/test_submission_drafts.py`

**Interfaces:**
- Consumes: `Submission.mail_in`, `PRE_ANALYSIS_STATUSES` (Task 1); helpers (Task 2).
- Produces: `SubmissionCreate.card_name: str | None`, `SubmissionCreate.mail_in: bool`; `SubmissionDetail.mail_in: bool`; `CardOut.card_name: str | None`; `config.max_open_drafts: int = 3`, `config.draft_retention_days: int = 7` (the second is read in Task 6).

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_submission_drafts.py`:

```python
"""Photo drafts: created without a name, capped per account, never charged
until analysis scores them. Mail-in submissions are exempt from the cap --
their card is in the post and there is nothing for the customer to finish.
"""

from zgrader.analysis import pipeline
from zgrader.auth.security import hash_password
from zgrader.config import config
from zgrader.models import User, UserRole

from tests import checkflow_helpers as h


def test_a_draft_needs_no_card_name(db_session):
    token = h.login("draft-noname@example.com")
    resp = h.create(token)
    assert resp.status_code == 201
    assert resp.json()["card"]["card_name"] is None
    assert resp.json()["mail_in"] is False


def test_a_blank_card_name_is_stored_as_none(db_session):
    token = h.login("draft-blank@example.com")
    assert h.create(token, card_name="   ").json()["card"]["card_name"] is None


def test_mail_in_requires_a_card_name(db_session):
    """The operator matches the physical card to its submission by name."""
    token = h.login("draft-mailin-noname@example.com")
    assert h.create(token, mail_in=True).status_code == 422
    assert h.create(token, mail_in=True, card_name="Charizard").status_code == 201


def test_a_fourth_open_draft_is_refused_with_409(db_session):
    token = h.login("draft-cap@example.com")
    for _ in range(3):
        h.create_code(token)

    refused = h.create(token)

    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "too_many_drafts"


def test_mail_in_submissions_do_not_count_toward_the_cap(db_session):
    token = h.login("draft-cap-mailin@example.com")
    for _ in range(3):
        h.create_code(token)
    assert h.create(token, mail_in=True, card_name="Posted").status_code == 201


def test_an_analysed_draft_no_longer_counts(db_session, sample_scan_paths, monkeypatch):
    h.set_free_limit(db_session, 10)
    token = h.login("draft-cap-analysed@example.com")
    codes = [h.create_code(token) for _ in range(3)]
    h.upload(token, codes[0], "front", sample_scan_paths["pokemon_front"])
    monkeypatch.setattr(pipeline, "run_analysis", h.fake_analysis(9.0))
    assert h.confirm(token, codes[0], "front").status_code == 200

    assert h.create(token).status_code == 201


def test_operators_are_exempt_from_the_cap(db_session):
    db_session.add(
        User(email="draft-op@example.com", hashed_password=hash_password("hunter2pass"), role=UserRole.operator, is_verified=True)
    )
    db_session.commit()
    token = h.client.post(
        "/auth/login", data={"username": "draft-op@example.com", "password": "hunter2pass"}
    ).json()["access_token"]
    for _ in range(4):
        assert h.create(token).status_code == 201


def test_the_cap_comes_from_config(db_session, monkeypatch):
    monkeypatch.setattr(config, "max_open_drafts", 1)
    token = h.login("draft-cap-config@example.com")
    h.create_code(token)
    assert h.create(token).status_code == 409
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_submission_drafts.py -v`
Expected: FAIL — 422 on the missing `card_name`, no `mail_in` key, no 409.

- [ ] **Step 3: Schemas** — in `backend/zgrader/schemas/submission.py` import `model_validator` alongside `field_validator`, and replace `SubmissionCreate` with:

```python
class SubmissionCreate(BaseModel):
    # Widths mirror models/card.py exactly. Without them an overlong value
    # reaches Postgres and raises StringDataRightTruncation, which surfaces as
    # a 500 where a 422 belongs -- and these strings also reach the report PDF,
    # the link-preview image and the public share page.
    game: str = Field(min_length=1, max_length=100)
    # Optional: the photo-first page creates the draft from the photo, and the
    # name is a label the customer may add later with PATCH .../card.
    card_name: str | None = Field(default=None, max_length=200)
    set_name: str | None = Field(default=None, max_length=200)
    card_number: str | None = Field(default=None, max_length=50)
    foil: bool = False
    language: SubmissionLanguage = SubmissionLanguage.en
    # The card is coming by post. Needs a name -- the operator matches the
    # physical card by it -- and is exempt from the open-draft cap.
    mail_in: bool = False

    @field_validator("card_name", mode="before")
    @classmethod
    def _blank_name_is_none(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def _mail_in_needs_a_name(self) -> "SubmissionCreate":
        if self.mail_in and not self.card_name:
            raise ValueError("A card sent by post needs a name, so it can be matched when it arrives.")
        return self
```

In `CardOut` change `card_name: str` to `card_name: str | None`. In `SubmissionDetail`, after the `charged` field from Task 2, add `mail_in: bool = False`.

- [ ] **Step 4: Settings** — in `backend/zgrader/config.py`, after `contact_message_retention_days`:

```python
    # How many photo checks one account may have started but not yet had
    # analysed. A draft costs nothing until analysis scores it, so without a
    # cap an account could park unlimited photos on this box for free.
    # Mail-in submissions and operators are exempt.
    max_open_drafts: int = 3

    # How long an untouched, never-analysed photo draft is kept before the
    # worker deletes it and its photos. "Untouched" is the later of the
    # submission's and its newest photo's updated_at. 0 keeps them forever.
    draft_retention_days: int = 7
```

In `docker-compose.yml`, in the `&backend-env` block directly after the `ZGRADER_CONTACT_MESSAGE_RETENTION_DAYS` line:

```yaml
      # How many photo checks an account may have started but not yet had
      # analysed. Drafts cost nothing until scored, so this is what stops
      # them being used as free photo storage.
      ZGRADER_MAX_OPEN_DRAFTS: ${ZGRADER_MAX_OPEN_DRAFTS:-3}
      # Days an untouched, never-analysed photo draft is kept before the
      # worker deletes it and its photos. 0 keeps them indefinitely.
      ZGRADER_DRAFT_RETENTION_DAYS: ${ZGRADER_DRAFT_RETENTION_DAYS:-7}
```

- [ ] **Step 5: Router** — in `backend/zgrader/api/routers/submissions.py` add `from zgrader.models.submission import PRE_ANALYSIS_STATUSES` beside the `submission_code_seq` import. In `create_submission`, after the quota check:

```python
    # Drafts are free until analysis scores them, so they need a ceiling of
    # their own. Mail-in submissions are waiting on the post, not on the
    # customer, and operators create on others' behalf.
    if not payload.mail_in and user.role != UserRole.operator:
        open_drafts = (
            db.query(Submission)
            .filter(
                Submission.user_id == user.id,
                Submission.mail_in.is_(False),
                Submission.charged_at.is_(None),
                Submission.status.in_(PRE_ANALYSIS_STATUSES),
            )
            .count()
        )
        if open_drafts >= config.max_open_drafts:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {
                    "message": (
                        f"You have {open_drafts} unfinished checks. "
                        "Finish or delete one to start another."
                    ),
                    "code": "too_many_drafts",
                },
            )
```

Pass `mail_in=payload.mail_in` to the `Submission(...)` constructor, and replace the two lines that send the received email with:

```python
    # Only a mail-in is a submission the customer is waiting on us for; the
    # email carries the reference to put in the package. A photo draft is
    # created silently by its first upload and may never be finished.
    if submission.mail_in:
        settings = db.query(Settings).first()
        send_submission_received(user, submission, settings)
```

- [ ] **Step 6: The email wiring test** — in `backend/tests/test_email.py` replace `test_creating_a_submission_sends_a_received_email` with:

```python
def test_a_photo_draft_sends_no_received_email():
    from fastapi.testclient import TestClient

    from zgrader.api.main import app

    client = TestClient(app)
    token = register_and_verify(client, "emailwire1@example.com")

    with patch("zgrader.api.routers.submissions.send_submission_received") as mock_send:
        resp = client.post("/submissions", json={"game": "Pokemon"}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 201
        mock_send.assert_not_called()


def test_a_mail_in_submission_sends_a_received_email():
    from fastapi.testclient import TestClient

    from zgrader.api.main import app

    client = TestClient(app)
    token = register_and_verify(client, "emailwire1b@example.com")

    with patch("zgrader.api.routers.submissions.send_submission_received") as mock_send:
        resp = client.post(
            "/submissions",
            json={"game": "Pokemon", "card_name": "Wired Card", "mail_in": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        mock_send.assert_called_once()
```

- [ ] **Step 7: Run the tests**

Run: `.venv/Scripts/python -m pytest tests/test_submission_drafts.py tests/test_email.py tests/test_compose_env_coverage.py tests/test_api_submissions.py -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/zgrader/schemas/submission.py backend/zgrader/api/routers/submissions.py backend/zgrader/config.py docker-compose.yml backend/tests/test_submission_drafts.py backend/tests/test_email.py
git commit -m "Make the card name optional, add mail-in, cap open photo drafts"
```

---

### Task 5: `PATCH /submissions/{code}/card`

**Files:**
- Modify: `backend/zgrader/schemas/submission.py`, `backend/zgrader/api/routers/submissions.py`
- Create: `backend/tests/test_card_update.py`

**Interfaces:**
- Produces: `CardUpdate` schema; `PATCH /submissions/{code}/card` returning `SubmissionDetail`. The frontend's `api.updateCard` (Task 7) sends `{card_name?, set_name?, card_number?, foil?}`, with `null` clearing a label.

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_card_update.py`:

```python
"""Card details are labels the customer can change at any time -- except foil,
which changes the analysis (assessment.CARD_IS_FOIL) and is therefore locked
once the card has been analysed."""

from zgrader.analysis import pipeline

from tests import checkflow_helpers as h


def _patch(token, code, body):
    return h.client.patch(f"/submissions/{code}/card", json=body, headers=h.headers(token))


def test_labels_can_be_set_and_cleared(db_session):
    token = h.login("card-labels@example.com")
    code = h.create_code(token, set_name="Base")

    resp = _patch(token, code, {"card_name": " Pikachu ", "set_name": None, "card_number": "58"})

    assert resp.status_code == 200
    card = resp.json()["card"]
    assert card["card_name"] == "Pikachu"
    assert card["set_name"] is None
    assert card["card_number"] == "58"


def test_omitted_fields_are_left_alone(db_session):
    token = h.login("card-omitted@example.com")
    code = h.create_code(token, card_name="Pikachu", set_name="Base")
    card = _patch(token, code, {"card_number": "58"}).json()["card"]
    assert card["card_name"] == "Pikachu"
    assert card["set_name"] == "Base"


def test_foil_can_change_before_analysis(db_session):
    token = h.login("card-foil-before@example.com")
    code = h.create_code(token)
    assert _patch(token, code, {"foil": True}).json()["card"]["foil"] is True


def test_foil_is_locked_after_analysis(db_session, sample_scan_paths, monkeypatch):
    token = h.login("card-foil-after@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])
    monkeypatch.setattr(pipeline, "run_analysis", h.fake_analysis(9.0))
    h.confirm(token, code, "front")

    assert _patch(token, code, {"foil": True}).status_code == 409
    # Sending the value it already has is not a change, and names still edit.
    assert _patch(token, code, {"foil": False, "card_name": "Later"}).status_code == 200


def test_unknown_fields_are_refused(db_session):
    token = h.login("card-extra@example.com")
    code = h.create_code(token)
    assert _patch(token, code, {"game": "Magic"}).status_code == 422


def test_an_overlong_name_is_a_422(db_session):
    token = h.login("card-long@example.com")
    code = h.create_code(token)
    assert _patch(token, code, {"card_name": "x" * 201}).status_code == 422


def test_someone_elses_card_is_403(db_session):
    owner = h.login("card-owner@example.com")
    code = h.create_code(owner)
    other = h.login("card-other@example.com")
    assert _patch(other, code, {"card_name": "Mine now"}).status_code == 403
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_card_update.py -v`
Expected: FAIL — 405 Method Not Allowed.

- [ ] **Step 3: Schema** — append to `backend/zgrader/schemas/submission.py`:

```python
class CardUpdate(BaseModel):
    """Edits to a submission's card. Omitted fields are left alone; `null`
    clears a label. Widths mirror models/card.py, as SubmissionCreate's do."""

    model_config = ConfigDict(extra="forbid")

    card_name: str | None = Field(default=None, max_length=200)
    set_name: str | None = Field(default=None, max_length=200)
    card_number: str | None = Field(default=None, max_length=50)
    foil: bool | None = None
```

- [ ] **Step 4: Endpoint** — in `backend/zgrader/api/routers/submissions.py` import `CardUpdate` in the schemas import block, add `_card_update_limit = rate_limit("card_update", limit=60, window_seconds=3600)` beside `_submission_adjust_limit`, and add after `upload_scan`:

```python
@router.patch(
    "/{code}/card", response_model=SubmissionDetail, dependencies=[Depends(_card_update_limit)]
)
def update_card(
    code: str,
    payload: CardUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Submission:
    """Name, set and number are labels -- nothing measured depends on them --
    so they edit in any status. Foil is part of the analysis
    (assessment.CARD_IS_FOIL), so it is locked once analysis has run: changing
    it afterwards would put a stale assessment beside a new declaration."""
    submission = _get_owned_submission(code, user, db)
    card = submission.card
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This submission has no card")

    fields = payload.model_fields_set
    if (
        "foil" in fields
        and payload.foil is not None
        and payload.foil != card.foil
        and submission.status not in PRE_ANALYSIS_STATUSES
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Foil can only be changed before the card is analysed -- it changes the result.",
        )

    for name in ("card_name", "set_name", "card_number"):
        if name in fields:
            value = getattr(payload, name)
            setattr(card, name, value.strip() or None if isinstance(value, str) else None)
    if "foil" in fields and payload.foil is not None:
        card.foil = payload.foil

    db.commit()
    db.refresh(submission)
    return submission
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python -m pytest tests/test_card_update.py tests/test_rate_limit_coverage.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/zgrader/schemas/submission.py backend/zgrader/api/routers/submissions.py backend/tests/test_card_update.py
git commit -m "Let customers edit card details; lock foil once analysed"
```

---

### Task 6: Sweep stale photo drafts

**Files:**
- Modify: `backend/zgrader/worker/main.py`
- Create: `backend/tests/test_stale_draft_sweep.py`

**Interfaces:**
- Consumes: `config.draft_retention_days` (Task 4), `PRE_ANALYSIS_STATUSES` (Task 1), `purge_submission_files` (`zgrader.storage`).
- Produces: `purge_stale_drafts(db: Session) -> int` in `zgrader.worker.main`.

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_stale_draft_sweep.py`:

```python
"""Never-analysed photo drafts are deleted after a week untouched, photos and
all. Mail-in, charged, and already-analysed submissions are never touched."""

import datetime
from pathlib import Path

from sqlalchemy import update

from zgrader.config import config
from zgrader.models import ScanImage, Submission, SubmissionStatus
from zgrader.worker import main as worker_main

from tests import checkflow_helpers as h

OLD = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=8)


def _draft(db_session, token, sample_scan_paths, **fields) -> str:
    code = h.create_code(token, **fields)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])
    return code


def _age(db_session, code, *, submission=True, scans=True) -> None:
    row = db_session.query(Submission).filter(Submission.submission_code == code).one()
    if submission:
        db_session.execute(update(Submission).where(Submission.id == row.id).values(updated_at=OLD))
    if scans:
        db_session.execute(update(ScanImage).where(ScanImage.submission_id == row.id).values(updated_at=OLD))
    db_session.commit()


def _exists(db_session, code) -> bool:
    db_session.expire_all()
    return db_session.query(Submission).filter(Submission.submission_code == code).count() == 1


def test_a_stale_draft_and_its_photos_are_removed(db_session, sample_scan_paths):
    token = h.login("sweep-stale@example.com")
    code = _draft(db_session, token, sample_scan_paths)
    _age(db_session, code)

    assert worker_main.purge_stale_drafts(db_session) == 1
    assert not _exists(db_session, code)
    assert not (Path(config.scans_dir) / code).exists()


def test_a_recent_photo_keeps_the_draft(db_session, sample_scan_paths):
    """Uploading writes a ScanImage, not the submission row -- keying on the
    submission alone would sweep a draft photographed yesterday."""
    token = h.login("sweep-recent-photo@example.com")
    code = _draft(db_session, token, sample_scan_paths)
    _age(db_session, code, scans=False)

    assert worker_main.purge_stale_drafts(db_session) == 0
    assert _exists(db_session, code)


def test_mail_in_charged_and_analysed_rows_are_kept(db_session, sample_scan_paths):
    token = h.login("sweep-keep@example.com")
    mail_in = h.create_code(token, mail_in=True, card_name="Posted")
    charged = _draft(db_session, token, sample_scan_paths)
    analysed = _draft(db_session, token, sample_scan_paths)
    for code in (mail_in, charged, analysed):
        _age(db_session, code)
    db_session.execute(
        update(Submission)
        .where(Submission.submission_code == charged)
        .values(charged_at=OLD, updated_at=OLD)
    )
    db_session.execute(
        update(Submission)
        .where(Submission.submission_code == analysed)
        .values(status=SubmissionStatus.draft_ready, updated_at=OLD)
    )
    db_session.commit()

    assert worker_main.purge_stale_drafts(db_session) == 0
    for code in (mail_in, charged, analysed):
        assert _exists(db_session, code)


def test_a_failed_file_purge_keeps_the_row_for_the_next_pass(db_session, sample_scan_paths, monkeypatch):
    """The row names the directory. Delete it first and a failed purge leaves
    photos nothing can find."""
    token = h.login("sweep-purge-fails@example.com")
    code = _draft(db_session, token, sample_scan_paths)
    _age(db_session, code)

    def refuse(code):
        raise PermissionError("read-only")

    monkeypatch.setattr(worker_main, "purge_submission_files", refuse)

    assert worker_main.purge_stale_drafts(db_session) == 0
    assert _exists(db_session, code)


def test_zero_disables_the_sweep(db_session, sample_scan_paths, monkeypatch):
    monkeypatch.setattr(config, "draft_retention_days", 0)
    token = h.login("sweep-disabled@example.com")
    code = _draft(db_session, token, sample_scan_paths)
    _age(db_session, code)

    assert worker_main.purge_stale_drafts(db_session) == 0
    assert _exists(db_session, code)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_stale_draft_sweep.py -v`
Expected: FAIL — `AttributeError: module 'zgrader.worker.main' has no attribute 'purge_stale_drafts'`.

- [ ] **Step 3: Implement** — in `backend/zgrader/worker/main.py` add imports:

```python
from sqlalchemy import func, select

from zgrader.models import AuditLog, ContactMessage, ScanImage, Submission, SubmissionStatus
from zgrader.models.submission import PRE_ANALYSIS_STATUSES
from zgrader.storage import purge_submission_files
```

(replacing the existing `from zgrader.models import ContactMessage, Submission, SubmissionStatus`), and after `purge_expired_contact_messages`:

```python
def purge_stale_drafts(db: Session) -> int:
    """Delete photo drafts nobody has touched for `draft_retention_days`.

    A draft costs nothing until analysis scores it, so an abandoned one would
    otherwise keep a customer's photograph on this box forever for no reason.
    Mail-in submissions (the card is in the post), charged ones and anything
    already analysed are never touched.

    "Touched" is the later of the submission's and its newest photo's
    updated_at: an upload writes a ScanImage, not the submission row.

    Files go before the row, which names their directory -- a purge that
    fails after the row is gone leaves photos nothing can find. A failed
    purge keeps the row for the next pass.
    """
    days = config.draft_retention_days
    if days <= 0:
        return 0
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    newest_photo = (
        select(func.max(ScanImage.updated_at))
        .where(ScanImage.submission_id == Submission.id)
        .scalar_subquery()
    )
    last_touched = func.greatest(Submission.updated_at, func.coalesce(newest_photo, Submission.updated_at))
    stale = (
        db.query(Submission)
        .filter(
            Submission.charged_at.is_(None),
            Submission.mail_in.is_(False),
            Submission.status.in_(PRE_ANALYSIS_STATUSES),
            last_touched < cutoff,
        )
        .all()
    )

    removed = 0
    for submission in stale:
        code = submission.submission_code
        try:
            purge_submission_files(code)
        except OSError:
            logger.warning("could not remove files for stale draft %s; kept for the next pass", code, exc_info=True)
            continue
        db.query(AuditLog).filter(AuditLog.submission_id == submission.id).update(
            {AuditLog.submission_id: None}, synchronize_session=False
        )
        db.add(
            AuditLog(
                submission_id=None,
                user_id=submission.user_id,
                action="draft_expired",
                detail={"deleted_code": code},
            )
        )
        db.delete(submission)
        db.commit()
        removed += 1
    return removed
```

and in `_sweep_retention`, after the contact-message block inside the `try`:

```python
        drafts = purge_stale_drafts(db)
        if drafts:
            logger.info(
                "purged %d photo draft(s) untouched for %d days", drafts, config.draft_retention_days
            )
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python -m pytest tests/test_stale_draft_sweep.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/zgrader/worker/main.py backend/tests/test_stale_draft_sweep.py
git commit -m "Sweep photo drafts left untouched for a week, photos first"
```

---

### Task 7: Summary payload, and a card with no name everywhere it is read

**Files:**
- Modify: `backend/zgrader/schemas/submission.py`, `backend/zgrader/api/routers/submissions.py`, `backend/zgrader/reports/builder.py`, `backend/zgrader/reports/strings.py`, `backend/zgrader/schemas/public_report.py`
- Create: `backend/tests/test_submission_summary.py`; Modify: `backend/tests/test_public_share.py`

**Interfaces:**
- Produces: `SubmissionSummary` fields `card_name: str | None`, `game: str | None`, `mail_in: bool`, `charged: bool`, `scores: dict[str, float | None]` (keys `centering|corners|edges|surface`, present only once analysed). `REPORT_STRINGS[lang]["untitled_card"]`.

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_submission_summary.py`:

```python
"""The dashboard list says which card each row is and how it scored, and
costs the same number of queries however many rows there are."""

from sqlalchemy import event

from zgrader.analysis import pipeline
from zgrader.auth.security import hash_password
from zgrader.db import engine
from zgrader.models import Card, Submission, SubmissionLanguage, SubmissionStatus, User
from zgrader.models.settings import get_or_create_settings
from zgrader.reports.builder import build_report_context

from tests import checkflow_helpers as h


def _rows(token) -> dict:
    resp = h.client.get("/submissions", headers=h.headers(token))
    assert resp.status_code == 200
    return {row["submission_code"]: row for row in resp.json()}


def test_the_list_carries_name_game_scores_and_charge(db_session, sample_scan_paths, monkeypatch):
    h.set_free_limit(db_session, 5)
    token = h.login("summary-fields@example.com")
    named = h.create_code(token, card_name="Pikachu")
    unnamed = h.create_code(token)
    h.upload(token, named, "front", sample_scan_paths["pokemon_front"])
    monkeypatch.setattr(pipeline, "run_analysis", h.fake_analysis(9.0))
    h.confirm(token, named, "front")

    rows = _rows(token)

    assert rows[named]["card_name"] == "Pikachu"
    assert rows[named]["game"] == "Pokemon"
    assert rows[named]["charged"] is True
    assert rows[named]["scores"] == {"centering": 9.0, "corners": 9.0, "edges": 9.0, "surface": 9.0}
    assert rows[unnamed]["card_name"] is None
    assert rows[unnamed]["charged"] is False
    assert rows[unnamed]["mail_in"] is False
    assert rows[unnamed]["scores"] == {}


def test_an_unmeasurable_category_is_null_not_zero(db_session, sample_scan_paths, monkeypatch):
    token = h.login("summary-null@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])
    monkeypatch.setattr(pipeline, "run_analysis", h.fake_analysis(None))
    h.confirm(token, code, "front")

    assert set(_rows(token)[code]["scores"].values()) == {None}


def test_listing_costs_the_same_queries_for_one_row_as_for_three(db_session):
    token = h.login("summary-queries@example.com")
    h.create_code(token)

    def count() -> int:
        statements: list[str] = []

        def listener(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", listener)
        try:
            _rows(token)
        finally:
            event.remove(engine, "before_cursor_execute", listener)
        return len(statements)

    one = count()
    h.create_code(token)
    h.create_code(token)
    assert count() == one


def test_the_report_names_an_untitled_card_in_its_language(db_session):
    user = User(email="summary-pdf@example.com", hashed_password=hash_password("hunter2pass"), is_verified=True)
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code="SUB-90903",
        user_id=user.id,
        status=SubmissionStatus.draft_ready,
        language=SubmissionLanguage.es,
    )
    db_session.add(submission)
    db_session.flush()
    db_session.add(Card(submission_id=submission.id, game="Pokemon", card_name=None))
    db_session.flush()
    db_session.refresh(submission)

    context = build_report_context(submission, get_or_create_settings(db_session))

    assert context["card"]["card_name"] == "Carta sin nombre"
```

and append to `backend/tests/test_public_share.py`:

```python
def test_a_card_with_no_name_still_renders_publicly(shared):
    """PublicCardOut is built field by field, so a required name would turn a
    nameless card into a 500 on the one page a buyer sees."""
    with SessionLocal() as db:
        submission = db.query(Submission).filter(Submission.submission_code == shared["code"]).one()
        submission.card.card_name = None
        db.commit()

    resp = client.get(f"/public/reports/{shared['token']}")

    assert resp.status_code == 200, resp.text
    assert resp.json()["card"]["card_name"] is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_submission_summary.py "tests/test_public_share.py::test_a_card_with_no_name_still_renders_publicly" -v`
Expected: FAIL — `KeyError: 'card_name'` on the list, `None` for the PDF name, a validation error on the public page.

- [ ] **Step 3: Summary** — in `backend/zgrader/schemas/submission.py` replace `SubmissionSummary` with:

```python
class SubmissionSummary(BaseModel):
    """One row of the customer's list: enough to tell ten cards apart."""

    submission_code: str
    status: SubmissionStatus
    created_at: datetime.datetime
    card_name: str | None = None
    game: str | None = None
    mail_in: bool = False
    charged: bool = False
    # The four combined category scores once analysed; None = unmeasurable,
    # never zero. Empty before any analysis.
    scores: dict[str, float | None] = {}
```

In `backend/zgrader/api/routers/submissions.py` add `from sqlalchemy.orm import Session, selectinload` (replacing the plain `Session` import), add `AnalysisSide` to the `zgrader.models` import list, and replace `list_submissions` with:

```python
def _summary(submission: Submission) -> SubmissionSummary:
    card = submission.card
    return SubmissionSummary(
        submission_code=submission.submission_code,
        status=submission.status,
        created_at=submission.created_at,
        card_name=card.card_name if card else None,
        game=card.game if card else None,
        mail_in=submission.mail_in,
        charged=submission.charged,
        scores={
            str(getattr(result.category, "value", result.category)): (
                float(result.raw_score) if result.raw_score is not None else None
            )
            for result in submission.analysis_results
            if result.side == AnalysisSide.combined
        },
    )


@router.get(
    "", response_model=list[SubmissionSummary], dependencies=[Depends(_submission_read_limit)]
)
def list_submissions(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[SubmissionSummary]:
    # selectinload: one query per relationship however many rows, rather
    # than one per row -- tests/test_submission_summary.py counts them.
    query = db.query(Submission).options(
        selectinload(Submission.card), selectinload(Submission.analysis_results)
    )
    if user.role != UserRole.operator:
        query = query.filter(Submission.user_id == user.id)
    return [_summary(s) for s in query.order_by(Submission.created_at.desc()).all()]
```

- [ ] **Step 4: The PDF** — in `backend/zgrader/reports/strings.py` add `"untitled_card": "Untitled card",` after `"foil_suffix"` in the `"en"` dict and `"untitled_card": "Carta sin nombre",` after `"foil_suffix"` in the `"es"` dict. In `backend/zgrader/reports/builder.py` change the `"card_name"` entry of the returned `"card"` dict to:

```python
            # The photo-first page makes the name optional; a PDF must never
            # print "None" where a card's name belongs.
            "card_name": (card.card_name if card else None) or REPORT_STRINGS[language]["untitled_card"],
```

- [ ] **Step 5: The public page** — in `backend/zgrader/schemas/public_report.py` change `PublicCardOut.card_name: str` to `card_name: str | None`.

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python -m pytest tests/test_submission_summary.py tests/test_public_share.py tests/test_api_submissions.py tests/test_unmeasurable.py -v`
Expected: all PASS, `test_public_payload_key_allowlist` included (types changed, keys did not).

- [ ] **Step 7: Full backend suite** — the backend is complete after this task.

Run: `.venv/Scripts/python -m pytest -q > ../../fcf-suite.txt 2>&1; echo exit=$?`
Expected: `exit=0`; the tail of `fcf-suite.txt` shows the Task 0 baseline count plus the new tests, no failures. Delete the file afterwards.

- [ ] **Step 8: Commit**

```bash
git add backend/zgrader/schemas/submission.py backend/zgrader/api/routers/submissions.py backend/zgrader/reports/builder.py backend/zgrader/reports/strings.py backend/zgrader/schemas/public_report.py backend/tests/test_submission_summary.py backend/tests/test_public_share.py
git commit -m "List card names and scores; never print None for an unnamed card"
```

---

### Task 8: Frontend foundation — API client, copy, status words, countdown, polling

**Files:**
- Modify: `frontend/lib/api.ts`, `frontend/lib/i18n/en.ts`, `frontend/lib/i18n/es.ts`, `frontend/components/StatusBadge.tsx`, `frontend/components/QuotaChip.tsx`
- Create: `frontend/lib/countdown.ts`, `frontend/lib/use-submission-poll.ts`

**Interfaces:**
- Consumes: the Task 2–7 payloads.
- Produces: `ApiError.detail: unknown`; `errorCode(err: unknown): string | null`; `Card.card_name: string | null`; `SubmissionSummary` / `SubmissionDetail` new fields; `SubmissionCreate.card_name?: string | null`, `mail_in?: boolean`; `CardUpdate`; `updateCard(token, code, payload): Promise<SubmissionDetail>`; `formatRemaining(iso, now, labels)`; `useSubmissionPoll(active: boolean, poll: () => Promise<void>): boolean` (returns "timed out"); `StatusBadge` props `audience?: "customer" | "operator"`, `mailIn?: boolean`, `charged?: boolean`; dictionary blocks `customerStatus`, `checkFlow`, `cropAdjust.handleLabel`, `cropAdjust.keyboardHint`, `dashboard.notCharged|continue|scoreAbbrev`.

This task only **adds and changes** copy. Keys that later tasks stop using are deleted in those tasks, so `tsc` stays green after every commit.

- [ ] **Step 1: `frontend/lib/api.ts`** — replace the `ApiError` class with:

```ts
export class ApiError extends Error {
  status: number;
  /** The response's parsed `detail`. Structured refusals -- the 402 quota
   *  payload, the 409 `too_many_drafts` -- carry fields here the UI can act on
   *  rather than a sentence it can only show. */
  detail: unknown;
  constructor(status: number, message: string, detail: unknown = null) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

/** The machine-readable `code` of a structured refusal, if it has one. */
export function errorCode(err: unknown): string | null {
  if (!(err instanceof ApiError)) return null;
  const detail = err.detail as { code?: unknown } | null;
  return detail && typeof detail.code === "string" ? detail.code : null;
}
```

In `describeDetail`, insert before `if (!Array.isArray(detail)) return null;`:

```ts
  // A structured refusal ({message, ...}) -- the 402 and 409 bodies. Without
  // this the customer saw the bare status text, "Payment Required".
  if (typeof detail === "object" && detail !== null && !Array.isArray(detail)) {
    const message = (detail as { message?: unknown }).message;
    return typeof message === "string" ? message : null;
  }
```

In `request`, keep the parsed detail and pass it on:

```ts
  if (!res.ok) {
    let message = res.statusText;
    let detail: unknown = null;
    try {
      const body = await res.json();
      detail = body.detail ?? null;
      message = describeDetail(detail) ?? message;
    } catch {
      // response wasn't JSON -- fall back to statusText
    }
    throw new ApiError(res.status, message, detail);
  }
```

Change `Card.card_name` to `card_name: string | null;`. Replace `SubmissionSummary` with:

```ts
export interface SubmissionSummary {
  submission_code: string;
  status: SubmissionStatus;
  created_at: string;
  card_name: string | null;
  game: string | null;
  mail_in: boolean;
  charged: boolean;
  /** Combined score per category once analysed; null = not measurable. */
  scores: Partial<Record<"centering" | "corners" | "edges" | "surface", number | null>>;
}
```

In `SubmissionDetail`, after `auto_publish`, add:

```ts
  /** Whether a check has been spent: true once an analysis first scored it. */
  charged: boolean;
  /** The card is coming by post rather than as a photo. */
  mail_in: boolean;
```

Replace `SubmissionCreate` with:

```ts
export interface SubmissionCreate {
  game: string;
  card_name?: string | null;
  set_name?: string;
  card_number?: string;
  foil?: boolean;
  language?: "en" | "es";
  mail_in?: boolean;
}

/** Omitted fields are left alone; null clears a label. Foil is refused (409)
 *  once the card has been analysed. */
export interface CardUpdate {
  card_name?: string | null;
  set_name?: string | null;
  card_number?: string | null;
  foil?: boolean;
}
```

and after `createSubmission`:

```ts
export async function updateCard(token: string, code: string, payload: CardUpdate): Promise<SubmissionDetail> {
  return request(`/submissions/${code}/card`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
```

- [ ] **Step 2: `frontend/lib/countdown.ts`** — move `formatRemaining` out of `QuotaChip.tsx` unchanged:

```ts
/**
 * Formats the gap to `iso` as a coarse countdown: days and hours, or hours and
 * minutes inside a day. Shared by the header chip and the out-of-checks panel
 * so both say the same thing.
 *
 * Deliberately not second-by-second. The reset is up to a week away, so a
 * ticking seconds display would be noise that also forces a re-render every
 * second on every page.
 */
export function formatRemaining(
  iso: string,
  now: number,
  labels: { d: string; h: string; m: string }
): string | null {
  const ms = new Date(iso).getTime() - now;
  if (!Number.isFinite(ms) || ms <= 0) return null;

  const minutes = Math.floor(ms / 60000);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days >= 1) return `${days}${labels.d} ${hours % 24}${labels.h}`;
  if (hours >= 1) return `${hours}${labels.h} ${minutes % 60}${labels.m}`;
  return `${Math.max(1, minutes)}${labels.m}`;
}
```

In `QuotaChip.tsx` delete the local function and its comment, add `import { formatRemaining } from "@/lib/countdown";`, and change `href="/services"` to `href="/pricing"` (`/services` still describes paid tiers as coming soon).

- [ ] **Step 3: `frontend/lib/use-submission-poll.ts`**:

```ts
"use client";

import { useEffect, useRef, useState } from "react";

const FAST_MS = 3_000;
const SLOW_MS = 10_000;
const FAST_FOR_MS = 60_000;
const GIVE_UP_MS = 600_000;

/**
 * Re-reads a submission while `active` is true, so a page that lands
 * mid-analysis finishes on its own instead of waiting for a reload.
 *
 * Every 3s for the first minute, then every 10s; paused while the tab is
 * hidden and resumed the moment it is shown; abandoned after 10 minutes,
 * when the caller shows "we'll email you". Worst case is about a third of
 * the submission_read allowance (300 per 5 minutes per address).
 *
 * Returns whether it gave up.
 */
export function useSubmissionPoll(active: boolean, poll: () => Promise<void>): boolean {
  const [timedOut, setTimedOut] = useState(false);
  const pollRef = useRef(poll);

  useEffect(() => {
    pollRef.current = poll;
  });

  useEffect(() => {
    if (!active) return;
    const started = Date.now();
    let timer: number | undefined;
    let cancelled = false;

    const schedule = () => {
      const elapsed = Date.now() - started;
      if (elapsed >= GIVE_UP_MS) {
        setTimedOut(true);
        return;
      }
      timer = window.setTimeout(tick, elapsed < FAST_FOR_MS ? FAST_MS : SLOW_MS);
    };
    const tick = async () => {
      if (cancelled || document.hidden) return; // resumed by visibilitychange
      try {
        await pollRef.current();
      } catch {
        // A failed read is retried on the next tick; nothing to show.
      }
      if (!cancelled) schedule();
    };
    const onVisibility = () => {
      if (!document.hidden && !cancelled) {
        window.clearTimeout(timer);
        void tick();
      }
    };

    document.addEventListener("visibilitychange", onVisibility);
    schedule();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [active]);

  return timedOut;
}
```

- [ ] **Step 4: `frontend/components/StatusBadge.tsx`** — replace the file with:

```tsx
import { Chip } from "@heroui/react";
import type { SubmissionStatus } from "@/lib/api";
import { getDictionary, type Locale } from "@/lib/i18n/context";

const STATUS_COLOR: Record<SubmissionStatus, "default" | "accent" | "warning" | "success" | "danger"> = {
  created: "default",
  awaiting_scans: "default",
  processing: "accent",
  draft_ready: "warning",
  approved: "accent",
  published: "success",
  error: "danger",
};

/**
 * The operator's words name pipeline states; a customer needs to know what is
 * happening to their card. Same colours, different vocabulary.
 */
export function customerStatusLabel(
  status: SubmissionStatus,
  flags: { mailIn: boolean; charged: boolean },
  locale: Locale
): string {
  const t = getDictionary(locale).customerStatus;
  switch (status) {
    case "created":
    case "awaiting_scans":
      // An uncharged photo draft is the customer's own unfinished work. A
      // mail-in -- or a submission charged under the old create-time rule --
      // is waiting on the post.
      return flags.mailIn || flags.charged ? t.awaitingCard : t.draft;
    case "processing":
      return t.analysing;
    case "draft_ready":
    case "approved":
      return t.inReview;
    case "published":
      return t.reportReady;
    case "error":
      return t.couldNotAnalyse;
  }
}

export default function StatusBadge({
  status,
  locale = "en",
  audience = "operator",
  mailIn = false,
  charged = false,
}: {
  status: SubmissionStatus;
  locale?: Locale;
  /** "operator" keeps the admin's pipeline vocabulary, and is the default so
   *  admin call sites need no change. */
  audience?: "customer" | "operator";
  mailIn?: boolean;
  charged?: boolean;
}) {
  const label =
    audience === "customer"
      ? customerStatusLabel(status, { mailIn, charged }, locale)
      : getDictionary(locale).status[status];
  return (
    <Chip color={STATUS_COLOR[status]} variant="soft" size="sm">
      {label}
    </Chip>
  );
}
```

- [ ] **Step 5: English copy** — in `frontend/lib/i18n/en.ts`:

After the `status` block add:

```ts
  // What a customer sees for a status. The operator keeps `status` above.
  customerStatus: {
    draft: "Draft",
    awaitingCard: "Awaiting your card",
    analysing: "Analysing",
    inReview: "Results ready · in review",
    reportReady: "Report ready",
    couldNotAnalyse: "Couldn't analyse",
  },
```

In `dashboard` change `subtitle` to `"Every card you've checked, and where each one stands."`, `newSubmission` to `"Check a card"`, `emptyDescription` to `"Every card you check shows up here."`, and add:

```ts
    notCharged: "Not charged",
    continue: "Continue",
    // Beside each score in the list; the full category name is read to
    // screen readers from `category`.
    scoreAbbrev: { centering: "Cen", corners: "Cor", edges: "Edg", surface: "Sur" },
```

In `submissionDetail` change `shareUnavailable` to `"The share link unlocks once we've checked the report — you'll get an email."`.

In `cropAdjust` add:

```ts
    // Named by where the handle sits, worked out on screen, not by the order
    // the points arrive in.
    handleLabel: {
      topLeft: "Top-left corner",
      topRight: "Top-right corner",
      bottomRight: "Bottom-right corner",
      bottomLeft: "Bottom-left corner",
    },
    keyboardHint: "Arrow keys move a selected corner; hold Shift for bigger steps.",
```

After the `cropAdjust` block add:

```ts
  // The photo-first check page (components/CheckFlow.tsx) and the states of a
  // submission around it (components/SubmissionView.tsx).
  checkFlow: {
    title: "Check a card",
    subtitle: "Choose the game, add a photo of the front, and we'll measure it.",
    // {count} comes from the quota, never from this copy.
    usesOneCheck: "Uses one check, only if we can score it. You have {count} left.",
    unverifiedTitle: "Confirm your email to run a check",
    unverifiedBody: "We sent a link to {email}. Open it, then come back here.",
    resend: "Resend the link",
    resent: "If that address needs confirming, a new link is on its way.",
    game: "Game",
    dimensionsUnverified: " (dimensions unverified)",
    takePhoto: "Take photo",
    choosePhoto: "Choose photo",
    foil: "Foil / holo",
    foilHint: "Tell us if it's foil or holo — glare on foil is treated more cautiously.",
    detailsSummary: "Card details (optional)",
    cardName: "Card name",
    setName: "Set",
    cardNumber: "Card number",
    analyse: "Analyse card",
    draftsFullTitle: "You have unfinished checks",
    draftsFullBody: "Finish or delete one of them to start another.",
    draftsFullLink: "Go to your submissions",
    mailInLink: "Sending us the card instead?",
    mailInTitle: "Send us the card",
    mailInBody: "Tell us which card it is. We'll email you a reference to put in the package.",
    mailInSubmit: "Create a mail-in submission",
    mailInCancel: "Use a photo instead",
    untitledCard: "Untitled card",
    addName: "Add name",
    editDetails: "Edit details",
    saveDetails: "Save",
    cancelEdit: "Cancel",
    detailsSaved: "Details saved.",
    detailsFailed: "Couldn't save the details.",
    refLabel: "Ref {code}",
    createFailed: "Couldn't start the check.",
    awaitingCardTitle: "Waiting for your card",
    awaitingCardBody: "Post the card with reference {code}. We'll email you when its report is ready.",
    backTitle: "Add the back for a full check",
    backBody: "The front is done. A photo of the back completes this check at no extra cost.",
    reviewTitle: "Your results are below",
    reviewBody: "We check every report before the PDF and share link unlock — you'll get an email.",
    stillWorking: "Still working — we'll email you when it's done.",
    errorTitle: "We couldn't analyse this photo",
    errorFree: "It didn't use a check.",
    errorTips:
      "Two things fix most failures: a plain background that contrasts with the card, and a crop traced tightly around it.",
    tryAnother: "Try another photo",
  },
```

- [ ] **Step 6: Spanish copy** — the same keys in `frontend/lib/i18n/es.ts`, in the same places:

```ts
  customerStatus: {
    draft: "Borrador",
    awaitingCard: "Esperando su carta",
    analysing: "Analizando",
    inReview: "Resultados listos · en revisión",
    reportReady: "Informe listo",
    couldNotAnalyse: "No se pudo analizar",
  },
```

`dashboard`: `subtitle: "Cada carta que ha analizado y en qué punto está."`, `newSubmission: "Analizar una carta"`, `emptyDescription: "Cada carta que analice aparecerá aquí."`, plus

```ts
    notCharged: "Sin cargo",
    continue: "Continuar",
    scoreAbbrev: { centering: "Cen", corners: "Esq", edges: "Bor", surface: "Sup" },
```

`submissionDetail.shareUnavailable: "El enlace para compartir se desbloquea cuando hayamos revisado el informe; recibirá un correo."`

`cropAdjust`:

```ts
    handleLabel: {
      topLeft: "Esquina superior izquierda",
      topRight: "Esquina superior derecha",
      bottomRight: "Esquina inferior derecha",
      bottomLeft: "Esquina inferior izquierda",
    },
    keyboardHint: "Las flechas mueven la esquina seleccionada; mantenga Mayús para pasos más grandes.",
```

```ts
  checkFlow: {
    title: "Analizar una carta",
    subtitle: "Elija el juego, añada una foto del frente y la mediremos.",
    usesOneCheck: "Usa un análisis, solo si podemos puntuarla. Le quedan {count}.",
    unverifiedTitle: "Confirme su correo para analizar una carta",
    unverifiedBody: "Enviamos un enlace a {email}. Ábralo y vuelva aquí.",
    resend: "Reenviar el enlace",
    resent: "Si esa dirección necesita confirmación, va de camino un enlace nuevo.",
    game: "Juego",
    dimensionsUnverified: " (dimensiones no verificadas)",
    takePhoto: "Hacer foto",
    choosePhoto: "Elegir foto",
    foil: "Foil / holográfica",
    foilHint: "Indíquenos si es foil u holográfica: los reflejos en el foil se tratan con más cautela.",
    detailsSummary: "Datos de la carta (opcional)",
    cardName: "Nombre de la carta",
    setName: "Edición",
    cardNumber: "Número de carta",
    analyse: "Analizar carta",
    draftsFullTitle: "Tiene análisis sin terminar",
    draftsFullBody: "Termine o elimine uno de ellos para empezar otro.",
    draftsFullLink: "Ir a sus envíos",
    mailInLink: "¿Prefiere enviarnos la carta?",
    mailInTitle: "Envíenos la carta",
    mailInBody: "Díganos qué carta es. Le enviaremos por correo una referencia para incluir en el paquete.",
    mailInSubmit: "Crear un envío por correo",
    mailInCancel: "Usar una foto",
    untitledCard: "Carta sin nombre",
    addName: "Añadir nombre",
    editDetails: "Editar datos",
    saveDetails: "Guardar",
    cancelEdit: "Cancelar",
    detailsSaved: "Datos guardados.",
    detailsFailed: "No se pudieron guardar los datos.",
    refLabel: "Ref. {code}",
    createFailed: "No se pudo iniciar el análisis.",
    awaitingCardTitle: "Esperando su carta",
    awaitingCardBody: "Envíe la carta con la referencia {code}. Le avisaremos por correo cuando su informe esté listo.",
    backTitle: "Añada el reverso para un análisis completo",
    backBody: "El frente ya está. Una foto del reverso completa este análisis sin coste adicional.",
    reviewTitle: "Sus resultados están abajo",
    reviewBody: "Revisamos cada informe antes de desbloquear el PDF y el enlace para compartir; recibirá un correo.",
    stillWorking: "Sigue en marcha; le avisaremos por correo cuando termine.",
    errorTitle: "No hemos podido analizar esta foto",
    errorFree: "No ha consumido ningún análisis.",
    errorTips:
      "Dos cosas resuelven la mayoría de los fallos: un fondo liso que contraste con la carta y un recorte ajustado a su contorno.",
    tryAnother: "Probar con otra foto",
  },
```

- [ ] **Step 7: Verify**

Run: `cd frontend && npx tsc --noEmit && npx eslint lib/api.ts lib/countdown.ts lib/use-submission-poll.ts components/StatusBadge.tsx components/QuotaChip.tsx`
Expected: no output. Then `git diff --stat lib/i18n` and open both files at the new blocks to confirm accented characters and em dashes survived the edit (AGENTS.md: tooling has mangled them before).

- [ ] **Step 8: Commit**

```bash
git add frontend/lib/api.ts frontend/lib/countdown.ts frontend/lib/use-submission-poll.ts frontend/lib/i18n/en.ts frontend/lib/i18n/es.ts frontend/components/StatusBadge.tsx frontend/components/QuotaChip.tsx
git commit -m "Frontend groundwork: structured API errors, customer status words, polling"
```

---

### Task 9: Crop editor — magnifier, keyboard handles, labelled rotate, extension points

**Files:**
- Modify (replace): `frontend/components/CropAdjustStep.tsx`

**Interfaces:**
- Consumes: `t.cropAdjust.handleLabel`, `t.cropAdjust.keyboardHint` (Task 8).
- Produces: `CropAdjustStep` props — unchanged `token`, `code`, `side`, `onConfirmed`, plus optional `confirmLabel?: string`, `beforeConfirm?: () => Promise<boolean>` (resolve `false` to stop; runs before the crop check), `onConfirmError?: (err: api.ApiError) => boolean` (return `true` when the caller has shown the refusal itself), `children?: ReactNode` (rendered between the editor and the confirm button). Existing callers passing only the original four props behave exactly as before.

- [ ] **Step 1: Replace the file** with:

```tsx
"use client";

import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import Button from "@/components/Button";
import Skeleton from "@/components/Skeleton";
import { toastError } from "@/lib/toast";
import { useTranslations } from "@/lib/i18n/context";
import * as api from "@/lib/api";

type NormPoint = [number, number];
type CornerKey = "topLeft" | "topRight" | "bottomRight" | "bottomLeft";

/** How far the touch magnifier enlarges the photo, and its diameter. */
const LOUPE_ZOOM = 3;
const LOUPE_PX = 120;
/** Gap between the finger and the magnifier, so the finger never covers it. */
const LOUPE_GAP_PX = 24;
/** Keyboard nudge as a fraction of the photo: fine, and with Shift held. */
const NUDGE = 0.005;
const NUDGE_LARGE = 0.02;

/** Where a drag is, in normalised photo space plus the photo's on-screen size. */
type Loupe = { x: number; y: number; width: number; height: number };

/** Names a handle by where it sits relative to the others, so the label is
 *  right whatever order the suggestion returned the points in. */
function cornerKey(point: NormPoint, centre: NormPoint): CornerKey {
  const top = point[1] < centre[1];
  const left = point[0] < centre[0];
  if (top) return left ? "topLeft" : "topRight";
  return left ? "bottomLeft" : "bottomRight";
}

export default function CropAdjustStep({
  token,
  code,
  side,
  onConfirmed,
  confirmLabel,
  beforeConfirm,
  onConfirmError,
  children,
}: {
  token: string;
  code: string;
  side: api.ScanSide;
  onConfirmed: (updated: api.SubmissionDetail) => void;
  /** Replaces "Confirm crop" -- the check page says "Analyse card". */
  confirmLabel?: string;
  /** Runs before the crop check. Resolve false to stop; the caller has
   *  already said why. */
  beforeConfirm?: () => Promise<boolean>;
  /** Return true when the caller has shown this refusal itself (the check
   *  page shows a 402 as a panel), so no toast follows. */
  onConfirmError?: (err: api.ApiError) => boolean;
  /** Between the editor and the confirm button: foil, card details. */
  children?: ReactNode;
}) {
  const t = useTranslations();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const dragIndex = useRef<number | null>(null);

  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [dims, setDims] = useState<{ width_px: number; height_px: number } | null>(null);
  const [points, setPoints] = useState<NormPoint[] | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [snapping, setSnapping] = useState(false);
  const [checking, setChecking] = useState(false);
  const [loupe, setLoupe] = useState<Loupe | null>(null);
  // Set when the crop check says the card's edges could not be found. Holding
  // the codes rather than a boolean lets the panel below reuse the same
  // wording the results page uses for the same condition.
  const [boundaryWarning, setBoundaryWarning] = useState<string[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    async function load() {
      try {
        const [blob, suggestion] = await Promise.all([
          api.fetchAuthedImage(token, api.rawScanUrl(code, side)),
          api.suggestCrop(token, code, side),
        ]);
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setPhotoUrl(objectUrl);
        setDims({ width_px: suggestion.width_px, height_px: suggestion.height_px });
        setPoints(
          suggestion.points.map(
            ([x, y]) => [x / suggestion.width_px, y / suggestion.height_px] as NormPoint
          )
        );
      } catch (err) {
        toastError(err instanceof api.ApiError ? err.message : t.cropAdjust.loadFailed);
      }
    }

    load();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, code, side]);

  function clientToNormalized(clientX: number, clientY: number): NormPoint {
    const rect = wrapperRef.current!.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (clientY - rect.top) / rect.height));
    return [x, y];
  }

  /** Touch only: a mouse pointer is a pixel wide and hides nothing, a finger
   *  hides exactly the corner being placed. */
  function showLoupe(event: ReactPointerEvent<HTMLButtonElement>, point: NormPoint) {
    if (event.pointerType !== "touch" || !wrapperRef.current) return;
    const rect = wrapperRef.current.getBoundingClientRect();
    setLoupe({ x: point[0], y: point[1], width: rect.width, height: rect.height });
  }

  function handlePointerDown(index: number, event: ReactPointerEvent<HTMLButtonElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragIndex.current = index;
    if (points) showLoupe(event, points[index]);
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLButtonElement>) {
    if (dragIndex.current === null) return;
    const next = clientToNormalized(event.clientX, event.clientY);
    const index = dragIndex.current;
    setPoints((prev) => {
      if (!prev) return prev;
      const updated = [...prev];
      updated[index] = next;
      return updated;
    });
    showLoupe(event, next);
  }

  function handlePointerUp(event: ReactPointerEvent<HTMLButtonElement>) {
    event.currentTarget.releasePointerCapture(event.pointerId);
    dragIndex.current = null;
    setLoupe(null);
  }

  /** The handles were pointer-only; arrow keys make them usable without one. */
  function handleKeyDown(index: number, event: ReactKeyboardEvent<HTMLButtonElement>) {
    const step = event.shiftKey ? NUDGE_LARGE : NUDGE;
    const moves: Record<string, NormPoint> = {
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
      ArrowUp: [0, -step],
      ArrowDown: [0, step],
    };
    const move = moves[event.key];
    if (!move) return;
    event.preventDefault();
    setPoints((prev) => {
      if (!prev) return prev;
      const updated = [...prev];
      const [x, y] = updated[index];
      updated[index] = [
        Math.min(1, Math.max(0, x + move[0])),
        Math.min(1, Math.max(0, y + move[1])),
      ];
      return updated;
    });
  }

  function toPixels(pts: NormPoint[]): api.CropPoint[] {
    return pts.map(([x, y]) => [x * dims!.width_px, y * dims!.height_px]);
  }

  // Rotate the 4 handles about their centroid in *pixel* space (rotating in
  // normalized 0..1 space would shear the angle by the image's aspect
  // ratio). Each nudge mutates the points, so it composes with dragging and
  // snapping and needs no backend change -- the existing points -> warp
  // pipeline straightens whatever quad we send.
  function nudgeRotate(degrees: number) {
    if (!dims) return;
    const rad = (degrees * Math.PI) / 180;
    const cos = Math.cos(rad);
    const sin = Math.sin(rad);
    setPoints((prev) => {
      if (!prev) return prev;
      const px = prev.map(([x, y]) => [x * dims.width_px, y * dims.height_px] as [number, number]);
      const cx = px.reduce((s, p) => s + p[0], 0) / px.length;
      const cy = px.reduce((s, p) => s + p[1], 0) / px.length;
      return px.map(([x, y]) => {
        const dx = x - cx;
        const dy = y - cy;
        const rx = cx + dx * cos - dy * sin;
        const ry = cy + dx * sin + dy * cos;
        return [
          Math.min(1, Math.max(0, rx / dims.width_px)),
          Math.min(1, Math.max(0, ry / dims.height_px)),
        ] as NormPoint;
      });
    });
  }

  async function handleSnap() {
    if (!points || !dims) return;
    setSnapping(true);
    try {
      const { points: snapped } = await api.snapCrop(token, code, side, toPixels(points));
      setPoints(snapped.map(([x, y]) => [x / dims.width_px, y / dims.height_px] as NormPoint));
    } catch (err) {
      toastError(err instanceof api.ApiError ? err.message : t.cropAdjust.snapFailed);
    } finally {
      setSnapping(false);
    }
  }

  /** Persist the crop and move on. Bypasses the check on purpose -- reached
   *  either because the check passed or because the customer chose to submit
   *  anyway. */
  async function submitCrop() {
    if (!points || !dims) return;
    setConfirming(true);
    try {
      const updated = await api.confirmCrop(token, code, side, toPixels(points));
      onConfirmed(updated);
    } catch (err) {
      if (err instanceof api.ApiError && onConfirmError?.(err)) {
        // Shown by the caller.
      } else if (err instanceof api.ApiError && err.status === 503) {
        // Two refusals here are capacity, not failure, and both are
        // recoverable by waiting -- so they get their own wording.
        toastError(t.cropAdjust.confirmBusy);
      } else if (err instanceof api.ApiError && err.status === 409) {
        toastError(t.cropAdjust.confirmAlreadyRunning);
      } else {
        toastError(err instanceof api.ApiError ? err.message : t.cropAdjust.confirmFailed);
      }
    } finally {
      setConfirming(false);
    }
  }

  /**
   * Check the crop before committing to it.
   *
   * Confirming runs the analysis, so a crop the pipeline cannot use costs
   * the customer a wait to find out. Across 30 real photographs the fit fell
   * back on a third of uncropped images, and 8 of those 10 failures were
   * recovered by re-cropping alone -- so the common case is one they can fix
   * right here.
   *
   * The warning does not block. Two of the thirty could not be fitted at any
   * crop, and trapping someone behind a check they cannot satisfy is worse
   * than letting them through to an honest "no scores" report.
   */
  async function handleConfirm() {
    if (!points || !dims) return;
    setBoundaryWarning(null);
    if (beforeConfirm && !(await beforeConfirm())) return;
    setChecking(true);
    try {
      const check = await api.checkCrop(token, code, side, toPixels(points));
      if (!check.boundary_found) {
        setBoundaryWarning(check.limitations);
        return;
      }
    } catch {
      // The check is an optimisation, not a gate. If it is unavailable the
      // customer must still be able to submit.
      toastError(t.cropAdjust.checkFailed);
    } finally {
      setChecking(false);
    }
    await submitCrop();
  }

  if (!photoUrl || !points) {
    return <Skeleton className="aspect-[3/4] w-full rounded-xl" />;
  }

  // Safe as an SVG polygon under the wrapper's non-uniform scaling -- unlike
  // the handles, which are HTML positioned by percentage, since circles
  // distort into ellipses under anisotropic scaling (see AnnotatedPhoto.tsx).
  const polygonPoints = points.map(([x, y]) => `${x},${y}`).join(" ");
  const centre: NormPoint = [
    points.reduce((s, p) => s + p[0], 0) / points.length,
    points.reduce((s, p) => s + p[1], 0) / points.length,
  ];

  let loupeStyle: CSSProperties | null = null;
  if (loupe) {
    const half = LOUPE_PX / 2;
    const px = loupe.x * loupe.width;
    const py = loupe.y * loupe.height;
    // Above the finger, which is what hides the corner; below it only when
    // there is no room above.
    const above = py - LOUPE_PX - LOUPE_GAP_PX;
    loupeStyle = {
      width: LOUPE_PX,
      height: LOUPE_PX,
      left: px - half,
      top: above >= 0 ? above : py + LOUPE_GAP_PX,
      backgroundImage: `url(${photoUrl})`,
      backgroundRepeat: "no-repeat",
      backgroundSize: `${loupe.width * LOUPE_ZOOM}px ${loupe.height * LOUPE_ZOOM}px`,
      backgroundPosition: `${half - px * LOUPE_ZOOM}px ${half - py * LOUPE_ZOOM}px`,
    };
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border p-4">
      <p className="text-sm font-semibold text-foreground">{t.cropAdjust.title}</p>
      <p className="text-sm text-muted">{t.cropAdjust.instructions}</p>
      <div ref={wrapperRef} className="relative touch-none select-none">
        <img src={photoUrl} alt="" className="w-full rounded-lg border border-border" draggable={false} />
        <svg
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          className="pointer-events-none absolute inset-0 h-full w-full"
        >
          <polygon
            points={polygonPoints}
            fill="var(--neon-pink)"
            fillOpacity={0.12}
            stroke="var(--neon-pink)"
            strokeWidth={0.006}
          />
        </svg>
        {points.map(([x, y], i) => (
          <button
            key={i}
            type="button"
            aria-label={t.cropAdjust.handleLabel[cornerKey([x, y], centre)]}
            onPointerDown={(e) => handlePointerDown(i, e)}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onKeyDown={(e) => handleKeyDown(i, e)}
            // 44px of transparent hit area around a 24px dot. The dot stays
            // its size because it marks the corner it is claiming.
            className="absolute flex h-11 w-11 -translate-x-1/2 -translate-y-1/2 touch-none items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--neon-pink)]"
            style={{ left: `${x * 100}%`, top: `${y * 100}%`, cursor: "grab" }}
          >
            <span
              aria-hidden="true"
              className="h-6 w-6 rounded-full border-2 border-white shadow-md"
              style={{ backgroundColor: "var(--neon-pink)" }}
            />
          </button>
        ))}
        {loupeStyle && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute z-10 overflow-hidden rounded-full border-2 border-white shadow-lg"
            style={loupeStyle}
          >
            <span
              className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2"
              style={{ backgroundColor: "var(--neon-pink)" }}
            />
            <span
              className="absolute left-0 top-1/2 h-px w-full -translate-y-1/2"
              style={{ backgroundColor: "var(--neon-pink)" }}
            />
          </span>
        )}
      </div>
      <p className="text-xs text-muted">{t.cropAdjust.keyboardHint}</p>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" onPress={handleSnap} isDisabled={snapping || confirming}>
          {t.cropAdjust.snapButton}
        </Button>
        <Button
          variant="outline"
          size="sm"
          aria-label={t.cropAdjust.rotateLeft}
          onPress={() => nudgeRotate(-1)}
          isDisabled={confirming}
        >
          ⟲ 1°
        </Button>
        <Button
          variant="outline"
          size="sm"
          aria-label={t.cropAdjust.rotateRight}
          onPress={() => nudgeRotate(1)}
          isDisabled={confirming}
        >
          1° ⟳
        </Button>
      </div>
      {boundaryWarning && (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-lg border-l-4 border border-border p-3"
          style={{ borderLeftColor: "var(--grade-warn)" }}
        >
          <p className="text-sm font-semibold text-foreground">{t.cropAdjust.boundaryWarningTitle}</p>
          {/* The explanation is the results page's own wording for this
              limitation, not a second phrasing of it. */}
          {boundaryWarning.map((codeName) => {
            const copy =
              t.submissionDetail.limitation[codeName as keyof typeof t.submissionDetail.limitation];
            return copy ? (
              <p key={codeName} className="text-sm leading-relaxed text-muted">
                {copy}
              </p>
            ) : null;
          })}
          <p className="text-sm leading-relaxed text-muted">{t.cropAdjust.boundaryWarningHint}</p>
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" size="sm" onPress={() => setBoundaryWarning(null)}>
              {t.cropAdjust.adjustInstead}
            </Button>
            <Button variant="outline" size="sm" onPress={submitCrop} isDisabled={confirming}>
              {confirming ? t.cropAdjust.confirming : t.cropAdjust.submitAnyway}
            </Button>
          </div>
        </div>
      )}

      {children}

      <Button
        variant="primary"
        onPress={handleConfirm}
        isDisabled={confirming || snapping || checking || boundaryWarning !== null}
      >
        {checking ? t.cropAdjust.checking : confirming ? t.cropAdjust.confirming : confirmLabel ?? t.cropAdjust.confirmButton}
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc --noEmit && npx eslint components/CropAdjustStep.tsx`
Expected: no output. (The magnifier and keyboard behaviour are exercised in the Task 12 browser walk; nothing renders this component differently until Task 10.)

- [ ] **Step 3: Commit**

```bash
git add frontend/components/CropAdjustStep.tsx
git commit -m "Crop editor: touch magnifier, keyboard-movable handles, labelled rotate"
```

---

### Task 10: Supporting components for the check page

Everything here is additive or backward-compatible, so the tree still builds before Task 11 uses it.

**Files:**
- Create: `frontend/components/CardLabelFields.tsx`, `frontend/components/OutOfChecksPanel.tsx`
- Modify: `frontend/components/ProcessingState.tsx`, `frontend/components/SubmissionOverview.tsx`, `frontend/components/PublicReport.tsx`

**Interfaces:**
- Consumes: `formatRemaining` (Task 8), `useQuota`, `t.checkFlow`, `t.quota`.
- Produces:
  - `CardLabelFields` (default) with props `{ value: CardLabels; onChange: (next: CardLabels) => void; nameRequired?: boolean }`
  - `type CardLabels = { card_name: string; set_name: string; card_number: string }`
  - `labelsOf(card: api.Card | null): CardLabels`
  - `labelChanges(before: CardLabels, after: CardLabels): api.CardUpdate`
  - `OutOfChecksPanel` (default, no props)
  - `ProcessingState` gains `stillWorking?: boolean`
  - `SubmissionOverview` gains `audience?: "customer" | "operator"` (default `"operator"`) and `afterScores?: ReactNode`

- [ ] **Step 1: `frontend/components/CardLabelFields.tsx`**:

```tsx
"use client";

import { Input, Label, TextField } from "@heroui/react";
import type { Card, CardUpdate } from "@/lib/api";
import { useTranslations } from "@/lib/i18n/context";

/** The card's labels as form state: never null, so inputs stay controlled. */
export type CardLabels = { card_name: string; set_name: string; card_number: string };

export function labelsOf(card: Card | null): CardLabels {
  return {
    card_name: card?.card_name ?? "",
    set_name: card?.set_name ?? "",
    card_number: card?.card_number ?? "",
  };
}

/** Only what changed, as a PATCH .../card body. A blanked field is sent as
 *  null, which clears it. */
export function labelChanges(before: CardLabels, after: CardLabels): CardUpdate {
  const changes: CardUpdate = {};
  (Object.keys(after) as (keyof CardLabels)[]).forEach((key) => {
    const next = after[key].trim();
    if (next !== before[key].trim()) changes[key] = next || null;
  });
  return changes;
}

/**
 * Name, set and number. Labels only -- nothing measured depends on them -- so
 * the check page offers them folded away and the header can edit them later.
 * Max lengths mirror backend models/card.py.
 */
export default function CardLabelFields({
  value,
  onChange,
  nameRequired = false,
}: {
  value: CardLabels;
  onChange: (next: CardLabels) => void;
  /** A mail-in needs a name: the operator matches the physical card by it. */
  nameRequired?: boolean;
}) {
  const t = useTranslations();
  return (
    <>
      <TextField
        value={value.card_name}
        onChange={(v) => onChange({ ...value, card_name: v })}
        isRequired={nameRequired}
        fullWidth
      >
        <Label>{t.checkFlow.cardName}</Label>
        <Input maxLength={200} />
      </TextField>
      <TextField value={value.set_name} onChange={(v) => onChange({ ...value, set_name: v })} fullWidth>
        <Label>{t.checkFlow.setName}</Label>
        <Input maxLength={200} />
      </TextField>
      <TextField
        value={value.card_number}
        onChange={(v) => onChange({ ...value, card_number: v })}
        fullWidth
      >
        <Label>{t.checkFlow.cardNumber}</Label>
        <Input maxLength={50} />
      </TextField>
    </>
  );
}
```

- [ ] **Step 2: `frontend/components/OutOfChecksPanel.tsx`**:

```tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, buttonVariants, cn } from "@heroui/react";
import { formatRemaining } from "@/lib/countdown";
import { useTranslations } from "@/lib/i18n/context";
import { useQuota } from "@/lib/quota-context";

/**
 * Shown instead of the photo step when the account has no checks left, so the
 * customer learns it before photographing and cropping rather than after.
 * Links to /pricing, the page that actually sells the plans.
 */
export default function OutOfChecksPanel() {
  const { quota } = useQuota();
  const t = useTranslations();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  const countdown = quota?.resets_at
    ? formatRemaining(quota.resets_at, now, {
        d: t.quota.unitDay,
        h: t.quota.unitHour,
        m: t.quota.unitMinute,
      })
    : null;

  return (
    <Card className="mx-auto w-full max-w-2xl">
      <Card.Header>
        <Card.Title>{t.quota.exhaustedTitle}</Card.Title>
      </Card.Header>
      <Card.Content className="flex flex-col gap-4">
        <p className="text-sm text-muted">
          {countdown ? t.quota.exhaustedBody.replace("{time}", countdown) : t.quota.exhaustedBodyNoTimer}
        </p>
        <div>
          <Link href="/pricing" className={cn(buttonVariants({ variant: "primary" }), "btn-press btn-neon-hover")}>
            {t.quota.seePlans}
          </Link>
        </div>
      </Card.Content>
    </Card>
  );
}
```

- [ ] **Step 3: `frontend/components/ProcessingState.tsx`** — add the prop and use it:

```tsx
export default function ProcessingState({
  status,
  locale = "en",
  stillWorking = false,
}: {
  status: SubmissionStatus;
  locale?: Locale;
  /** Polling gave up: say we'll email rather than spin forever. */
  stillWorking?: boolean;
}) {
  const t = getDictionary(locale);
  const title = status === "processing" ? t.submissionDetail.processingTitle : t.submissionDetail.awaitingScansTitle;

  return (
    <Card>
      <Card.Content className="flex flex-col items-center gap-4 py-8 text-center">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="text-sm text-muted">
          {stillWorking ? t.checkFlow.stillWorking : t.submissionDetail.processingDescription}
        </p>
        {!stillWorking && (
          <ProgressBar aria-label={title} isIndeterminate className="w-full max-w-xs">
            <ProgressBar.Track>
              <ProgressBar.Fill />
            </ProgressBar.Track>
          </ProgressBar>
        )}
      </Card.Content>
    </Card>
  );
}
```

- [ ] **Step 4: `frontend/components/SubmissionOverview.tsx`** — add `import type { ReactNode } from "react";`; extend the props with

```tsx
  /** "customer" hides the in-card status chip -- the page header already
   *  shows the customer's own wording. The admin view keeps it. */
  audience?: "customer" | "operator";
  /** Rendered directly under the scores: where "add the back" belongs on a
   *  front-only check, rather than below the whole report. */
  afterScores?: ReactNode;
```

(destructured with `audience = "operator"` and `afterScores`); change `<StatusBadge status={submission.status} locale={locale} />` to `{audience === "operator" && <StatusBadge status={submission.status} locale={locale} />}`; change `submission.card?.card_name ?? t.submissionDetail.unknownCard` to `submission.card?.card_name ?? t.checkFlow.untitledCard`; and immediately after the scores `</Card>` (the first top-level `Card`, before the per-side photo cards) insert:

```tsx
      {afterScores && <div className="mt-5">{afterScores}</div>}
```

- [ ] **Step 5: `frontend/components/PublicReport.tsx`** — change `report.card?.card_name ?? t.submissionDetail.unknownCard` to `report.card?.card_name ?? t.checkFlow.untitledCard`, so a nameless card reads the same on both pages.

- [ ] **Step 6: Verify**

Run: `cd frontend && npx tsc --noEmit && npx eslint components/CardLabelFields.tsx components/OutOfChecksPanel.tsx components/ProcessingState.tsx components/SubmissionOverview.tsx components/PublicReport.tsx`
Expected: no output.

- [ ] **Step 7: Commit**

```bash
git add frontend/components/CardLabelFields.tsx frontend/components/OutOfChecksPanel.tsx frontend/components/ProcessingState.tsx frontend/components/SubmissionOverview.tsx frontend/components/PublicReport.tsx
git commit -m "Add card-label fields and out-of-checks panel; untitled cards read the same everywhere"
```

---

### Task 11: The check page — `CheckFlow`, `SubmissionView`, the routes

**Files:**
- Create: `frontend/components/CheckFlow.tsx`, `frontend/components/SubmissionView.tsx`
- Modify (replace): `frontend/components/UploadStep.tsx`, `frontend/app/dashboard/new/page.tsx`, `frontend/app/dashboard/[code]/detail-client.tsx`
- Modify: `frontend/lib/i18n/en.ts`, `frontend/lib/i18n/es.ts` (delete keys that stop being used)

**Interfaces:**
- Consumes: everything from Tasks 8–10.
- Produces: `CheckFlow` (default) props `{ submission: api.SubmissionDetail | null; onChange: (next: api.SubmissionDetail) => void }`; `SubmissionView` (default) props `{ code: string | null }`; `UploadStep` props become `{ code: string; token: string; scanSides: api.ScanSide[]; onUploaded: (updated: api.SubmissionDetail) => void }` (back photo only).

How the page holds together (spec §5.1): both routes render `SubmissionView`, which owns the submission state. `/dashboard/new` starts with `code={null}`; when the first photo creates the draft, `CheckFlow` swaps the address to `/dashboard/{code}` with `window.history.replaceState` (supported by the Next router — `node_modules/next/dist/docs/01-app/01-getting-started/04-linking-and-navigating.md`, "Native History API") and hands the new submission up through `onChange`. Nothing remounts, and a reload at `/dashboard/{code}` renders the same `SubmissionView` from server state.

- [ ] **Step 1: `frontend/components/CheckFlow.tsx`**:

```tsx
"use client";

import { useCallback, useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import Link from "next/link";
import { Card, Checkbox, Label, ListBox, ProgressBar, Select, buttonVariants, cn } from "@heroui/react";
import Button from "@/components/Button";
import CardLabelFields, { labelChanges, labelsOf, type CardLabels } from "@/components/CardLabelFields";
import CropAdjustStep from "@/components/CropAdjustStep";
import ErrorState from "@/components/ErrorState";
import OutOfChecksPanel from "@/components/OutOfChecksPanel";
import Skeleton from "@/components/Skeleton";
import { useAuth } from "@/lib/auth-context";
import { useLocale, useTranslations } from "@/lib/i18n/context";
import { useQuota } from "@/lib/quota-context";
import { toastError, toastSuccess } from "@/lib/toast";
import * as api from "@/lib/api";

const LAST_GAME_KEY = "zgrader_last_game";

/** Wrapped: storage can be absent or throw (private windows, blocked site
 *  data, thumbnail capture). The page works without it. */
function readLastGame(): string | null {
  try {
    return window.localStorage.getItem(LAST_GAME_KEY);
  } catch {
    return null;
  }
}

function rememberGame(game: string): void {
  try {
    window.localStorage.setItem(LAST_GAME_KEY, game);
  } catch {
    // A per-browser convenience; losing it costs one extra tap.
  }
}

function FoilCheckbox({ value, onChange }: { value: boolean; onChange: (next: boolean) => void }) {
  const t = useTranslations();
  return (
    <div className="flex flex-col gap-1">
      <Checkbox.Root isSelected={value} onChange={onChange}>
        <Checkbox.Content>
          <Checkbox.Control>
            <Checkbox.Indicator />
          </Checkbox.Control>
          {t.checkFlow.foil}
        </Checkbox.Content>
      </Checkbox.Root>
      <p className="text-xs text-muted">{t.checkFlow.foilHint}</p>
    </div>
  );
}

/** "Uses one check, only if we can score it." The number comes from the
 *  quota, never the copy; nothing is shown for unlimited plans, an unknown
 *  quota, or a submission already charged. */
function QuotaLine({ charged }: { charged: boolean }) {
  const { quota } = useQuota();
  const t = useTranslations();
  if (charged || !quota || quota.unlimited || quota.remaining === null) return null;
  return (
    <p className="text-xs text-muted">{t.checkFlow.usesOneCheck.replace("{count}", String(quota.remaining))}</p>
  );
}

function VerifyEmailPanel({ email }: { email: string }) {
  const t = useTranslations();
  const [sending, setSending] = useState(false);

  async function resend() {
    setSending(true);
    try {
      await api.resendVerification(email);
      toastSuccess(t.checkFlow.resent);
    } catch (err) {
      toastError(err instanceof api.ApiError ? err.message : t.checkFlow.createFailed);
    } finally {
      setSending(false);
    }
  }

  return (
    <Card className="mx-auto w-full max-w-2xl">
      <Card.Header>
        <Card.Title>{t.checkFlow.unverifiedTitle}</Card.Title>
        <Card.Description>{t.checkFlow.unverifiedBody.replace("{email}", email)}</Card.Description>
      </Card.Header>
      <Card.Content>
        <Button variant="primary" onPress={resend} isDisabled={sending}>
          {t.checkFlow.resend}
        </Button>
      </Card.Content>
    </Card>
  );
}

function DraftsFullPanel() {
  const t = useTranslations();
  return (
    <Card className="mx-auto w-full max-w-2xl">
      <Card.Header>
        <Card.Title>{t.checkFlow.draftsFullTitle}</Card.Title>
        <Card.Description>{t.checkFlow.draftsFullBody}</Card.Description>
      </Card.Header>
      <Card.Content>
        <Link href="/dashboard" className={cn(buttonVariants({ variant: "primary" }), "btn-press btn-neon-hover")}>
          {t.checkFlow.draftsFullLink}
        </Link>
      </Card.Content>
    </Card>
  );
}

function GameSelect({
  games,
  value,
  onChange,
  isDisabled,
}: {
  games: api.Game[];
  value: string;
  onChange: (game: string) => void;
  isDisabled: boolean;
}) {
  const t = useTranslations();
  return (
    <Select.Root
      selectedKey={value}
      onSelectionChange={(key) => onChange(String(key))}
      isDisabled={isDisabled}
      isRequired
      fullWidth
    >
      <Label>{t.checkFlow.game}</Label>
      <Select.Trigger>
        <Select.Value />
        <Select.Indicator />
      </Select.Trigger>
      <Select.Popover>
        <ListBox>
          {games.map((g) => (
            <ListBox.Item id={g.game} key={g.game} textValue={g.game}>
              {g.game}
              {!g.verified ? t.checkFlow.dimensionsUnverified : ""}
            </ListBox.Item>
          ))}
        </ListBox>
      </Select.Popover>
    </Select.Root>
  );
}

/**
 * The photo-first check (spec §5.2): blocks first, then game and photo, then
 * the crop editor in place. Analysis needs only the game (for the card's
 * physical size) and foil; name, set and number are optional labels.
 */
export default function CheckFlow({
  submission,
  onChange,
}: {
  submission: api.SubmissionDetail | null;
  onChange: (next: api.SubmissionDetail) => void;
}) {
  const { user, token } = useAuth();
  const { quota, refresh: refreshQuota } = useQuota();
  const { locale } = useLocale();
  const t = useTranslations();
  const cameraRef = useRef<HTMLInputElement>(null);
  const libraryRef = useRef<HTMLInputElement>(null);

  const [games, setGames] = useState<api.Game[] | null>(null);
  const [gamesError, setGamesError] = useState<string | null>(null);
  const [game, setGame] = useState(submission?.card?.game ?? "");
  const [uploading, setUploading] = useState(false);
  const [mailIn, setMailIn] = useState(false);
  const [draftsFull, setDraftsFull] = useState(false);
  const [exhausted, setExhausted] = useState(false);
  const [foil, setFoil] = useState(submission?.card?.foil ?? false);
  const [labels, setLabels] = useState<CardLabels>(() => labelsOf(submission?.card ?? null));

  const loadGames = useCallback(() => {
    setGamesError(null);
    api
      .getGames()
      .then((list) => {
        setGames(list);
        // A draft already has its game; only a fresh check picks a default.
        if (!submission) {
          const last = readLastGame();
          setGame(last && list.some((g) => g.game === last) ? last : list[0]?.game ?? "");
        }
      })
      .catch((err) => setGamesError(err instanceof Error ? err.message : t.checkFlow.createFailed));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(loadGames, [loadGames]);

  /** The two refusals the page shows as panels rather than toasts. */
  function handleRefusal(err: unknown): boolean {
    if (!(err instanceof api.ApiError)) return false;
    if (err.status === 402) {
      setExhausted(true);
      void refreshQuota();
      return true;
    }
    if (api.errorCode(err) === "too_many_drafts") {
      setDraftsFull(true);
      return true;
    }
    return false;
  }

  /** The draft becomes this page's address without a remount, so a reload
   *  resumes it rather than starting another. */
  function adopt(created: api.SubmissionDetail) {
    rememberGame(game);
    window.history.replaceState(null, "", `/dashboard/${created.submission_code}`);
    onChange(created);
  }

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !token) return;
    setUploading(true);
    try {
      let current = submission;
      if (!current) {
        current = await api.createSubmission(token, { game, foil: false, language: locale });
        // Adopted before the upload, so a failed upload retries into this
        // draft rather than opening a second one.
        adopt(current);
      }
      onChange(await api.uploadScan(token, current.submission_code, "front", file));
    } catch (err) {
      if (!handleRefusal(err)) {
        toastError(err instanceof api.ApiError ? err.message : t.upload.uploadFailed);
      }
    } finally {
      setUploading(false);
    }
  }

  async function handleMailIn(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setUploading(true);
    try {
      adopt(
        await api.createSubmission(token, {
          game,
          card_name: labels.card_name.trim(),
          set_name: labels.set_name.trim() || undefined,
          card_number: labels.card_number.trim() || undefined,
          foil,
          language: locale,
          mail_in: true,
        })
      );
    } catch (err) {
      if (!handleRefusal(err)) {
        toastError(err instanceof api.ApiError ? err.message : t.checkFlow.createFailed);
      }
    } finally {
      setUploading(false);
    }
  }

  /** Runs before the crop check: foil changes the analysis, so it has to be
   *  saved before the analysis runs; labels ride along. */
  async function saveCardDetails(): Promise<boolean> {
    if (!token || !submission) return false;
    const changes = labelChanges(labelsOf(submission.card), labels);
    if (foil !== (submission.card?.foil ?? false)) changes.foil = foil;
    if (Object.keys(changes).length === 0) return true;
    try {
      onChange(await api.updateCard(token, submission.submission_code, changes));
      return true;
    } catch (err) {
      toastError(err instanceof api.ApiError ? err.message : t.checkFlow.detailsFailed);
      return false;
    }
  }

  const outOfChecks =
    exhausted || (quota !== null && !quota.unlimited && quota.remaining === 0 && !submission?.charged);

  if (user && !user.is_verified) return <VerifyEmailPanel email={user.email} />;
  if (outOfChecks) return <OutOfChecksPanel />;
  if (draftsFull) return <DraftsFullPanel />;

  if (submission && token && submission.scan_sides.includes("front")) {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <CropAdjustStep
          token={token}
          code={submission.submission_code}
          side="front"
          confirmLabel={t.checkFlow.analyse}
          beforeConfirm={saveCardDetails}
          onConfirmError={handleRefusal}
          onConfirmed={(updated) => {
            onChange(updated);
            void refreshQuota();
          }}
        >
          <FoilCheckbox value={foil} onChange={setFoil} />
          <details className="rounded-lg border border-border px-3 py-2">
            <summary className="-my-2 cursor-pointer py-2 text-sm font-semibold text-foreground">
              {t.checkFlow.detailsSummary}
            </summary>
            <div className="mt-2 flex flex-col gap-3 pb-1">
              <CardLabelFields value={labels} onChange={setLabels} />
            </div>
          </details>
          <QuotaLine charged={submission.charged} />
        </CropAdjustStep>
      </div>
    );
  }

  return (
    <Card className="mx-auto w-full max-w-2xl">
      <Card.Header>
        <Card.Title>{mailIn ? t.checkFlow.mailInTitle : t.checkFlow.title}</Card.Title>
        <Card.Description>{mailIn ? t.checkFlow.mailInBody : t.checkFlow.subtitle}</Card.Description>
      </Card.Header>
      <Card.Content className="flex flex-col gap-4">
        {gamesError ? (
          <ErrorState message={gamesError} onRetry={loadGames} retryLabel={t.common.retry} />
        ) : games === null ? (
          <Skeleton className="h-10 w-full" />
        ) : (
          <GameSelect games={games} value={game} onChange={setGame} isDisabled={submission !== null} />
        )}

        {mailIn ? (
          <form className="flex flex-col gap-4" onSubmit={handleMailIn}>
            <CardLabelFields value={labels} onChange={setLabels} nameRequired />
            <FoilCheckbox value={foil} onChange={setFoil} />
            <Button
              type="submit"
              variant="primary"
              isDisabled={uploading || !game || !labels.card_name.trim()}
              fullWidth
            >
              {t.checkFlow.mailInSubmit}
            </Button>
            <button
              type="button"
              onClick={() => setMailIn(false)}
              className="-my-2 self-start py-2 text-sm text-accent hover:underline"
            >
              {t.checkFlow.mailInCancel}
            </button>
          </form>
        ) : (
          <>
            <p className="text-sm text-muted">{t.upload.backgroundHint}</p>
            {uploading ? (
              <ProgressBar aria-label={t.upload.uploading} isIndeterminate className="w-full">
                <ProgressBar.Track>
                  <ProgressBar.Fill />
                </ProgressBar.Track>
              </ProgressBar>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {/* Two inputs on purpose: a bare `capture` opens the camera
                    directly on Android, with no way to pick a photo already
                    taken. */}
                <input ref={cameraRef} type="file" accept="image/*" capture="environment" onChange={handleFile} className="hidden" />
                <input ref={libraryRef} type="file" accept="image/*" onChange={handleFile} className="hidden" />
                <Button variant="primary" onPress={() => cameraRef.current?.click()} isDisabled={!game}>
                  {t.checkFlow.takePhoto}
                </Button>
                <Button variant="outline" onPress={() => libraryRef.current?.click()} isDisabled={!game}>
                  {t.checkFlow.choosePhoto}
                </Button>
              </div>
            )}
            <QuotaLine charged={false} />
            {!submission && (
              <button
                type="button"
                onClick={() => setMailIn(true)}
                className="-my-2 self-start py-2 text-sm text-accent hover:underline"
              >
                {t.checkFlow.mailInLink}
              </button>
            )}
          </>
        )}
      </Card.Content>
    </Card>
  );
}
```

- [ ] **Step 2: `frontend/components/UploadStep.tsx`** — replace with the back-only version:

```tsx
"use client";

import { useRef, useState, type ChangeEvent } from "react";
import { Card, ProgressBar } from "@heroui/react";
import Button from "@/components/Button";
import CropAdjustStep from "@/components/CropAdjustStep";
import { toastError } from "@/lib/toast";
import { useTranslations } from "@/lib/i18n/context";
import * as api from "@/lib/api";

/**
 * The back photo, offered once the front has a result. The front goes through
 * CheckFlow; this completes a check, and adding it never charges again.
 */
export default function UploadStep({
  code,
  token,
  scanSides,
  onUploaded,
}: {
  code: string;
  token: string;
  scanSides: api.ScanSide[];
  onUploaded: (updated: api.SubmissionDetail) => void;
}) {
  const t = useTranslations();
  const cameraRef = useRef<HTMLInputElement>(null);
  const libraryRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  // A back already uploaded (a refresh mid-crop) goes straight to the crop.
  const [awaitingCrop, setAwaitingCrop] = useState(scanSides.includes("back"));

  async function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploading(true);
    try {
      await api.uploadScan(token, code, "back", file);
      setAwaitingCrop(true);
    } catch (err) {
      toastError(err instanceof api.ApiError ? err.message : t.upload.uploadFailed);
    } finally {
      setUploading(false);
    }
  }

  return (
    <Card>
      <Card.Header>
        <Card.Title>{t.checkFlow.backTitle}</Card.Title>
        <Card.Description>{t.checkFlow.backBody}</Card.Description>
      </Card.Header>
      <Card.Content>
        {awaitingCrop ? (
          <CropAdjustStep
            token={token}
            code={code}
            side="back"
            onConfirmed={(updated) => {
              setAwaitingCrop(false);
              onUploaded(updated);
            }}
          />
        ) : uploading ? (
          <ProgressBar aria-label={t.upload.uploading} isIndeterminate className="w-full">
            <ProgressBar.Track>
              <ProgressBar.Fill />
            </ProgressBar.Track>
          </ProgressBar>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            <input ref={cameraRef} type="file" accept="image/*" capture="environment" onChange={handleChange} className="hidden" />
            <input ref={libraryRef} type="file" accept="image/*" onChange={handleChange} className="hidden" />
            <Button variant="outline" onPress={() => cameraRef.current?.click()}>
              {t.checkFlow.takePhoto}
            </Button>
            <Button variant="outline" onPress={() => libraryRef.current?.click()}>
              {t.checkFlow.choosePhoto}
            </Button>
          </div>
        )}
      </Card.Content>
    </Card>
  );
}
```

- [ ] **Step 3: `frontend/components/SubmissionView.tsx`**:

```tsx
"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card, buttonVariants, cn } from "@heroui/react";
import Button from "@/components/Button";
import CardLabelFields, { labelChanges, labelsOf, type CardLabels } from "@/components/CardLabelFields";
import CheckFlow from "@/components/CheckFlow";
import ConfirmDialog from "@/components/ConfirmDialog";
import ErrorState from "@/components/ErrorState";
import ProcessingState from "@/components/ProcessingState";
import SharePanel from "@/components/SharePanel";
import Skeleton from "@/components/Skeleton";
import StatusBadge from "@/components/StatusBadge";
import SubmissionOverview from "@/components/SubmissionOverview";
import UploadStep from "@/components/UploadStep";
import { useAuth } from "@/lib/auth-context";
import { useLocale, useTranslations } from "@/lib/i18n/context";
import { toastError, toastSuccess } from "@/lib/toast";
import { useSubmissionPoll } from "@/lib/use-submission-poll";
import * as api from "@/lib/api";

const PRE_ANALYSIS = new Set<api.SubmissionStatus>(["created", "awaiting_scans"]);
// Mirrors the backend's upload gate: once approved/published/errored, no
// more scans.
const UPLOAD_ALLOWED = new Set<api.SubmissionStatus>(["created", "awaiting_scans", "draft_ready"]);
const IN_REVIEW = new Set<api.SubmissionStatus>(["draft_ready", "approved"]);

function SubmissionHeader({
  submission,
  onChange,
  actions,
}: {
  submission: api.SubmissionDetail;
  onChange: (next: api.SubmissionDetail) => void;
  actions: ReactNode;
}) {
  const { token } = useAuth();
  const { locale } = useLocale();
  const t = useTranslations();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [labels, setLabels] = useState<CardLabels>(() => labelsOf(submission.card));
  const name = submission.card?.card_name ?? null;

  async function save() {
    if (!token) return;
    const changes = labelChanges(labelsOf(submission.card), labels);
    if (Object.keys(changes).length === 0) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      onChange(await api.updateCard(token, submission.submission_code, changes));
      setEditing(false);
      toastSuccess(t.checkFlow.detailsSaved);
    } catch (err) {
      toastError(err instanceof api.ApiError ? err.message : t.checkFlow.detailsFailed);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mb-5 flex flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="break-words text-2xl font-bold text-foreground">{name ?? t.checkFlow.untitledCard}</h1>
          {/* The code is for support emails, not the headline: it is
              sequential and means nothing to the customer. */}
          <p className="text-xs text-muted">
            {t.checkFlow.refLabel.replace("{code}", submission.submission_code)} ·{" "}
            {new Date(submission.created_at).toLocaleDateString(locale)}
            {!editing && (
              <button
                type="button"
                onClick={() => {
                  setLabels(labelsOf(submission.card));
                  setEditing(true);
                }}
                className="-my-2 ml-2 inline-flex py-2 text-accent hover:underline"
              >
                {name ? t.checkFlow.editDetails : t.checkFlow.addName}
              </button>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            status={submission.status}
            locale={locale}
            audience="customer"
            mailIn={submission.mail_in}
            charged={submission.charged}
          />
          {actions}
        </div>
      </div>
      {editing && (
        <Card>
          <Card.Content className="flex flex-col gap-3">
            <CardLabelFields value={labels} onChange={setLabels} />
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" size="sm" onPress={save} isDisabled={saving}>
                {t.checkFlow.saveDetails}
              </Button>
              <Button variant="outline" size="sm" onPress={() => setEditing(false)}>
                {t.checkFlow.cancelEdit}
              </Button>
            </div>
          </Card.Content>
        </Card>
      )}
    </div>
  );
}

function Notice({ title, body }: { title: string; body: string }) {
  return (
    <Card>
      <Card.Content>
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="mt-1 text-sm text-muted">{body}</p>
      </Card.Content>
    </Card>
  );
}

function AnalysisFailed({ charged, onDelete }: { charged: boolean; onDelete: () => void }) {
  const t = useTranslations();
  return (
    <Card>
      <Card.Header>
        <Card.Title>{t.checkFlow.errorTitle}</Card.Title>
        {/* A charged submission errored on a re-analysis after one that
            scored, so "it didn't use a check" would be untrue. */}
        {!charged && <Card.Description>{t.checkFlow.errorFree}</Card.Description>}
      </Card.Header>
      <Card.Content className="flex flex-col gap-4">
        <p className="text-sm text-muted">{t.checkFlow.errorTips}</p>
        <div className="flex flex-wrap gap-2">
          <Link href="/dashboard/new" className={cn(buttonVariants({ variant: "primary" }), "btn-press btn-neon-hover")}>
            {t.checkFlow.tryAnother}
          </Link>
          <Button variant="outline" onPress={onDelete}>
            {t.submissionDetail.deleteButton}
          </Button>
        </div>
      </Card.Content>
    </Card>
  );
}

/**
 * Every state of one submission, from "no photo yet" to the published report.
 * Rendered by /dashboard/new (code null) and /dashboard/[code]. It owns the
 * submission state, so the draft CheckFlow creates on the first page becomes
 * the report on the same page without a navigation.
 */
export default function SubmissionView({ code }: { code: string | null }) {
  const { token } = useAuth();
  const { locale } = useLocale();
  const t = useTranslations();
  const router = useRouter();
  const [submission, setSubmission] = useState<api.SubmissionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(() => {
    if (!token || !code) return;
    setError(null);
    api
      .getSubmission(token, code)
      .then(setSubmission)
      .catch((err) => setError(err instanceof Error ? err.message : t.submissionDetail.loadFailed));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, code]);

  useEffect(load, [load]);

  const analysing =
    submission !== null &&
    (submission.status === "processing" ||
      (PRE_ANALYSIS.has(submission.status) && submission.confirmed_sides.includes("front")));

  const pollTimedOut = useSubmissionPoll(analysing, async () => {
    if (!token || !submission) return;
    setSubmission(await api.getSubmission(token, submission.submission_code));
  });

  async function handleDownload() {
    if (!token || !submission) return;
    setDownloading(true);
    try {
      const blob = await api.downloadReport(token, submission.submission_code);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${submission.submission_code}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      toastError(err instanceof Error ? err.message : t.submissionDetail.downloadFailed);
    } finally {
      setDownloading(false);
    }
  }

  async function handleDelete() {
    if (!token || !submission) return;
    setDeleting(true);
    try {
      await api.deleteSubmission(token, submission.submission_code);
      router.push("/dashboard");
    } catch (err) {
      toastError(err instanceof Error ? err.message : t.submissionDetail.deleteFailed);
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  async function handleToggleRegion(regionKey: string, dismissed: boolean) {
    if (!token || !submission) return;
    try {
      setSubmission(await api.toggleRegion(token, submission.submission_code, regionKey, dismissed));
    } catch (err) {
      toastError(err instanceof Error ? err.message : t.breakout.toggleFailed);
    }
  }

  if (error) return <ErrorState message={error} onRetry={load} retryLabel={t.common.retry} />;
  if (code && !submission) {
    return (
      <div className="flex flex-col gap-5">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }
  if (!submission) return <CheckFlow submission={null} onChange={setSubmission} />;

  const s = submission;
  let body: ReactNode;
  if (s.mail_in && PRE_ANALYSIS.has(s.status) && !analysing) {
    body = (
      <Notice
        title={t.checkFlow.awaitingCardTitle}
        body={t.checkFlow.awaitingCardBody.replace("{code}", s.submission_code)}
      />
    );
  } else if (PRE_ANALYSIS.has(s.status) && !s.confirmed_sides.includes("front")) {
    body = <CheckFlow submission={s} onChange={setSubmission} />;
  } else if (analysing) {
    body = <ProcessingState status="processing" locale={locale} stillWorking={pollTimedOut} />;
  } else if (s.status === "error") {
    body = <AnalysisFailed charged={s.charged} onDelete={() => setConfirmDelete(true)} />;
  } else {
    body = (
      <div className="flex flex-col gap-5">
        {IN_REVIEW.has(s.status) && <Notice title={t.checkFlow.reviewTitle} body={t.checkFlow.reviewBody} />}
        <SubmissionOverview
          submission={s}
          token={token!}
          locale={locale}
          audience="customer"
          onToggleRegion={handleToggleRegion}
          onAdjusted={setSubmission}
          afterScores={
            UPLOAD_ALLOWED.has(s.status) && !s.confirmed_sides.includes("back") ? (
              <UploadStep code={s.submission_code} token={token!} scanSides={s.scan_sides} onUploaded={setSubmission} />
            ) : null
          }
        />
        <SharePanel code={s.submission_code} token={token!} publishable={s.status === "published"} />
      </div>
    );
  }

  return (
    <>
      <SubmissionHeader
        submission={s}
        onChange={setSubmission}
        actions={
          <>
            {s.status === "published" && (
              <Button variant="primary" onPress={handleDownload} isDisabled={downloading}>
                {downloading ? t.submissionDetail.downloading : t.submissionDetail.download}
              </Button>
            )}
            <Button variant="outline" onPress={() => setConfirmDelete(true)}>
              {t.submissionDetail.deleteButton}
            </Button>
          </>
        }
      />
      <ConfirmDialog
        open={confirmDelete}
        title={t.submissionDetail.deleteTitle}
        body={t.submissionDetail.deleteBody}
        confirmLabel={t.submissionDetail.deleteConfirm}
        cancelLabel={t.submissionDetail.deleteCancel}
        destructive
        busy={deleting}
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />
      {body}
    </>
  );
}
```

- [ ] **Step 4: Routes** — replace `frontend/app/dashboard/[code]/detail-client.tsx` with:

```tsx
"use client";

import RequireAuth from "@/components/RequireAuth";
import SubmissionView from "@/components/SubmissionView";

export default function SubmissionDetailClient({ code }: { code: string }) {
  return (
    <RequireAuth>
      <SubmissionView code={code} />
    </RequireAuth>
  );
}
```

and `frontend/app/dashboard/new/page.tsx` with:

```tsx
"use client";

import RequireAuth from "@/components/RequireAuth";
import SubmissionView from "@/components/SubmissionView";

/** The check page. Starts with no submission; the first photo creates one and
 *  the address becomes /dashboard/{code} without a remount (SubmissionView). */
export default function NewCheckPage() {
  return (
    <RequireAuth>
      <SubmissionView code={null} />
    </RequireAuth>
  );
}
```

- [ ] **Step 5: Delete copy nothing uses any more** — from both `en.ts` and `es.ts`: the whole `newSubmission` block (its shipping subtitle was the stale "then ship it to us for scanning"), and from `upload` the keys `title`, `subtitle`, `frontLabel`, `backLabel`, `backHint`, `chooseFile`, `frontUploadedTitle`, `frontUploadedNote`. Keep `backgroundHint`, `uploading`, `uploadFailed`, `invalidImage`, `fileTooLarge`. `tsc` fails if anything still reads a deleted key — fix the reader, not the dictionary.

- [ ] **Step 6: Verify**

Run: `cd frontend && npx tsc --noEmit && npx eslint components/CheckFlow.tsx components/SubmissionView.tsx components/UploadStep.tsx "app/dashboard/new/page.tsx" "app/dashboard/[code]/detail-client.tsx" && npx next build`
Expected: no `tsc`/`eslint` output; the build succeeds and `/r/[token]` is still listed as `●` (ISR), not `ƒ`.

- [ ] **Step 7: Commit**

```bash
git add frontend/components/CheckFlow.tsx frontend/components/SubmissionView.tsx frontend/components/UploadStep.tsx frontend/app/dashboard/new/page.tsx "frontend/app/dashboard/[code]/detail-client.tsx" frontend/lib/i18n/en.ts frontend/lib/i18n/es.ts
git commit -m "Photo-first check page: one view from first photo to report"
```

---

### Task 12: Dashboard list — names, scores, customer status words

**Files:**
- Modify (replace): `frontend/app/dashboard/page.tsx`
- Modify: `frontend/lib/i18n/en.ts`, `frontend/lib/i18n/es.ts` (delete the table-column keys)

**Interfaces:**
- Consumes: `SubmissionSummary` fields (Task 8), `StatusBadge` `audience` (Task 8), `CATEGORY_ORDER`/`gradeTierClass` (`lib/grade-display.ts`), `t.dashboard.scoreAbbrev|notCharged|continue`.

One responsive list rather than a table: rows stack below `sm` and sit on one line above it, so nothing scrolls sideways at 320.

- [ ] **Step 1: Replace `frontend/app/dashboard/page.tsx`** with:

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Card, buttonVariants, cn } from "@heroui/react";
import RequireAuth from "@/components/RequireAuth";
import StatusBadge from "@/components/StatusBadge";
import Skeleton from "@/components/Skeleton";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import { useAuth } from "@/lib/auth-context";
import { CATEGORY_ORDER, gradeTierClass } from "@/lib/grade-display";
import { useLocale, useTranslations } from "@/lib/i18n/context";
import * as api from "@/lib/api";

/** The four combined scores, compact. A null is "not measurable" and reads
 *  as a dash -- never a zero. The full category name is for screen readers;
 *  the abbreviation is what fits beside it. */
function ScoreStrip({ scores }: { scores: api.SubmissionSummary["scores"] }) {
  const t = useTranslations();
  const present = CATEGORY_ORDER.filter((c) => c in scores);
  if (present.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {present.map((category) => {
        const value = scores[category] ?? null;
        return (
          <span
            key={category}
            className={`inline-flex items-baseline gap-1 rounded-md px-1.5 py-0.5 text-xs ${
              value === null ? "text-muted" : gradeTierClass(value)
            }`}
          >
            <span aria-hidden="true" className="opacity-80">
              {t.dashboard.scoreAbbrev[category]}
            </span>
            <span className="sr-only">{t.category[category]}</span>
            <span className="font-semibold tabular-nums">{value === null ? "—" : value.toFixed(1)}</span>
          </span>
        );
      })}
    </div>
  );
}

function DashboardList() {
  const { token } = useAuth();
  const { locale } = useLocale();
  const t = useTranslations();
  const [submissions, setSubmissions] = useState<api.SubmissionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!token) return;
    setError(null);
    api
      .listSubmissions(token)
      .then(setSubmissions)
      .catch((err) => setError(err instanceof Error ? err.message : t.dashboard.loadFailed));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(load, [load]);

  return (
    <>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t.dashboard.title}</h1>
          <p className="text-sm text-muted">{t.dashboard.subtitle}</p>
        </div>
        <Link href="/dashboard/new" className={cn(buttonVariants({ variant: "primary" }), "btn-press btn-neon-hover")}>
          {t.dashboard.newSubmission}
        </Link>
      </div>

      {error ? (
        <ErrorState message={error} onRetry={load} retryLabel={t.common.retry} />
      ) : (
        <Card>
          <Card.Content>
            {submissions === null ? (
              <div className="flex flex-col gap-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : submissions.length === 0 ? (
              <EmptyState
                title={t.dashboard.emptyTitle}
                description={t.dashboard.emptyDescription}
                actionLabel={t.dashboard.emptyCta}
                actionHref="/dashboard/new"
              />
            ) : (
              <ul className="flex flex-col divide-y divide-border">
                {submissions.map((s) => {
                  // An uncharged photo draft: the customer's own unfinished
                  // work, which costs nothing until it is analysed.
                  const draft =
                    !s.charged && !s.mail_in && (s.status === "created" || s.status === "awaiting_scans");
                  return (
                    <li key={s.submission_code}>
                      {/* The whole row is the link: the rows above and below
                          are other cards, so a small target opens the wrong one. */}
                      <Link
                        href={`/dashboard/${s.submission_code}`}
                        className="-mx-2 flex flex-col gap-2 rounded-lg px-2 py-3 hover:bg-surface-secondary sm:flex-row sm:items-center sm:justify-between sm:gap-4"
                      >
                        <div className="min-w-0">
                          <p className="truncate font-semibold text-foreground">
                            {s.card_name ?? t.checkFlow.untitledCard}
                          </p>
                          <p className="text-xs text-muted">
                            {s.game ? `${s.game} · ` : ""}
                            {new Date(s.created_at).toLocaleDateString(locale)}
                            {draft ? ` · ${t.dashboard.notCharged}` : ""}
                          </p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                          <ScoreStrip scores={s.scores} />
                          <StatusBadge
                            status={s.status}
                            locale={locale}
                            audience="customer"
                            mailIn={s.mail_in}
                            charged={s.charged}
                          />
                          <span className="text-sm text-accent">{draft ? t.dashboard.continue : t.dashboard.view}</span>
                        </div>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </Card.Content>
        </Card>
      )}
    </>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardList />
    </RequireAuth>
  );
}
```

- [ ] **Step 2: Delete** `colCode`, `colStatus` and `colCreated` from `dashboard` in both `en.ts` and `es.ts` (nothing else reads them; `tsc` confirms).

- [ ] **Step 3: Verify**

Run: `cd frontend && npx tsc --noEmit && npx eslint app/dashboard/page.tsx`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/dashboard/page.tsx frontend/lib/i18n/en.ts frontend/lib/i18n/es.ts
git commit -m "Dashboard list: card names, scores and customer status words"
```

---

### Task 13: Docs, and prove it in a browser

**Files:**
- Modify: `AGENTS.md`, `docs/qa_checklist.md`
- Not committed: `C:\Claude\Projects\ZGrader\.claude\launch.json` (the session's launch config), a preview script in the executing session's scratchpad.

- [ ] **Step 1: AGENTS.md invariant** — insert under **Invariants**, directly after the paragraph that begins "**Re-running analysis replaces the previous assessment**":

```markdown
**A check is charged when an analysis first scores the card — once, and never refunded.**
`entitlements.charge_if_scored` is the only thing that spends one, called from `_advance_submission`
so the API's `confirm-crop` and the worker charge identically; `run_analysis` knows nothing of
billing, so `dev_trigger` stays free. "Scored" means at least one combined `AnalysisResult` with a
number, read from the database rather than from relationship collections the pipeline's bulk
deletes leave stale. A pipeline error or an all-declined result (a failed geometry fit) costs
nothing: the customer got no answer. `submissions.charged_at` is claimed by a conditional
`UPDATE ... WHERE charged_at IS NULL`, because the API and the worker are not serialised and only
one of two racing analyses may charge.

It used to be spent at "Create submission", before any photo existed, so an abandoned draft or a
photo that never cropped still cost one. The migration backfilled every existing row to its
`created_at` — left NULL, a late back photo on an old submission would have charged it twice.

Two consequences are easy to undo by accident. `confirm-crop` refuses with 402 **before** it saves
the crop points: saved points make the front confirmed, the worker's poll analyses confirmed fronts
without asking anyone, and a refusal after the save would be followed by a charge past the limit
anyway. And because a draft is free, drafts need their own ceiling — `max_open_drafts` photo
drafts per account, with `purge_stale_drafts` removing any untouched for `draft_retention_days`,
photos first. "Untouched" is the later of the submission's and its newest photo's `updated_at`,
because an upload writes a `ScanImage`, not the submission row. Mail-in submissions are exempt from
both: their card is in the post.
```

- [ ] **Step 2: QA checklist** — in `docs/qa_checklist.md`, directly before `## Client sees the result`, add:

```markdown
## Photo check (self-serve)

- [ ] `/dashboard/new` as an **unverified** account shows "Confirm your email" with a working
      Resend button, and no photo buttons.
- [ ] As a verified account: the game defaults to the last one used; "Take photo" opens the camera
      on a phone, "Choose photo" opens the library.
- [ ] Choosing a photo changes the address to `/dashboard/SUB-…` and shows the crop editor.
      Reloading there resumes the crop — it does not start a new draft.
- [ ] On a phone, dragging a corner shows the magnifier above the finger. On a desktop, Tab reaches
      each corner and the arrow keys move it.
- [ ] Before "Analyse card", the quota chip is unchanged. After a scored result it drops by one;
      adding the back does not drop it again.
- [ ] With the quota at zero, `/dashboard/new` shows "You've used this period's checks" with a
      countdown and a link to `/pricing`.
- [ ] A fourth unfinished photo draft is refused with "You have unfinished checks".
- [ ] "Sending us the card instead?" creates a mail-in submission, which shows "Waiting for your
      card" with its reference.
- [ ] The dashboard lists cards by name ("Untitled card" when none), with scores and the customer
      status words; drafts say "Not charged" and "Continue".
```

- [ ] **Step 3: Full checks**

```bash
cd C:/Claude/Projects/ZGrader-first-check-flow/backend
.venv/Scripts/python -m pytest -q > ../../fcf-suite.txt 2>&1; echo exit=$?
cd ../frontend
npx tsc --noEmit && npx next build
```

Expected: `exit=0`, and the tail of `fcf-suite.txt` shows the Task 0 baseline plus the new tests with no failures. `tsc` silent. The build succeeds with `/r/[token]` still `●`. Delete `fcf-suite.txt`.

- [ ] **Step 4: Run the worktree locally.** Stop any preview already on ports 3000/8000 (`preview_list`, then `preview_stop`); they serve the main checkout, not this branch. Write `backend-preview-fcf.sh` into the executing session's scratchpad:

```bash
#!/usr/bin/env bash
# Local backend for browser verification of the first-check-flow worktree ONLY.
# Refuses to start unless the database name ends in _test -- 127.0.0.1:5432 is
# an SSH tunnel to the production Postgres. Never prints the database URL.
set -euo pipefail
url="${ZGRADER_TEST_DATABASE_URL:?ZGRADER_TEST_DATABASE_URL is not set}"
name="${url##*/}"; name="${name%%\?*}"
case "$name" in *_test) ;; *) echo "refusing: '$name' is not a *_test database" >&2; exit 1 ;; esac
export ZGRADER_DATABASE_URL="$url" ZGRADER_ENV=development ZGRADER_SITE_URL=http://localhost:3000
scratch="$(cd "$(dirname "$0")" && pwd)/fcf-preview-data"
mkdir -p "$scratch/scans" "$scratch/reports"
export ZGRADER_SCANS_DIR="$(cygpath -w "$scratch/scans")" ZGRADER_REPORTS_DIR="$(cygpath -w "$scratch/reports")"
cd /c/Claude/Projects/ZGrader-first-check-flow/backend
exec ./.venv/Scripts/python.exe -m uvicorn zgrader.api.main:app --port 8000
```

The test suite's `create_all` built `zgrader_test`, so the schema already has the new columns once Step 3 has run. Add two entries to the `configurations` array of `C:\Claude\Projects\ZGrader\.claude\launch.json`, with `<scratchpad>` replaced by the real path:

```json
    {
      "name": "frontend-fcf",
      "runtimeExecutable": "C:\\Program Files\\nodejs\\node.exe",
      "runtimeArgs": ["C:/Claude/Projects/ZGrader-first-check-flow/frontend/node_modules/next/dist/bin/next", "dev", "C:/Claude/Projects/ZGrader-first-check-flow/frontend"],
      "port": 3000
    },
    {
      "name": "backend-fcf",
      "runtimeExecutable": "C:\\Program Files\\Git\\bin\\bash.exe",
      "runtimeArgs": ["<scratchpad>/backend-preview-fcf.sh"],
      "port": 8000
    }
```

Then run `preview_start` for `backend-fcf` and `frontend-fcf`, and check `preview_logs` for the backend's `database 'zgrader_test'` line.

- [ ] **Step 5: Browser walk.** The user registers the test account in the pane: creating accounts and typing passwords is theirs to do. Then walk every item of the new QA section using photographs from `backend/tests/fixtures/real_scans/`, plus:
  - **Polling:** with a `zgrader_test` submission open, set its status to `processing` in SQL, watch the page show "Analysing…", set it back to `draft_ready`, and confirm the page updates within about 3s with no reload. Local `confirm-crop` is synchronous, so this is the only way to see it.
  - **402 at Analyse:** exhaust the quota in SQL (`quota_used` = limit) after the photo is uploaded, press Analyse, and see the out-of-checks panel rather than a toast. Reload, and confirm the crop was not saved.
  - **Error state:** set a submission's status to `error` in SQL. The page says "We couldn't analyse this photo. It didn't use a check." and never shows `error_message`.
  - **Widths and languages:** at **320, 375, 768, 1024, 1280** in **EN and ES**, on `/dashboard/new` (each state), `/dashboard/{code}` (crop, analysing, review, error) and `/dashboard`:
    - `document.body.scrollWidth === window.innerWidth`
    - every `a, button, [role=slider], summary` is at least 24×24, measured as the union of the element and its descendants, per `frontend/AGENTS.md`
    - Spanish reads back correctly rendered: accents, `·`, `—`
  - Reset the viewport with `resize_window` preset `desktop` when done.

  Report what was exercised and what was not. Screenshot the check page mid-crop and the dashboard.

- [ ] **Step 6: Commit the docs**

```bash
git add AGENTS.md docs/qa_checklist.md
git commit -m "Document the charge-on-score invariant and the photo-check QA pass"
```

---

## Deliberate divergences from the spec

Found while planning. Each is small, and each is stated here rather than left for a reviewer to find.

1. **The quota gate sits before the crop is saved** (spec §4.2 said only "before taking an analysis slot"). Saved crop points would let the worker's poll analyse the draft and charge past the limit — see Task 3.
2. **`ApiError` gains `detail`, and `describeDetail` reads `{message}` objects.** The spec did not mention it, but the page cannot tell a 409 `too_many_drafts` from any other 409 without it. It also fixes the existing 402, which showed customers the bare text "Payment Required".
3. **Dashboard drafts read "Draft" (chip) plus "Not charged" (meta line)**, rather than one "Draft · not charged" string. The status chip is shared with the other states, so the charge note goes beside it.
4. **One responsive list replaces the table** at every width, rather than a table above `sm` and cards below it. One layout has nothing to fall out of step.
5. **`SubmissionView` replaces `detail-client`'s body** and renders both routes. The spec described `CheckFlow` on two routes; the page also needs to become the report without a navigation, so the state lives one level up.
6. **The worker never refuses, so its charge can take an account one over.** This is as the spec says. Noted here because it is the one path where `quota_used` can exceed the limit.

