# ZGrader manual QA checklist

Run this after any change that touches the client portal, admin flow, or the
API/worker contracts they depend on. It walks the same path a real
submission takes end-to-end: client creates a submission, an operator
scans the card and drops the files, the pipeline analyzes it, and an
operator (or auto-publish) gets it in front of the client as a report.

## Setup

1. Postgres running, dev DB migrated and reachable at
   `postgresql://zgrader:zgrader@localhost:5432/zgrader`.
2. Backend API: `cd backend && source .venv/bin/activate && uvicorn zgrader.api.main:app --port 8000`
3. Watcher worker: `cd backend && source .venv/bin/activate && python -m zgrader.worker.main`
4. Frontend: `cd frontend && BACKEND_URL=http://localhost:8000 npm run dev -- --port 3000`
5. Open `http://localhost:3000`.

## Client flow

- [ ] Landing page loads, describes the service, has working "Get started" /
      "Log in" links.
- [ ] Register a new client account. Redirects to the dashboard, empty state
      shown with a link to create the first submission.
- [ ] Create a submission (pick a game, name, set, card number, foil).
      Redirects to the submission detail page, status `Created`.
- [ ] Confirm a folder named after the submission code now exists under the
      configured scans directory.
- [ ] Copy a front+back scan pair (e.g. from
      `backend/tests/fixtures/sample_scans/`) into that folder, named with
      `front`/`back` in the filename.
- [ ] Within ~worker debounce + poll interval, reloading the submission page
      shows status `Draft ready`, a populated scorecard (Centering, Corners,
      Edges, Surface -- Surface tagged "lower confidence"), and a
      multi-company comparison table covering **all four categories**
      (a regression here means the centering-row generation bug is back --
      see `zgrader/analysis/pipeline.py`'s `_persist_combined`).
- [ ] "Download report" is not shown yet (report isn't published).

## Admin flow

- [ ] Log in as an operator account (operators aren't self-registrable --
      create one directly in the DB with `role=operator`). Login redirects
      to `/admin`, not `/dashboard`.
- [ ] Admin overview shows stats (total submissions, draft ready count,
      published reports) and lists the submission created above.
- [ ] Open the submission's admin detail page. Auto-publish selector shows
      "Inherit global default"; changing it to "Force on"/"Force off" and
      reloading persists the choice.
- [ ] Click "Approve & publish". Status flips to `Published`, a success
      message shows, and the PDF becomes downloadable from this page too.
- [ ] Visit `/admin/settings`, change the business name/contact/disclaimer,
      save, reload -- changes persisted.

## Client sees the result

- [ ] Log back in as the client. The submission now shows status
      `Published` and a "Download report" button.
- [ ] Download the report. It opens as a valid PDF with: header/branding,
      the scorecard, annotated front/back images per category, the
      multi-company comparison table (all 4 categories), and the
      limitations/disclaimer section.

## Auto-publish path (skips the manual approve step)

- [ ] In `/admin/settings`, enable "Auto-publish new submissions by
      default" (or set the override to "Force on" on a specific
      submission).
- [ ] Create a new submission, drop scans into its folder as above.
- [ ] Once the worker processes it, status should go straight to
      `Published` without an operator visiting `/admin/[code]`.

## Cross-cutting checks

- [ ] A client cannot see or open another client's submission (try the
      submission-detail URL directly while logged in as a different
      client -- expect a 403/redirect, not the data).
- [ ] A non-operator hitting `/admin` gets redirected away.
- [ ] Backend test suite passes: `cd backend && source .venv/bin/activate && pytest -q`.
- [ ] Frontend type-checks and builds cleanly: `cd frontend && npx next build`.
