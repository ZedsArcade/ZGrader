# First check flow — design

**Date:** 2026-09-13
**Status:** draft for review — no code until this is approved and turned into a plan
**Covers:** the first sub-project of the UI/UX pass — a customer getting from "new check" to a result
without losing a check, a photo or their place. Report layout, sharing and marketing copy are later
sub-projects (§10).

---

## 1. What the walkthrough found

The live site was in maintenance, so the walk ran against a local stack (frontend + backend on
`zgrader_test`). Public pages were seen rendered at desktop and 375px; the signed-in pages were read in
code, not rendered. Findings this spec acts on:

| # | Finding | Where |
|---|---|---|
| F1 | A check is spent at **Create submission**, before any photo exists. Abandoning at upload, or a photo that never crops, still costs one. | `create_submission` → `entitlements.consume_submission` |
| F2 | The form asks for game, name, set and number before the photo — the thing the customer came to do — and its subtitle says "ship it to us for scanning". | `app/dashboard/new/page.tsx`, `newSubmission.subtitle` |
| F3 | The crop editor sits in half of a two-column grid on desktop, has no magnification under a finger, handles are pointer-only, and rotate buttons are bare glyphs. | `UploadStep`, `CropAdjustStep` |
| F4 | `<input capture>` opens the camera directly on Android, with no way to pick a photo already taken. | `UploadStep.ScanSlot` |
| F5 | `ProcessingState` never polls: a page that lands mid-analysis stays there until reloaded. | `ProcessingState`, `detail-client.tsx` |
| F6 | `error` has no customer branch — the page falls through to an empty overview, and uploads are refused from `error`, so it is a dead end. | `detail-client.tsx` |
| F7 | Customers see operator vocabulary: "Draft ready", "Awaiting scans", "Error", and a page titled with the sequential submission code. | `StatusBadge`, `detail-client.tsx` |
| F8 | The dashboard list is code, status and date — ten submissions are indistinguishable. | `SubmissionSummary` (both ends) |
| F9 | An unverified account learns it cannot submit from a 403 toast after filling the form. | `require_verified_user` |
| F10 | `QuotaChip` links to `/services`, which still says paid tiers are "coming soon". | `QuotaChip.tsx` |

## 2. Decisions made during brainstorming

| Question | Decision |
|---|---|
| Which sub-project first? | First check succeeds (this spec). |
| When is a check charged? | **When an analysis first produces a score.** Pipeline errors and all-declined results are free. Deleting never refunds. |
| Flow shape | **One page, photo-first.** Only game and foil are needed before analysis; name, set, number are optional labels. |
| Architecture | **Draft submissions**: the first upload quietly creates an uncharged submission and every existing upload/crop endpoint is reused. Rejected: client-side staging (every crop helper would need a stateless variant re-uploading the photo — a second image entry point for the EXIF/metadata invariants); draft on page open (many empty drafts). |
| Draft limits | At most **3** open photo drafts per account; untouched photo drafts deleted after **7 days**, files included. |
| Worker charging | Operator drops are never refused; they charge under the same rule and may take an account one over. |
| "Submission received" email | Sent only for mail-in submissions, where it tells the customer their reference. Not for photo drafts. |
| Back photo | Asked for **after** the front result, not beside it. |
| Mail-in | A secondary **"Sending us the card instead?"** link on the page. Mail-in rows carry a flag and are exempt from the draft cap and sweep. |
| Status words | Customers get their own labels; the admin keeps the operator ones. |
| Polling during review | None — the "report published" email covers a wait measured in hours. |

## 3. Principles this design establishes

These become AGENTS.md invariants when the work lands.

1. **A submission is charged once, the first time an analysis gives it a score, and never refunded.**
   `submissions.charged_at` records it. The charge is a conditional update (`WHERE charged_at IS NULL`)
   and `consume_submission` runs only if that update touched a row, so the API and the worker racing on
   one submission cannot charge twice.
2. **The charge lives in `_advance_submission`, not in `run_analysis` and not in a caller.** Both paths
   that run analysis for a customer end there, so they charge identically. `run_analysis` stays ignorant of
   billing; `dev_trigger`, which calls it directly, stays free.
3. **"Scored" means at least one combined `AnalysisResult` with a non-null `raw_score`**, queried from the
   database after `run_analysis` returns — not read from relationship collections, which the pipeline's
   bulk deletes leave stale.
4. **A refusal that depends on the caller stays at the API boundary**, as `api/capacity.py` already
   argues: `confirm-crop` refuses with 402; the worker never refuses.
5. **The customer is told about a block before they act on it, not after.** Unverified email and
   exhausted quota are the page's first state, not a toast after the work is done.

## 4. Backend

### 4.1 Schema (one migration)

| Change | Detail |
|---|---|
| `submissions.charged_at` | `timestamptz NULL`. **Backfilled to `created_at` for every existing row** — every existing submission was charged at create, and leaving them NULL would charge them again on the next re-analysis. |
| `submissions.mail_in` | `boolean NOT NULL DEFAULT false`. No backfill needed: every existing row is charged, and the cap and sweep only look at uncharged rows. |
| `cards.card_name` | Becomes `NULL`able. |

`tests/test_migrations.py` runs the chain; the backfill gets its own assertion there.

### 4.2 Charging

- `create_submission` keeps its `can_submit` check and 402 — an exhausted account should not open drafts —
  but **no longer calls `consume_submission`**.
- `confirm-crop` refuses with the same 402 payload **before** taking an analysis slot when the submission
  is uncharged and `can_submit` is false. The per-user cap of one analysis already serialises one
  account's confirms, so check-then-charge cannot be raced into overspending from the API.
- `_advance_submission`, after `run_analysis` succeeds and before either commit: if the submission is
  scored (§3.3), run the conditional update; if it touched a row, `consume_submission(db, user)` and add
  `AuditLog(action="check_charged")`. A `PipelineError` path never charges.
- Charging happens in the same transaction as the status change it accompanies, so a crash leaves
  neither.

### 4.3 Creating a submission

`SubmissionCreate`:

- `card_name: str | None` (`max_length=200`; an empty string normalises to `None`).
- `mail_in: bool = False`. When true, `card_name` is required (422) — the operator matches a physical
  card by it.
- Everything else unchanged.

Before creating an **uncharged photo draft** (`mail_in` false), count the account's submissions with
`charged_at IS NULL AND mail_in = false AND status IN (created, awaiting_scans)`. At
`config.max_open_drafts` (default 3) refuse with **409** and
`{"message": "You have {n} unfinished checks. Finish or delete one to start another.", "code":
"too_many_drafts"}`. The frontend renders its own translated copy keyed on `code` and uses the message
only as a fallback. Operators are exempt.

`send_submission_received` fires only when `mail_in` is true.

### 4.4 Editing card details

`PATCH /submissions/{code}/card`, owner only, `CardUpdate` with `extra="forbid"` and every field optional:
`card_name`, `set_name`, `card_number`, `foil`.

- Name, set and number are editable in any status. They are labels; nothing measured depends on them.
- `foil` is editable only while the submission is `created` or `awaiting_scans`, and 409 afterwards. It
  changes the result (`assessment.CARD_IS_FOIL`), so changing it after analysis would put a stale
  assessment beside a new declaration.
- Carries `rate_limit("card_update", limit=60, window_seconds=3600)`, in line with
  `_confirm_crop_limit`'s hourly shape. `tests/test_rate_limit_coverage.py` fails without one.

### 4.5 Stale drafts

`purge_stale_drafts(db)` in `worker/main.py`, called from `_sweep_retention` beside
`purge_expired_contact_messages`:

- Selects `charged_at IS NULL AND mail_in = false AND status IN (created, awaiting_scans)` whose
  **last activity** is older than `config.draft_retention_days` (default 7). Last activity is
  `GREATEST(submissions.updated_at, MAX(scan_images.updated_at))`. Both come from `TimestampMixin`,
  whose `onupdate` fires only when that row is written. Uploading a photo writes a `ScanImage`, not the
  submission, so keying on the submission alone would sweep a draft someone photographed yesterday.
- For each: `purge_submission_files(code)`, then delete the row. The cascades in AGENTS.md make the row
  delete complete.
- Files go **before** the row. The row names the directory, so failing after a row delete would orphan
  files nothing can find. A failed file purge leaves the row for the next pass.

If `Submission` has no `updated_at`, the implementation plan adds one in the same migration rather than
keying off `created_at`. A customer resuming a draft on day 6 must not lose it on day 7.

### 4.6 Summary payload

`SubmissionSummary` gains `card_name: str | None`, `game: str`, `mail_in: bool`, `charged: bool`, and
`scores: dict[str, float | None]` — the four combined category scores, `None` where unmeasurable.
`list_submissions` loads cards and results with `selectinload`, and a test counts queries, so the list
cannot turn into one query per row.

`SubmissionDetail` gains `charged: bool` and `mail_in: bool`. `schemas/public_report.py` is explicit and
not touched, so `test_public_payload_key_allowlist` is unaffected.

### 4.7 Settings

`ZGRADER_MAX_OPEN_DRAFTS` (3) and `ZGRADER_DRAFT_RETENTION_DAYS` (7) in `config.py`, and forwarded in
`docker-compose.yml` as `${VAR:-default}`. `tests/test_compose_env_coverage.py` enforces the second half.

## 5. Frontend — the check page

### 5.1 One component, two addresses

A new `CheckFlow` client component renders on two routes:

- **`/dashboard/new`**, where no submission exists yet.
- **`/dashboard/[code]`**, while the front is unconfirmed. It replaces the `UploadStep` branch in
  `detail-client.tsx`.

When the first photo creates the draft, `window.history.replaceState(null, "", "/dashboard/{code}")`
changes the address without remounting. The Next 16 docs confirm this integrates with the router
(`01-getting-started/04-linking-and-navigating.md`, "Native History API"). Back then leads to the
dashboard. A reload renders the same component from `scan_sides`/`confirmed_sides`, which is resuming
mid-crop by construction.

### 5.2 The screen, top to bottom

1. **Block states first.**
   - Unverified (`user.is_verified` false): "Confirm your email to run a check", with a **Resend** button
     calling `resendVerification`.
   - Exhausted quota: the reset countdown (the formatter moves out of `QuotaChip` so both can use it) and a
     link to `/pricing`.
   - Otherwise, one line: "Uses 1 of your {count} remaining checks, only if we can score it." The number
     comes from `useQuota`, never the copy. It is hidden for unlimited plans, as `QuotaChip` already is.
2. **Game**, defaulting to the last game used (`localStorage`, wrapped in try/catch, falling back to the
   first game in the list).
3. **Photo.** The contrast hint sits above two buttons:
   - **Take photo**: `capture="environment"`.
   - **Choose photo**: no `capture` (F4).
4. **Picking a photo**: create the draft (game, `foil: false`, no name), upload, `replaceState`, and the
   crop editor appears in place, full column width (F3).
5. **Under the editor:**
   - **Foil** checkbox, with one line on why it matters.
   - **Card details (optional)**, collapsed: name, set, number.
   - Primary button **Analyse card**. On press, send `PATCH /card` if any of those fields changed, then the
     existing check → confirm sequence.
6. **Analysis errors:**
   - 402 shows the exhausted state inline.
   - 409 `too_many_drafts` (create only) links to the dashboard's drafts.
   - 503 and 409 already-running keep their current wording.
7. **After confirm** the page becomes the result (§6). The back is offered there with the same two
   buttons and the same editor.
8. **Mail-in.** A quiet "Sending us the card instead?" link swaps the photo step for today's details form,
   with name required. Its create sends `mail_in: true`.

### 5.3 The crop editor

`CropAdjustStep` keeps its contract. Its suggest, snap, check and confirm calls, the 44px hit area around
the 24px dot, and the edges-not-found warning with Adjust / Submit anyway are all unchanged. What changes:

- **Magnifier while dragging with touch** (`pointerType === "touch"`). A ~120px circle at 3× sits above
  the finger, with a crosshair on the corner. It is drawn as a CSS background from the same blob URL, so
  there is no extra fetch. It is hidden for mouse and pen, where nothing covers the corner.
- **Handles become focusable buttons**, labelled "Top-left corner" and so on. Arrow keys move them 0.5% of
  the image, 2% with Shift. Previously they were pointer-only.
- **Rotate buttons get visible labels** ("⟲ 1°" / "1° ⟳"), keeping their `aria-label`s.

## 6. Frontend — after analysis

### 6.1 Waiting

While status is `processing`, the detail page polls `GET /submissions/{code}`:

- Every 3s for the first minute, then every 10s.
- Paused while `document.hidden`, resumed on `visibilitychange`.
- Stopped at any other status.
- After 10 minutes it stops and shows "Still working — we'll email you when it's done."

The worst case is about 100 of the `submission_read` allowance's 300 per 5 minutes. There is no polling in
`awaiting_scans`, which is a mail-in waiting on post, or in `draft_ready`, which is waiting on review.

### 6.2 Status words

`StatusBadge` takes `audience: "customer" | "operator"`, defaulting to `"operator"` so admin call sites
do not change.

| State | Customer label |
|---|---|
| uncharged photo draft (`created`/`awaiting_scans`) | Draft |
| mail-in `created`/`awaiting_scans` | Awaiting your card |
| `processing` | Analysing |
| `draft_ready` | Results ready · in review |
| `approved` | Results ready · in review |
| `published` | Report ready |
| `error` | Couldn't analyse |

### 6.3 Review, error and header

- **`draft_ready`.** A banner above the scores: "Your results are below. We check every report before the
  PDF and share link unlock — you'll get an email." `SharePanel`'s unpublished copy says the same. For a
  front-only check, the add-the-back card moves directly under the scores.
- **`error`** (F6) gets its own branch:
  - "We couldn't analyse this photo. It didn't use a check." For a charged submission, the second sentence
    is dropped: the error came from a re-analysis after one that scored.
  - The two tips that resolve most failures: contrast, and a crop traced tightly around the card.
  - **Try another photo**, linking to `/dashboard/new`.
  - **Delete**.

  `error_message` is never shown to customers; it is internal exception text.
- **Header.** The title is the card name, or "Untitled card" with an **Add name** link opening the same
  details editor. The code moves to a small muted "Ref {code}" line.

### 6.4 Dashboard list

- Each row shows:
  - the card name (or "Untitled card"), as a link covering the whole row
  - game · date
  - the customer status chip
  - a four-score strip in the existing `gradeTierClass` colours, with "—" for `null`
- Uncharged photo drafts read "Draft · not charged" and offer **Continue**.
- Below `sm` the rows are stacked cards, not a table scrolling sideways.
- The empty state is unchanged.

`QuotaChip` links to `/pricing` (F10).

## 7. Copy

- All new strings go in `lib/i18n/en.ts` and `es.ts`. `npx tsc --noEmit` is the completeness check.
- Figures come from `useQuota` placeholders, never the copy.
- The stale strings go: `newSubmission.subtitle`'s shipping line, and `upload.title` "card scans".
- Spanish is read back rendered in a browser. Dates and lists pass `locale` explicitly
  (`frontend/AGENTS.md`).

## 8. Testing and verification

**Backend (pytest, `zgrader_test`)**

- `test_api_quota.py` is rewritten around the new trigger.
- Its intent is kept: refusal leaves nothing behind, deleting never refunds, unlimited plans are never
  refused, the window rolls forward, and an unknown plan falls back to free.
- New tests:
  - A draft is not charged by creating or uploading.
  - A scored front confirm charges once.
  - Adding the back does not charge again.
  - An all-declined result is free, and a later scored run charges.
  - A `PipelineError` is free.
  - 402 at `confirm-crop` leaves the draft intact.
  - The conditional update charges once when run twice.
  - The worker path charges and never refuses.
  - The draft cap, including the mail-in and operator exemptions.
  - `mail_in` requires a name.
  - The foil lock on `PATCH /card`.
  - The sweep removes files and row, leaves mail-in and charged rows alone, and keeps the row when the file
    purge fails.
  - The summary fields and the query count.
- `test_migrations.py` asserts the backfill.

**Frontend**

- `npx tsc --noEmit` and `npx next build`.
- A browser walk against the local backend on `zgrader_test`, using photographs from `real_scans/`:
  - The new-check page end to end, including a reload mid-crop.
  - Unverified, exhausted, 402-at-analyse and `too_many_drafts`.
  - The magnifier under touch emulation.
  - Keyboard handles.
  - Mail-in create.
  - The error and review states.
  - Polling, by moving a `zgrader_test` row into and out of `processing`, since local `confirm-crop` is
    synchronous.
- Every screen in **EN and ES at 320, 375, 768, 1024 and 1280**, signed in: no horizontal scroll, and no
  target under 24×24 measured as `frontend/AGENTS.md` describes.

## 9. Files expected to change

**Backend**
- `models/submission.py`
- `models/card.py`
- a new Alembic migration
- `schemas/submission.py`
- `api/routers/submissions.py`
- `worker/watcher.py` (`_advance_submission`)
- `worker/main.py`
- `config.py`
- `docker-compose.yml`
- `tests/test_api_quota.py`, plus new test modules

**Frontend**
- `app/dashboard/new/page.tsx`
- `app/dashboard/[code]/detail-client.tsx`
- `app/dashboard/page.tsx`
- a new `components/CheckFlow.tsx`
- `components/CropAdjustStep.tsx`
- `components/UploadStep.tsx` (reduced to the back-photo case, or folded into `CheckFlow`)
- `components/ProcessingState.tsx`
- `components/StatusBadge.tsx`
- `components/SharePanel.tsx`
- `components/QuotaChip.tsx`
- `lib/api.ts`
- `lib/i18n/en.ts`
- `lib/i18n/es.ts`

**Docs**
- `AGENTS.md`: the §3 invariants.
- `docs/qa_checklist.md`: the new-check walkthrough.

The neighbouring `corner-mask-design` spec changes `preprocessing.rectify` and the corners category.
Neither is touched here.

## 10. Not in this sub-project, and why

| Left out | Why |
|---|---|
| Report top-line summary, compact company tables, share panel placement | Sub-project 2 (report & sharing). |
| Mail-in wording on the landing page, `/services` vs `/pricing`, the 36 literal `--` in `en.ts`, sample report on the landing page | Sub-project 3 (marketing & pricing). |
| A published promise that a check is only used when scored | Terms §7 is silent on when a check is used, so nothing breaks. Promising it publicly would need a test tying copy to behaviour, and belongs with the pricing copy. |
| Quoting the 7-day draft deletion in the privacy policy | Deleting unanalysed photos sooner only reduces what is held; nothing published is contradicted. Revisit with sub-project 3. |
| Thumbnails in the dashboard list | Every row would need an authenticated image fetch and blob URL. The name and scores already distinguish rows. |
| Lifetime / credit-pack allowances | Unchanged; AGENTS.md's known-open entry stands. |
