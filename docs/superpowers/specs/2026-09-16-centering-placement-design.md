# Centering placement — design

**Date:** 2026-09-16
**Status:** draft for review — no code until this is approved and turned into a plan
**Covers:** letting a customer place and fine-tune the centering lines when detection declined to measure
centering, with an in-page magnifier; and the PDF "client-adjusted" watermark that a centering adjustment
never triggered

---

## 1. What the report showed

The report was "the feature to adjust the centering lines has been lost", with SUB-00023 as the example.

**Nothing was removed.** `use-centering-adjust.ts`, `CenteringLines.tsx` and the handle wiring in
`AnnotatedPhoto.tsx` have not changed since 2026-08-14, before any recent work. What happened is that
SUB-00023's centering **declined**: the scorecard reads "Not measurable" with the `centering_no_frame` copy
("No clear printed border to measure against"). `centering.py` declines when two or more sides have no
fitted border, or no axis is complete. This is a Japanese card with a silver border and the name bar and
text box printed hard against it, which is the characterised-but-unfixed border weakness in AGENTS.md.

The handles are withheld for a declined side **by design**:

- `centeringHandles()` returns `null` when `raw_score === null`, so `canAdjust` is false and the toggle is
  not rendered.
- `POST /submissions/{code}/centering-adjust` answers 409 for an unscored side — "accepting would let a
  client invent a centering reading for a side the pipeline explicitly declined to give one for".
- The ±`centering_adjust_limit_mm` cap is measured from where detection put each line, so with nothing
  detected there is no anchor to measure it from.

The green lines visible on the SUB-00023 photo are **edge regions** (`regions._build_edge_regions`, the
strips edges measures, drawn green when `ok`), not centering lines. That is why the "top line" looked
slightly off the printed border: it was never meant to sit on it.

Two further findings from reading the code:

- **The PDF never marks a centering-only adjustment as client-adjusted.** `builder.build_report_context`
  sets `"client_adjusted": bool(dismissed_findings)`, while `Submission.client_adjusted` counts
  `dismissed_regions` *or* `centering_adjustments`, and its docstring says why both must count. So a report
  whose only change is a moved centering line publishes without the watermark, the title tag or the
  `_client_adjusted` filename suffix. Read from the code, not yet reproduced by rendering one.
- **The handles are announced as sliders but ignore the keyboard.** `CenteringLines` gives each handle
  `role="slider"` and `tabIndex={0}` with no key handler.

## 2. Decisions made during brainstorming

| Question | Decision |
|---|---|
| Who may set the lines when detection declined, and does the result score? | **The customer, and it scores**: score, company comparisons and PDF all use it, labelled everywhere as placed by the customer, at reduced confidence. |
| Where do the lines start, and how far may they move? | Each line starts at the pipeline's `indicative_estimate` width where that side was measured, otherwise at a fixed default. Movement is free within **0–8mm** of the card edge; no ±4mm cap, since there is no detection to stay near. |
| What should adjusting feel like? | **In-page with a magnifier** (mockup option B), not a fullscreen editor. Plus tap-to-select nudge buttons and keyboard control. |
| The watermark bug | Fixed in this work. |
| The crop issue reported alongside | Separate spec: `2026-09-16-crop-guided-edge-fit-design.md`. |

## 3. Two modes of one adjustment

Everything below turns on one distinction, derived from the stored per-side centering row and never stored
separately:

| Side's stored centering row | Mode | Bounds |
|---|---|---|
| `raw_score` is a number | **nudge** (today's behaviour) | ±`centering_adjust_limit_mm` from detected, as now |
| `raw_score` is `None`, assessment limitations contain `centering_no_frame`, none are in `assessment.DISQUALIFYING_LIMITATIONS`, and `card_geometry.px_per_mm > 0` | **place** | each width in `[0, PLACEMENT_MAX_MM × px_per_mm]`, and within half the raster span (the existing clamp) |
| anything else — above all `geometry_unverified` | **refused**, 409 as now | — |

`geometry_unverified` stays refused on purpose. When the edge fit fell back, the raster may be mostly desk
(`2_FarStandardShot` is the recorded example), and lines placed on it would publish a centering score for a
card nobody has seen.

`centering_adjust_limit_mm = 0` keeps its meaning as the kill switch: it disables both modes (403, as now).
It is the operator's existing "if this is ever abused" control, and a second switch for placement would be
one more thing to forget.

`PLACEMENT_MAX_MM = 8.0` and `PLACEMENT_DEFAULT_MM = 3.0` live in `analysis/scoring.py` beside the other
centering constants, tagged **ARBITRARY**: 8mm is comfortably wider than any printed border on the supported
games and stops a line being dragged across the artwork, and 3mm is only a starting position the customer
is expected to move.

## 4. Backend

### 4.1 Storage

No new column. A placement is stored in `submissions.centering_adjustments[side]` as the same four
`*_px` widths a nudge stores. The per-side `AnalysisResult` is never modified: it remains the record of what
was measured, which is the invariant adjustments already rest on, and it is what lets the mode be derived
rather than stored.

### 4.2 Endpoint

`POST /{code}/centering-adjust` gains the place mode; the request body (`CenteringAdjustIn`) is unchanged.

- Mode is resolved as in §3. Place mode validates the §3 bounds. The existing "every line back where
  detection had it clears the adjustment" rule applies to nudge mode only, because a placement has no
  detected lines to compare with.
- **Clearing a placement** gets an explicit route, `DELETE /{code}/centering-adjust/{side}`, which removes
  that side's entry and recomputes. It works for either mode, so "Back to detected" can use it too.
  Same rate limiter as the POST (`test_rate_limit_coverage.py` will insist), same ownership check.
- Audit actions: `centering_placed` / `centering_placement_cleared` beside the existing
  `centering_adjusted` / `centering_adjust_cleared`, so the history says which kind of claim was made.
- **Status gate — new, and it changes today's nudge behaviour too.** The adjust endpoint currently has
  none: a centering adjustment is accepted in any status, including `published`, while
  `regions/toggle` accepts a dismissal only in `draft_ready`. The public share page renders from the
  database rather than the PDF, so an adjustment made after publication changes what a stranger sees,
  with no operator review, and the published PDF then disagrees with the page. Both modes, POST and
  DELETE, answer 409 outside `draft_ready`, matching `toggle_region`. **Needs the operator's
  confirmation at spec review**, because it removes something customers can do today.

### 4.3 Scoring

A new limitation code `assessment.CENTERING_CLIENT_PLACED = "centering_client_placed"` and confidence
`CONFIDENCE_CENTERING_CLIENT_PLACED = 0.4` (REASONED: below a partial frame's 0.6, because no part of the
reading was measured, and above a declined frame's 0.2, because the customer can see the border when the
detector could not). Registered wherever limitation codes are enumerated, with EN/ES copy.

`recompute._adjusted_side_score` gets a centering-placement branch **before** the generic
"state ≠ measured → None" guard, and only for that branch. The guard stays exactly as it is for every other
category and every other declined state; it exists so the next declining path is covered without anyone
predicting it, and it must keep doing that. The branch applies only when the side's stored row is
placement-eligible (§3) and an adjustment is present. It then:

1. scores the placed widths through `centering.ratios_from_widths` → `centering.score_from_worse_pct`
   (never a second copy of the mapping — the `recompute.py`-keeps-forgetting rule in AGENTS.md);
2. returns the score, the worse-side percentage, and an **effective per-side assessment**:
   `assessment.measured(score, CONFIDENCE_CENTERING_CLIENT_PLACED, (CENTERING_CLIENT_PLACED,))`.

`recompute_submission` then has to change what it writes on the combined centering row, because today it
touches only `raw_score` and `worse_side_pct`, and the combined `assessment` would go on saying
`unmeasurable` beside a number — the exact contradiction `_persist_combined` was fixed for (SUB-00011).
So for centering it:

- rebuilds `measurements["assessment"]` from the two effective per-side assessments with
  `pipeline._combine_assessments`. That function moves to `analysis/assessment.py` so recompute does not
  import the pipeline; its behaviour, including "the front decides whether there is a reading at all", is
  unchanged;
- keeps the pipeline's own combined assessment as `measurements["original_assessment"]`, written the first
  time recompute changes it (rows analysed before this ship have none, and the current assessment is the
  original at that moment), mirroring `original_raw_score`;
- hoists `worse_side_pct` as it already does, so `rules_engine` produces centering comparisons from the
  placed ratio with no change of its own.

Clearing therefore restores the original assessment, score and comparisons exactly. That reverse direction
is the one the tests have to pin (§7), because it is where the equivalent bugs lived before.

### 4.4 Everything drawn from the numbers

AGENTS.md: *before adding a client-editable measurement, ask what is drawn from it.* Every surface that
renders centering:

| Surface | Change |
|---|---|
| `recompute.redraw_centering_annotations` | Today it skips `raw_score is None` rows. It also draws a placement-eligible row that has a placement, from the placed widths alone (all four are present in the adjustment). Still unconditional, so clearing redraws the plain image. |
| `builder.build_report_context` | `"client_adjusted": submission.client_adjusted` (the watermark fix). `unmeasurable` already follows the combined assessment state, so the rebuilt assessment carries through. The limitation note renders from `LIMITATION_LABELS`. |
| `report.html.jinja` | No structural change expected; the note arrives through the existing limitation notes. Verified by rendering. |
| Public share (`schemas/public_report.py`, `PublicReport.tsx`) | Placement uses keys the page already publishes (`centering_adjustments`, assessment limitations). `test_public_payload_key_allowlist` is the arbiter; if it fails, answer "should a stranger see this?" and add the key deliberately. The page shows the same "placed by the customer" note and remaps the frame the way it already does for nudges. |
| `og_image` | Fingerprint already includes `centering_adjustments` and the combined scores; nothing to change. A test confirms a placement changes the fingerprint and clearing restores it. |
| `rules_engine` | No change; reads the hoisted `worse_side_pct`. |

## 5. Frontend

### 5.1 Where it appears

- `centeringHandles()` returns `{ mode: "nudge" | "place", detected, pxPerMm, bounds }` or `null`, applying
  the same eligibility as §3 from the result it is given. For place mode, `detected` is built from
  `measurements.indicative_estimate`: a side whose `per_side[side].measured` is true keeps its width, and
  any other side starts at `PLACEMENT_DEFAULT_MM × pxPerMm`. The bounds come from the same constants
  (published through `/catalog`, which already carries `centering_adjust_limit_mm`, so the client never
  hard-codes a number the server enforces).
- A declined-but-placeable centering tile gets a **"Place the lines yourself"** button, and the photo
  toolbar a **"Place centering lines"** toggle. A scored tile keeps today's "Adjust centering".
  A `geometry_unverified` side shows neither.

### 5.2 The adjusting experience (mockup option B)

- **Magnifier while dragging.** A 96px circular loupe, offset from the pointer so a finger never covers
  it, flipping side near the edges of the photo. It shows the base photo through a CSS background (the same
  object URL, no second fetch), the line being moved, and a small crosshair. Zoom is capped by what the
  image holds: the base photo is at most `artifacts.MAX_DERIVED_PX` (1600px) on its long side, about 18px
  per millimetre of card, so the loupe uses `min(4, 2 × naturalWidth / displayedWidth)` — about 4× on a
  phone, 1.5–2× on a wide desktop layout. Past that it only magnifies blur. A sharper image for the loupe
  would mean storing a larger base image, against the derived-image size invariant; not done.
- **Selection and nudges.** Tapping a line selects it (it turns pink). ▲▼ (or ◀▶) buttons move it
  0.1mm per tap, and the loupe docks at the selected line while nudging.
- **Keyboard.** Tab moves between handles; arrow keys move 0.1mm, Shift+arrow 1mm; `aria-valuenow`,
  `aria-valuemin` and `aria-valuemax` are real values, in millimetres. This also fixes the silent-slider bug.
- **Live readout, server score.** The L/R and T/B splits and the worse side update while moving; the score
  is computed only by the server on **Apply**, as today. **Cancel** discards unsaved moves.
- Clamping in the hook uses the mode's bounds; the server enforces them independently, so a rejection is
  shown rather than swallowed, as now.

### 5.3 After applying

- The centering tile shows the score with a **"placed by you"** chip beside "lower confidence", a one-line
  note that detection could not find the border so these lines were placed by the customer rather than
  measured, and **Adjust lines** / **Clear my lines** buttons.
- On the photo, placed lines draw **dashed pink**; detected lines stay solid green. A placement must never
  read as a measurement at a glance.
- The per-side split under the score, which today is derived from detected widths, is derived from the
  placed widths for a placed side.
- All new strings in `en.ts` and `es.ts`; `npx tsc --noEmit` enforces completeness.

## 6. Not in scope

- **The admin detail page** renders `SubmissionOverview` without `onAdjusted` and has never offered
  adjustment. The backend already accepts an operator's adjustment. Adding it is a small follow-up, not
  part of this change.
- **Improving border detection** so fewer cards decline. The untested lead (mask the text printed against
  the bottom border) stays recorded in AGENTS.md.
- **A higher-resolution loupe image** (see §5.2).

## 7. Testing

Backend (pytest, `zgrader_test`):

- `test_centering_adjust.py`, extended:
  - a declined `centering_no_frame` side accepts a placement within 0–8mm, rejects one outside, and the
    combined row becomes `measured` with `centering_client_placed`, a score, `worse_side_pct` and
    company comparisons;
  - **clearing restores the original combined assessment, score, `worse_side_pct` and comparisons
    exactly**, including for a row analysed before `original_assessment` existed;
  - a `geometry_unverified` side is refused (409); limit 0 refuses both modes (403);
  - outside `draft_ready` (above all `published`), POST and DELETE both answer 409 in both modes;
  - front declined and placed + back scored, and front scored + back declined and placed, combine
    through `_combine_assessments` as the front-decides rule says.
- `test_centering_annotation_redraw.py`: a placed side is redrawn from the placement; clearing redraws it
  plain.
- A new watermark test: a centering-only adjustment produces `client_adjusted` in the report context and
  the `_client_adjusted` filename suffix. Written first, to fail against today's builder.
- `test_public_share.py`: allowlist passes (or is changed deliberately); the note is present.
- `test_og_image.py`: placement changes the fingerprint; clearing restores it.
- End to end: a declined-centering fixture carried through placement → combined row → PDF → public payload,
  in the manner of `test_corners_decline_end_to_end.py`.
- `test_rate_limit_coverage.py` covers the new DELETE route.

Frontend (there is no unit-test runner in this repo; adding one is out of scope):

- `npx tsc --noEmit` and `npx next build`.
- In the browser pane against a **local** stack on `zgrader_test` data — never the production tunnel on
  5432 — on a declined-centering submission: place, magnifier, nudges, keyboard, apply, chip, dashed lines,
  clear; and a phone-width pass (375px) for the loupe's flip and the touch targets.

No change under `analysis/` affects a measurement, so `fixture_drift.py` should report no drift; it is run to
confirm that, not assumed.

## 8. Documentation

- AGENTS.md: amend the client-adjustment invariant to cover placement (a declined centering can become a
  client-placed score; the per-side row stays the measurement record; `original_assessment` is the reverse
  path), and add the `raw_score` grep note in the opposite direction: *a declined category that can be
  un-declined* is new, and the surfaces in §4.4 are the ones it reached.
- `/methodology`: one sentence on customer-placed centering and how it is labelled, EN/ES.
- Privacy policy and Terms: no change; no new data is collected.
