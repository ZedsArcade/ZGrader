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

**Scale comes from the card's physical size, never image DPI.** A phone photo's EXIF DPI bears no
relation to how many pixels cover the card — using it once reported a 244mm crease on an 88mm-tall
card. `preprocessing.rectify` now enforces this by construction: it *builds* the card raster at a
chosen px/mm from the known millimetre dimensions, so the scale is definitional rather than
measured back off the image. `analysis/scale.py`'s `px_per_mm` is the older measured form, still
correct but no longer on the analysis path.

**Measurement geometry comes from fitted card edges, never from the customer's crop.**
`analysis/geometry.py` fits a RANSAC line to each side — excluding a margin at both ends, so
intersecting adjacent lines recovers the *ideal* apex even where a corner is chipped — and
`preprocessing.rectify` warps to those apexes. `ScanImage.crop_points` is passed in as a
region-of-interest hint and nothing more. It used to be the geometry itself, which made every
number a function of where four handles were dragged: a crop half a millimetre inside the card
removed the damage from the image before any detector saw it.

**When the fit falls back, every category declines rather than scoring.** The result carries
`GEOMETRY_UNVERIFIED` and `assessment.apply_external_limitations` strips the score outright — see
`assessment.DISQUALIFYING_LIMITATIONS`. It used to halve confidence instead, which was not enough:
across 30 real photographs the fit fell back on 10, and on those the mean corners score was 9.04
against 7.79 where it held. **The broken path scored 1.26 points higher**, because a desk has no
corner wear and no edge whitening — `2_FarStandardShot` reported corners 10.00 and edges 9.88 off a
raster that was mostly desk. A halved confidence on a 10.00 is still a published 10.00, and the
error is biased *upward*, so every one of these failures flattered the card.

Two things follow. The fallback must never become silent. And the synthetic fixtures cannot protect
this: **all 23 fit cleanly with zero geometry limitations**, so the drift baseline does not move
when this behaviour changes — `tests/test_geometry_disqualifies.py` is the safety net, not
`fixture_drift.py`. `fixture_metrics` applies the same call as `pipeline._persist_side` for the same
reason; when it did not, the harness measured a pipeline that does not ship.

The crop is the dominant variable and the customer controls it. Uncropped, the fit falls back on
33% of real photographs; with a crop traced tightly around the card that floor is 7% (2 of 30 fail
at every crop tightness). 8 of the 10 failures are recovered by re-cropping alone, which is why the
`geometry_unverified` copy leads with "fix the crop" rather than "retake the photo". A crop traced
around the card has never broken a fit that worked without one — the five apparent regressions in
the first measurement were an artefact of simulating crops as centred rectangles, which clip a card
that is off-centre.

**A threshold calibrated against the synthetic fixtures has been wrong on real photographs every
single time it was checked.** Thirty photographs of seven real cards found five bugs that
twenty-three synthetic fixtures could not, and each was the same shape: a confident number with
nothing behind it. Detection reported the whole photograph as the card; corners measured 24mm² of
"material loss" against a desk; diamond-cut tilt read 14mm on a 63mm card. Synthetic content is
unnaturally clean — flat fills, no paper fibre, no holo, one connected component in a variance mask
where a real photo has 237–1183 — so any threshold tuned on it is tuned against the easy case.
Not always in the same direction, either: some were too sensitive, and one case had no signal at all
where no threshold setting would have helped. **Before believing a new constant, run
`scripts/fixture_drift.py` and read the real-photo block at the bottom.**

**A quantity whose noise is comparable to its scoring range must not be scored.** Diamond-cut tilt
was measured, scored, demonstrated with its own fixture — and then repeat photographs of one
unchanging card showed it reading 0.18–1.43mm, about 1.2mm of noise against a 1.5mm range. It is now
measured and reported but contributes nothing to any score (`scoring.CENTERING_TILT_SCORED`). The
same reasoning set `scoring.CORNER_AREA_NOISE_FLOOR_MM2`. Reporting a difference smaller than the
noise that produced it is false precision, and it biases every number downstream in one direction.

**When a category gains the ability to decline, something downstream assumes it cannot.** Since
`raw_score` became nullable this has surfaced four times: the Pydantic response schema (reached
production as a 500 on every request for the affected submission), the drift harness's reporting,
`fixture_metrics`, and `recompute`. The guard in `recompute._adjusted_side_score` is written against
the assessment *state* rather than per category so the fifth is covered. Grep for `raw_score` before
adding a fifth declining path.

**Emails are stored lowercased behind a unique index on `lower(email)`.** Every user lookup must
compare with `func.lower(...)` — see `_find_by_email` in `api/routers/auth.py`. A single
case-sensitive `==` left a production deployment with no operator account, silently, because the
insert it fell through to violated that index and startup swallows seeding errors.

**`token_version` is the only session-revocation mechanism.** It is a JWT claim compared against the
row on every request. Bump it anywhere a credential changes — password reset, password change, admin
password reset — or a stolen token outlives the change meant to kill it.

**Deleting a submission cascades in the database, and it has to.** Every foreign key pointing at
`submissions` is `ON DELETE CASCADE` (`audit_logs.submission_id` is `SET NULL` — the history is
worth keeping when the submission is not), and the relationships carry `passive_deletes=True` so
the ORM stands back and lets Postgres do it.

That is not a tidiness preference. It used to be `NO ACTION` with the cascade living only in the
SQLAlchemy relationship, which works exactly as long as nothing else is writing: the ORM reads the
children, deletes them, then deletes the parent, and anything inserting in between strands a row and
fails the parent delete. **Two things do write.** `confirm-crop` runs the pipeline inside the API
request, and the worker runs it too, driven by a watchdog on the scans directory and a poll loop
over `created`/`awaiting_scans` submissions — with nothing serialising them. That reached production
as a 500 on delete, and because the submission kept being re-picked up it failed on every retry
rather than once. `tests/test_submission_delete_cascade.py` reproduces it with a second session,
which is the only way to see it: a single-session test passes against the broken schema, because the
ORM cascade handles what it can see.

So a plain `DELETE FROM submissions` is now correct and atomic. What is still *not* in the database
is the files: the scans and reports directories go only through `purge_submission_files(code)`, so
SQL deletion orphans them on disk and they must be cleaned up on the host. Prefer the app's own
delete endpoint, which does both.

Deleting submissions no longer risks reissuing a code — `_next_submission_code` draws from
`submission_code_seq`, and a sequence never goes backwards, so a partial delete is as safe as a
full one. (It used to be `COUNT(*) + 1`, where deleting *some* submissions handed the next one a
code that was still live.) But a bulk delete resets no counter anywhere else, so `users.quota_used`
has to be zeroed explicitly or the customer is still charged for submissions that no longer exist;
set `quota_period_started_at = NULL` alongside it so the next submission anchors a fresh window
rather than resuming an expired one.

**Re-running analysis replaces the previous assessment, and `run_analysis` is the only thing that
may guarantee it.** Nothing in the persistence path upserts — `_persist_side` and
`rules_engine.evaluate` both insert fresh rows — so the delete is what stops a rerun stacking a
second complete set on top of the first. That cleanup used to live in `worker/watcher.py` behind a
`status == draft_ready` check, which covered exactly one of the ways analysis gets re-run:
`dev_trigger` never cleaned up and neither did a rerun from the error state, and one production
submission reached three sets. Anything that reads the newest row hides it; anything that
aggregates would multiply-count. Put per-submission cleanup in the pipeline, never in a caller —
`tests/test_reanalysis_replaces_results.py` calls `run_analysis` directly for that reason. The
deletes are bulk, so they bypass the identity map and the relationship collections must be expired
afterwards, or `_persist_combined` and `rules_engine.evaluate` read rows that no longer exist.

**The rules engine never predicts a numeric grade for any company.** It emits a severity flag and a
templated reason, nothing more. That is a product and legal boundary, not a modelling limitation;
the same applies to the "not affiliated with" disclaimers, which are generated from the *enabled*
company list so the copy can't name a company the operator switched off.

**Surface analysis is lower-confidence by design and says so publicly.** A flatbed lights the card
diffusely; a grader uses raking light that casts a shadow along a scratch. Faint defects are missed
and printed text is sometimes flagged. Don't remove the caveat — it's load-bearing for trust and it's
on the public `/methodology` page.

**Every change under `analysis/` must be checked for per-fixture drift.** `scripts/fixture_drift.py`
runs 23 synthetic fixtures — bordered, full-art, foil, white-bordered, damaged, and deliberately bad
captures — through the detectors and diffs them against `tests/fixtures/drift_baseline.json`.
`tests/test_fixture_drift.py` fails if anything moved, so it can't be forgotten. When a change is
intended, `python scripts/fixture_drift.py --update` records it, and the resulting baseline diff is
the reviewable statement of what the change did to each kind of card. This matters because an
aggregate score hides the interesting case: a retune that sharpens bordered cards while wrecking
full-art centering reads as an improvement until someone looks per fixture.

Fixtures must stay deterministic — seed any noise — or the baseline reports drift that isn't there
and everyone learns to ignore it.

The same harness also measures anything in `backend/tests/fixtures/real_scans/` and prints it
**without baselining it** — real photographs should move as the pipeline improves, and a test
demanding they stay fixed would punish the work it was meant to protect. That directory is empty in
a fresh clone: the operator's own photographs are deliberately not committed, because the repo is
public. Ask for them before concluding the pipeline is fine, and see that directory's README for
what to shoot. Nearly every finding in the last round came from photographing *one card several
times* — the card cannot change between shots, so all the variation is measurement error.

**Retuning an analysis threshold means regenerating the published figures.** `/methodology`
describes the detector's behaviour to customers, illustrated by images produced by the real
pipeline. After changing anything in `analysis/`, run
`backend/scripts/generate_methodology_figures.py` — otherwise the page describes software that no
longer exists. `tests/test_methodology_figures.py` fails if the filter stops rejecting text.

**Every setting in `config.py` must be reachable through `docker-compose.yml`.** Compose only
forwards variables named in a service's `environment:` block; anything else in `.env` is invisible
to the container. `tests/test_compose_env_coverage.py` enforces this against an explicit exclusion
list.

## How the analysis pipeline fits together

Read in this order; each module depends on the one above it.

| Module | Owns |
|---|---|
| `preprocessing.rectify` | The entry point. Detects the card, fits its geometry, warps to a canonical raster built at a known px/mm from the card's physical size. Returns image, scale, geometry and a **card mask** in that same raster. |
| `geometry.py` | RANSAC line per side with a 12% corner margin excluded, sub-pixel refinement by parabola-fitting the gradient peak along each normal, apexes from intersecting adjacent lines. The margin is what makes an apex *extrapolated*, so a chipped corner has a known ideal tip to measure loss against. |
| `border.py` | Where the printed border ends. Shared by edges (to place its reference) and centering (because it *is* the measurement). Extracted precisely so the two cannot drift apart. |
| `capture.py` | Sharpness, resolution, clipping, illumination uniformity. **Only `px_per_mm` gates anything** — the other three track what is *printed* on the card as strongly as how it was photographed, so no absolute threshold works. |
| `assessment.py` | The output contract: `measured`/`unmeasurable`, confidence, interval, limitation **codes**. `EXTERNAL_LIMITATION_FACTORS` is the hook for anything established once per card rather than per category (geometry provenance, foil). |
| `scoring.py` | Every measurement→score mapping, each tagged DERIVED / REASONED / ARBITRARY. **Every consumer must route through it** — `recompute.py` is the one that keeps forgetting, twice now. |

Two structural rules that keep being re-learned: a category that cannot measure something returns
`raw_score = None` rather than a low score, and `build_regions` plus `_annotate_category` both key
off that being `None` so an unscored category draws no overlay and emits no findings — every region
severity is a claim, and `ok` asserts that part of the card was checked and is clean.

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

**The migrations themselves are covered, but only by `tests/test_migrations.py`.** It runs the real
chain against its own scratch database, because for six merges nothing did. `b7f4c2e19a83` shipped
using `sa.Enum(..., create_type=False)` — `create_type` belongs to `postgresql.ENUM`, and the
generic `sa.Enum` **accepts and silently ignores it** — so `create_table` re-emitted `CREATE TYPE`
for an enum the migration had just created. Alembic runs a migration in one transaction, so the
failure rolled back completely: no table, no type, `alembic_version` unmoved. It looked like the
migration had never run rather than that it had failed.

The blast radius was the whole stack, not just the feature. `migrate` never completed, and
`backend` and `worker` both wait on `service_completed_successfully`, so neither started — nor did
anything downstream of them. Every redeploy had to be followed by starting containers by hand,
because a manual start ignores `depends_on`. The symptom looked nothing like the cause.

Alembic has to run in a **subprocess** in those tests. `alembic/env.py` sets the URL from
`zgrader_config.database_url`, a singleton built at import time, so an in-process run ignores the
URL it is handed and migrates the *test* database instead — which the first version of that file
duly did.

## Running it

Tests need a live Postgres with a database whose name **ends in `_test`**:

```
cd backend && source .venv/bin/activate && pytest -q
cd frontend && npx tsc --noEmit && npx next build
```

`ZGRADER_TEST_DATABASE_URL` overrides the default
(`postgresql+psycopg://zgrader:zgrader@localhost:5432/zgrader_test`), which is how the suite runs
against the deployed Postgres instead of a local one. Compose binds Postgres to the host's loopback
only, so reach it over a tunnel:

```
ssh -N -L 5432:127.0.0.1:5432 <host>
```

**The suite is destructive and guards itself accordingly.** It drops every table at session start,
deletes every row after each test, and removes the scans and reports directories after each test.
Two guards in `tests/conftest.py` keep that contained: it refuses to start unless the database name
ends in `_test`, and it forces the scans/reports directories to a fresh temp directory per run
rather than honouring the environment. Neither is decoration — without the first, a typo drops the
production schema; without the second, any shell with `ZGRADER_SCANS_DIR` exported deletes customer
scans.

**Only one suite at a time against a given database.** The per-run temp directories make the
*files* concurrency-safe and it is easy to read that as the whole story, but the schema is shared:
a second pytest process deletes rows out from under the first. It surfaces as an
`ObjectDeletedError` on an unrelated row in whichever run lost the race — which reads exactly like
a product bug. If you need two at once, give the second its own `ZGRADER_TEST_DATABASE_URL`.

`zgrader_test` is pytest's scratch space and nothing else. `conftest` builds it with
`create_all`, so it lacks the raw-SQL indexes the migrations create (`ix_users_email_lower`) — it is
not a staging copy.

`build_pdf` imports WeasyPrint lazily, so everything except the PDF tests runs without Pango
present. The API process doesn't load it at startup either.

**WeasyPrint on Windows needs three separate things, and only the first is obvious.** The pip
package installs fine and is not the problem. Rendering goes through Pango, a system library that
ships in no wheel:

1. Install Pango: `pacman -S mingw-w64-x86_64-pango` under MSYS2. The winget "Gtk+ 3 Runtime"
   package is a dead end — it is from 2019 and its Pango predates
   `pango_context_set_round_glyph_positions` (added in 1.44), so WeasyPrint imports and then dies
   on the first render. **Uninstall it if it is already present**: it adds itself to the machine
   `PATH`, and WeasyPrint finds that copy ahead of a perfectly good MSYS2 one, so having it
   installed breaks a setup that would otherwise work. The failure names the old path, which is the
   only clue.
2. Set **both** `WEASYPRINT_DLL_DIRECTORIES=C:\msys64\mingw64\bin` *and* put that directory first
   on `PATH`. They fix different halves and neither is sufficient alone:
   - `PATH` alone doesn't load dependent DLLs — since Python 3.8 Windows no longer searches it for
     those — so you get a bare `error 0x7e` from a library plainly sitting right there.
   - `WEASYPRINT_DLL_DIRECTORIES` alone doesn't decide *which* Pango gets picked:
     `ctypes.util.find_library` walks `PATH` and returns the first hit, so a stale copy earlier on
     `PATH` still wins. Check with
     `python -c "import ctypes.util; print(ctypes.util.find_library('libpango-1.0-0'))"` — if that
     prints anything other than the MSYS2 path, fix `PATH` before looking anywhere else.
3. Nothing on Linux or in the container needs any of this; Debian's `libpango-1.0-0` is already on
   the loader path. Don't put the Windows path in `conftest.py`.

**If pacman fails every download with "unable to get local issuer certificate", check for TLS
interception before anything else.** AVG's Web/Mail Shield MITMs HTTPS and presents its own root,
which Windows trusts and MSYS2's private CA bundle does not — so winget, `gh` and browser downloads
all work while pacman alone fails, which points suspicion in entirely the wrong direction.
Confirm it with:

```
openssl s_client -connect repo.msys2.org:443 2>/dev/null | openssl x509 -noout -issuer
```

The fix that needs no change to any trust store: `pacman -Sp --needed <pkg>` prints the exact
package URLs, so fetch them with PowerShell (which uses the Windows store, and is therefore happy)
and install from disk with `pacman -U`.

`npx tsc --noEmit` doubles as the translation completeness check: `Dictionary = Widen<typeof en>`
forces `es.ts` to have the same key structure as `en.ts`, so a missing Spanish string is a type
error rather than a runtime hole.

**The backend image builds from `backend/requirements.lock`, not from the `>=` ranges in
`pyproject.toml`.** Change a dependency there and the lock has to be regenerated, or the image
builds without it — `pip install --no-deps .` will not quietly fetch the missing package, so the
failure surfaces as an `ImportError` inside the container.

```
cd backend && python -m uv pip compile pyproject.toml --python-platform linux \
  --python-version 3.11 --generate-hashes -o requirements.lock
```

`--python-platform linux` is not optional. `uvicorn[standard]` pulls `uvloop` and `httptools` only
on non-Windows, so a lock resolved on a Windows host omits both and the image silently loses them —
uvicorn falls back to the stdlib event loop and the only symptom is being slower.
`tests/test_lockfile_covers_dependencies.py` asserts they are present for exactly that reason, and
that every declared dependency made it in.

`docs/qa_checklist.md` is the manual end-to-end walkthrough. `docs/deployment.md` covers the
Cloudflare Tunnel, file ownership on Unraid, and getting into the admin panel.

## Analysis issues that are characterised but unfixed

Diagnosed with evidence, deliberately left rather than patched badly. Each has a measurement behind
it, so the next attempt starts from where the last one stopped.

- **The border transition threshold fires on real print texture.** `border.TRANSITION_DELTA_E` is 25
  Lab units, calibrated on synthetic flat fills where the step into artwork is 112–192. Real print
  crosses 25 routinely. Three distinct cases, not one: a clean profile works; a transient spike
  before the real transition makes first-crossing fire early; and glare can erase the transition
  entirely (ΔE never exceeds 11), where no threshold setting helps. A persistence test fixes the
  latter two but converts seven honest refusals into readings that disagree by up to 5 points across
  shots of one card — trading ~2 wrong readings for ~7. **Attempted twice, measured, rejected both
  times.** Card 6 in the photo set still spreads 6.02 on centering.

  **A third attempt profiled it before choosing a rule, and that changed the diagnosis.** Dumping
  the ΔE crossings for every edge of all 32 real photographs shows each edge carries *two*
  populations — a shallow one and a deep one, typically ~45px apart — and the RANSAC fit arbitrates
  between them on line straightness, which has no reason to prefer the right one. Card 6's bottom
  reads 79, 81 and **34** across three shots while its other three edges stay within 5px, and the
  raw first-crossing median sits at ~34 in all three: the crossings do not move, the *fit* changes
  which population it locks onto. So this is **bistable selection between two real transitions**,
  not a miscalibrated threshold, and it concentrated on one edge (the bottom) in every failing case.

  Two candidate signals were measured and **both failed**:
  - *Contrast quality* (ΔE at the crossing, profile peak, signal-to-noise against the border's own
    texture) does not separate. Card 6's outlier shot scores inside the range of the two shots that
    agree with each other on every one of them.
  - *Bimodality* does not separate either. The most balanced split measured, 653 shallow against 707
    deep, belongs to `4_FrontGlareShot` — part of one of the **steadiest** cards in the set (0.9pp).
  - *Preferring the deepest well-supported mode* was then prototyped and evaluated end to end. It
    helps cards 3 (6.40→1.40) and 6 (19.40→11.30) and leaves 4 and 7 untouched, but pushes card 2
    from 2.00 to **10.00** by driving its border past the true transition into artwork, and card 6 is
    still 11.3pp. Aggregate spread improves, 29.2→24.1, which is exactly the aggregate hiding the
    interesting case. Rejected: it trades one broken card for another, the same shape as the
    persistence test.

  So the disambiguating information is probably not in a single edge's ΔE profile at all. The lead
  worth trying next is **cross-edge plausibility** — a card's four border widths are related, and for
  card 6 the true bottom (79) is far closer to its top (88) than the spurious 34 is. That is the one
  hypothesis this data supports and nobody has tested.

  Do not reach again for a contrast-quality gate, a bimodality gate, or a deepest-mode rule without
  new evidence; all three are measured and recorded above. The harness is
  `scripts/fixture_drift.py` plus repeat shots of one card: judge on **spread per card and how many
  photographs still produce a reading, together**, never the aggregate.
- **`capture_worst_case` scores a flat 10.00 on surface.** Its noise generates plenty of raw
  variance, so it does not trip `surface.MIN_DETAIL_FRACTION` — the noise *masks* scratches rather
  than erasing them, which needs a noise measure that does not exist yet.
- **Foil is declared, not detected.** Phase 7 uses `Card.foil` from the customer. Detecting it from
  the image was tried and rejected: clipped-highlight density separates on per-card averages
  (5.6–9.1% against 0.6–2.8%) but overlaps badly per photograph — a plain card under high glare
  reads 10.7%, a foil card in flat light 0.4%. Local variance and sparkle density do not separate at
  all. Do not reach for those three again without new evidence.
- **A failed geometry fit cannot be graded, only detected.** When the fit falls back there is no way
  to tell "the boundary is a millimetre out" from "that raster is a photograph of a desk", so
  everything the boundary touches has to decline together. Re-running `detect_boundary` on the
  *rectified* raster was the obvious separator and it does not work: fitted photographs score
  0.324–0.937 card-fill and fallbacks score 0.225–0.975, medians 0.786 against 0.782. It fails
  hardest where it should pass, because a correct rectification fills the frame edge to edge and
  leaves the detector no background to find an edge against — it latches onto the printed artwork
  frame instead. `7_FrontView`, a visually perfect rectification, scores 0.324; `6_FrontSkewed`, a
  fallback, scores 0.975. Do not reach for that one again.

## Known-open, deliberately

Listed so a review reports something new rather than re-deriving these:

- **The session token lives in `localStorage`**, so an XSS could steal it. Moving it to an
  `httpOnly` cookie means adding CSRF protection and reworking every authenticated image fetch.
- **The copy and the seeded plan describe different products.** The free tier *is* enforced — this
  entry used to claim otherwise, naming a `FREE_TIER_LIMIT` that has never existed in the codebase.
  `submissions.py` refuses on `quota.can_submit` and consumes on create, the rules live in the
  admin-editable `plan_entitlements` table (`GET`/`PATCH /plans/{plan}`), and `QuotaChip` counts the
  customer down. What is unsettled is the *number*: the seed grants free accounts **3 checks per 7
  days, renewing**, while `en.ts` says "The first check is free" in two places — so on today's
  settings nobody ever has to pay. One of the two has to move, and the limit is a panel value rather
  than a deploy, deliberately.
- **A lifetime allowance is not expressible.** `period_days` is `NOT NULL` with
  `CheckConstraint("period_days >= 1")` and `_roll_period_forward` always advances the window, so
  every cap renews. "N checks per account, ever" needs a nullable `period_days` meaning *never
  resets*, or an explicit lifetime cap — a very large `period_days` works arithmetically but shows
  the customer a countdown measured in decades.
Three entries left this list rather than being forgotten, and the reason each was here is still
worth knowing: outbound mail now goes through a real relay (the operator's send-test-email action
in the admin panel is what proves it, and it reports what SMTP actually did); Postgres is backed up
nightly by `infra/backup/`; and `submission_code` comes from `submission_code_seq` rather than
`COUNT(*) + 1`, so a code is issued once and never reissued — see the comment on
`models/submission.py`, which keeps the full reasoning.
