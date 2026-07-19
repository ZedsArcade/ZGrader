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
5. (Optional, for testing notification emails) a local SMTP catcher on
   `localhost:1025`, matching the backend's defaults -- e.g.
   `python3 -m smtpd -n -c DebuggingServer localhost:1025`, which prints
   received mail to stdout. Without one, email sending fails silently (by
   design -- see `zgrader/email/client.py`) and everything else still works.
6. Open `http://localhost:3000`.

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
- [ ] If an SMTP catcher is running, a "Submission received" email arrived
      the moment the submission was created (not later).

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
- [ ] If an SMTP catcher is running, a "Your report ... is ready" email
      arrived at the moment of publish.
- [ ] Visit `/admin/settings`, change the business name/contact/disclaimer,
      save. **The NavBar brand text updates immediately, without a page
      reload** (a regression here means `BrandingProvider`'s `refresh()`
      wiring broke -- see `lib/branding-context.tsx` and
      `app/admin/settings/page.tsx`). Reload and confirm the change
      persisted.
- [ ] Visit `/admin/audit-log`. The approve action from above appears with
      the correct submission code, operator email, and a `report_version`
      detail. Pagination ("Newer"/"Older") doesn't error on an empty page.

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

## Docker Compose deployment (homelab)

The `docker-compose.yml`, both `Dockerfile`s, and `infra/caddy/Caddyfile` are
syntax-validated (`docker compose config`) but were **not** run end-to-end
with a live daemon during development -- the sandbox this was built in can't
run nested Docker. Treat the steps below as the first real test of the
container path, not a formality:

1. `cp .env.example .env` and fill in real values (`ZGRADER_SECRET_KEY`
   especially -- generate with
   `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`).
   Set `SCANS_HOST_PATH` to wherever your scanner actually writes.
2. `docker compose --profile dev up --build` (the `dev` profile adds
   mailhog at `http://localhost:8025` so notification emails have
   somewhere to go without a real SMTP relay).
3. Confirm all containers reach a healthy/running state: `postgres`,
   `migrate` (should exit 0, not stay running), `backend`, `worker`,
   `frontend`, `mailhog`.
4. Hit `http://localhost:3000` directly, and separately
   `http://localhost` (via Caddy) -- both should serve the same app.
5. Walk the full client/admin flow above against the Dockerized stack.
6. Drop a real scan pair into `${SCANS_HOST_PATH}/<submission-code>/` from
   the host filesystem (not from inside a container) to confirm the bind
   mount actually round-trips files the way a real scanner would.
7. For production use, either point `ZGRADER_SMTP_*` at a real relay and
   drop the `dev` profile (no mailhog), or swap the `Caddyfile`'s `:80`
   site block for a real domain name to get automatic HTTPS -- see the
   comments in `infra/caddy/Caddyfile`.
