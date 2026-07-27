# Card Care Center

An independent pre-grading service for trading card games. A customer submits a card, the pipeline
measures centering, corners, edges and surface, and an operator publishes a PDF report estimating
how the major grading companies are likely to treat it.

It is **not** a grading company and must never present itself as one. One operator, self-hosted on
Unraid behind a Cloudflare Tunnel.

| Part | Where | What it does |
|---|---|---|
| API | `backend/zgrader/api/` | FastAPI + SQLAlchemy, Postgres |
| Analysis | `backend/zgrader/analysis/` | OpenCV pipeline: deskew, four categories, crease detection |
| Worker | `backend/zgrader/worker/` | Watches the scans directory, runs the pipeline |
| Reports | `backend/zgrader/reports/` | Jinja + WeasyPrint PDFs, EN/ES |
| Frontend | `frontend/` | Next.js 16 App Router, HeroUI v3, Tailwind v4, EN/ES |
| Proxy | `infra/caddy/` | Single external entry point |

`frontend/AGENTS.md` carries its own warning worth heeding: that Next.js version differs from
training data, so read `node_modules/next/dist/docs/` before writing frontend code.

## Invariants

These were each arrived at the hard way and are cheap to break by accident.

**Scale comes from the card's physical size, never image DPI.** `analysis/scale.py` divides pixels
per card by millimetres per card. A phone photo's EXIF DPI bears no relation to how many pixels
cover the card — using it once reported a 244mm crease on an 88mm-tall card.

**Emails are stored lowercased behind a unique index on `lower(email)`.** Every user lookup must
compare with `func.lower(...)` — see `_find_by_email` in `api/routers/auth.py`. A single
case-sensitive `==` left a production deployment with no operator account, silently, because the
insert it fell through to violated that index and startup swallows seeding errors.

**`token_version` is the only session-revocation mechanism.** It is a JWT claim compared against the
row on every request. Bump it anywhere a credential changes — password reset, password change, admin
password reset — or a stolen token outlives the change meant to kill it.

**The rules engine never predicts a numeric grade for any company.** It emits a severity flag and a
templated reason, nothing more. That is a product and legal boundary, not a modelling limitation;
the same applies to the "not affiliated with" disclaimers, which are generated from the *enabled*
company list so the copy can't name a company the operator switched off.

**Surface analysis is lower-confidence by design and says so publicly.** A flatbed lights the card
diffusely; a grader uses raking light that casts a shadow along a scratch. Faint defects are missed
and printed text is sometimes flagged. Don't remove the caveat — it's load-bearing for trust and it's
on the public `/methodology` page.

**Retuning an analysis threshold means regenerating the published figures.** `/methodology`
describes the detector's behaviour to customers, illustrated by images produced by the real
pipeline. After changing anything in `analysis/`, run
`backend/scripts/generate_methodology_figures.py` — otherwise the page describes software that no
longer exists. `tests/test_methodology_figures.py` fails if the filter stops rejecting text.

**Every setting in `config.py` must be reachable through `docker-compose.yml`.** Compose only
forwards variables named in a service's `environment:` block; anything else in `.env` is invisible
to the container. `tests/test_compose_env_coverage.py` enforces this against an explicit exclusion
list.

## Two traps that have already cost real time

**`localhost` lies about browser security behaviour.** It's a "potentially trustworthy" origin and
is exempt from several protections — notably `upgrade-insecure-requests`, which rewrites every
`http://` subresource to `https://`. A CSP that serves unstyled HTML to every real visitor passes
cleanly on `http://localhost:3000`. Always load the site on its actual hostname or IP before
believing a security header is fine.

**The test database is not the production schema.** `tests/conftest.py` builds it with
`Base.metadata.create_all`, which creates only what the models declare. Indexes created by raw SQL
in migrations — `ix_users_email_lower` in particular — do not exist there, so a class of constraint
violation cannot reproduce under pytest. Check those against a migrated database.

## Running it

Tests need a live Postgres with a `zgrader_test` database:

```
cd backend && source .venv/bin/activate && pytest -q
cd frontend && npx tsc --noEmit && npx next build
```

`npx tsc --noEmit` doubles as the translation completeness check: `Dictionary = Widen<typeof en>`
forces `es.ts` to have the same key structure as `en.ts`, so a missing Spanish string is a type
error rather than a runtime hole.

`docs/qa_checklist.md` is the manual end-to-end walkthrough. `docs/deployment.md` covers the
Cloudflare Tunnel, file ownership on Unraid, and getting into the admin panel.

## Known-open, deliberately

Listed so a review reports something new rather than re-deriving these:

- **SMTP is unconfigured.** The defaults point at a MailHog service that only runs under the `dev`
  compose profile. Since submitting a card requires a confirmed email address, a customer can
  register and then find they cannot use the service at all. This is the most urgent item.
- **No Postgres backups.** Not a code change, and the largest operational gap.
- **The session token lives in `localStorage`**, so an XSS could steal it. Moving it to an
  `httpOnly` cookie means adding CSRF protection and reworking every authenticated image fetch.
- **The free-tier limit is described in the copy but not enforced.** `entitlements.py` has the seam;
  `FREE_TIER_LIMIT` is `None` because the number depends on unsettled pricing.
- **`submission_code` is `COUNT(*) + 1`** (`api/routers/submissions.py`), so deleting a submission
  frees a code the next one will reuse — a unique-constraint 500, and a directory path reused across
  users.
- **No dependency lockfile on the backend.** `pip install .` over unbounded `>=` ranges means each
  image build resolves the newest release of everything, including libraries that parse uploaded
  bytes.
