# Centering Placement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a customer place and fine-tune the centering lines when detection declined to measure centering (scored, labelled as placed, lower confidence), with an in-page magnifier, and fix the PDF watermark that a centering-only adjustment never triggered.

**Architecture:** A placement is stored in the existing `submissions.centering_adjustments` beside an unchanged, declined per-side row; "nudge" vs "place" is derived from that row, never stored. `recompute` scores the placed widths through the existing centering functions and rebuilds the combined assessment, keeping the pipeline's own as `original_assessment` so clearing restores it exactly. The frontend hook gains a place mode, and `CenteringLines` gains selection, keyboard nudges and a loupe.

**Tech Stack:** FastAPI + SQLAlchemy + Postgres (pytest), OpenCV/Pillow, Next.js 16 App Router + HeroUI v3 + Tailwind v4, TypeScript.

**Spec:** `docs/superpowers/specs/2026-09-16-centering-placement-design.md`

## Global Constraints

- Branch: `centering-placement`, cut from `centering-placement-and-crop-fit-design` (which carries the specs).
- Tests need a Postgres database whose name ends in `_test`. `127.0.0.1:5432` is an ssh tunnel to **production** Postgres; never point a dev server, seed script or `ZGRADER_DATABASE_URL` at anything but `zgrader_test`. Only one pytest process at a time against it.
- Run backend tests as `cd backend && .venv/Scripts/python.exe -m pytest <args> > <scratch>/pytest.log 2>&1; echo exit=$?` then read the log. **Never pipe pytest through `tail`/`head`** — it replaces the exit status.
- Frontend checks: `cd frontend && npx tsc --noEmit && npx next build`. `tsc` also enforces that `es.ts` has every key `en.ts` has.
- There is **no frontend unit-test runner** in this repo; frontend behaviour is verified in the browser pane (Task 10). Do not add one in this work.
- Placement bounds: `CENTERING_PLACEMENT_MAX_MM = 8.0`, `CENTERING_PLACEMENT_DEFAULT_MM = 3.0` (spec's `PLACEMENT_MAX_MM` / `PLACEMENT_DEFAULT_MM`, prefixed to match `scoring.py`), tagged ARBITRARY.
- New limitation code `centering_client_placed`; confidence `CONFIDENCE_CENTERING_CLIENT_PLACED = 0.4`.
- Placement is allowed only when the side's row has `raw_score is None`, its assessment limitations contain `centering_no_frame`, none are in `assessment.DISQUALIFYING_LIMITATIONS`, and `card_geometry.px_per_mm > 0`.
- `centering_adjust_limit_mm = 0` disables both nudge and place (403).
- Both POST and DELETE on centering adjustment answer 409 unless the submission is `draft_ready` (confirmed at spec review; changes today's nudge behaviour).
- Every score goes through `centering.ratios_from_widths` → `centering.score_from_worse_pct`; never a second copy of the mapping, in Python or TypeScript.
- All new customer-facing copy exists in English and Spanish, backend (`reports/strings.py`) and frontend (`lib/i18n/en.ts`, `es.ts`). The limitation copy is neutral ("placed by hand"), because the public share page shows it to strangers.
- `<scratch>` in commands means a scratch directory outside the repo (the session scratchpad); never write logs into the repo.
- Spec §5.3 puts **Adjust lines** / **Clear my lines** on the centering tile. Here the tile carries a link that opens the photo's adjuster, and **Clear my lines** lives in that adjuster, because the adjuster owns the drag state and the tile has none. Same actions, one place to perform them.
- Commit messages end with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

## Files

| File | Responsibility | Tasks |
|---|---|---|
| `backend/zgrader/reports/builder.py` | `client_adjusted` from the model property | 1 |
| `backend/zgrader/analysis/assessment.py` | new code + confidence; `combine_assessments` moved here | 2 |
| `backend/zgrader/analysis/pipeline.py` | calls `assessment.combine_assessments` | 2 |
| `backend/zgrader/analysis/centering.py` | `WIDTH_KEYS`, `widths_from`, `placement_eligible` | 2 |
| `backend/zgrader/analysis/scoring.py` | placement constants | 2 |
| `backend/zgrader/reports/strings.py` | EN/ES label for the new code | 2 |
| `backend/zgrader/analysis/recompute.py` | placement scoring, combined assessment rebuild, score-follows-assessment | 3 |
| `backend/zgrader/api/routers/submissions.py` | place mode, bounds, status gate, DELETE | 4 |
| `backend/zgrader/schemas/catalog.py`, `api/routers/catalog.py` | publish placement bounds | 4 |
| `backend/zgrader/analysis/recompute.py` (`redraw_centering_annotations`) | draw placed / plain for eligible rows | 5 |
| `backend/tests/centering_rows.py` | shared row builders for tests | 3 |
| `frontend/lib/api.ts`, `branding-context.tsx`, `use-centering-adjust.ts` | types, DELETE call, hook modes | 7 |
| `frontend/components/CenteringLines.tsx` | selection, keyboard, loupe, placed style | 8 |
| `frontend/components/AnnotatedPhoto.tsx`, `SubmissionOverview.tsx`, `PublicReport.tsx` | wiring, chips, links | 9 |
| `AGENTS.md`, `frontend/lib/i18n/{en,es}.ts` (`methodology.adjustBody`) | docs | 10 |

---

### Task 1: Branch, housekeeping, and the PDF watermark fix

**Files:**
- Modify: `.gitignore`, `backend/zgrader/reports/builder.py:199`
- Modify: `docs/superpowers/specs/2026-09-16-centering-placement-design.md` (§7 frontend line)
- Test: `backend/tests/test_report_client_adjusted.py` (create)

**Interfaces:**
- Produces: `build_report_context(...)["client_adjusted"]` equals `submission.client_adjusted`.

- [ ] **Step 1: Cut the branch and ignore mockup files**

```bash
git switch centering-placement-and-crop-fit-design
git switch -c centering-placement
printf '\n# Brainstorming mockups (superpowers visual companion)\n.superpowers/\n' >> .gitignore
```

- [ ] **Step 2: Correct the spec's frontend testing line**

In the spec's §7 "Frontend:" list, replace the bullet list's opening so it reads:

```markdown
Frontend (there is no unit-test runner in this repo; adding one is out of scope):
```

- [ ] **Step 3: Write the failing test**

Create `backend/tests/test_report_client_adjusted.py`:

```python
"""A centering-only adjustment must mark the PDF as client-adjusted.

`Submission.client_adjusted` counts dismissed findings *or* centering
adjustments, and says why both must. The report builder recomputed the flag
from dismissed findings alone, so a report whose only change was a moved
centering line published without the watermark, the title tag or the
`_client_adjusted` filename suffix.
"""

from zgrader.auth.security import hash_password
from zgrader.models import Submission, SubmissionStatus, User
from zgrader.models.settings import get_or_create_settings
from zgrader.reports.builder import build_report_context


def _submission(db_session, code: str) -> Submission:
    user = User(
        email=f"{code.lower()}@example.com",
        hashed_password=hash_password("hunter2pass"),
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    submission = Submission(submission_code=code, user_id=user.id, status=SubmissionStatus.draft_ready)
    db_session.add(submission)
    db_session.commit()
    return submission


def test_a_centering_only_adjustment_marks_the_report_adjusted(db_session):
    submission = _submission(db_session, "SUB-WMK01")
    submission.centering_adjustments = {
        "front": {"left_px": 30.0, "right_px": 34.0, "top_px": 28.0, "bottom_px": 31.0}
    }
    db_session.commit()

    context = build_report_context(submission, get_or_create_settings(db_session))

    assert context["dismissed_count"] == 0
    assert context["client_adjusted"] is True


def test_an_untouched_report_is_not_marked_adjusted(db_session):
    submission = _submission(db_session, "SUB-WMK02")

    context = build_report_context(submission, get_or_create_settings(db_session))

    assert context["client_adjusted"] is False
```

- [ ] **Step 4: Run it to verify the first test fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_report_client_adjusted.py -v > <scratch>/pytest.log 2>&1; echo exit=$?`
Expected: `test_a_centering_only_adjustment_marks_the_report_adjusted` FAILS (`assert False is True`); the other passes.

- [ ] **Step 5: Fix the builder**

In `backend/zgrader/reports/builder.py`, in `build_report_context`'s return dict, replace:

```python
        "client_adjusted": bool(dismissed_findings),
```

with:

```python
        # The model's property, not a recount of dismissals: a moved centering
        # line changes a published number as much as a dismissed finding does,
        # and leaves less trace. Recounting here shipped a centering-only
        # adjustment without the watermark.
        "client_adjusted": submission.client_adjusted,
```

- [ ] **Step 6: Run the test file and the report tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_report_client_adjusted.py tests/test_unmeasurable.py -v > <scratch>/pytest.log 2>&1; echo exit=$?`
Expected: all PASS, `exit=0`.

- [ ] **Step 7: Commit**

```bash
git add .gitignore docs/superpowers/specs/2026-09-16-centering-placement-design.md backend/zgrader/reports/builder.py backend/tests/test_report_client_adjusted.py
git commit -m "Mark a centering-only adjustment as client-adjusted in the PDF" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Placement primitives — code, confidence, eligibility, constants, copy

**Files:**
- Modify: `backend/zgrader/analysis/assessment.py` (codes block ~line 53, `ALL_LIMITATION_CODES`, confidences ~line 108; add `combine_assessments` at end)
- Modify: `backend/zgrader/analysis/pipeline.py:222-290` (remove `_combine_assessments`), `:338` (call site)
- Modify: `backend/tests/test_combined_sides.py:19`, `backend/tests/test_indicative_estimate.py:122` (imports)
- Modify: `backend/zgrader/analysis/centering.py` (add helpers near `ratios_from_widths`)
- Modify: `backend/zgrader/analysis/scoring.py` (after `CENTERING_POINTS_PER_PCT`)
- Modify: `backend/zgrader/reports/strings.py` (EN after `centering_partial_frame` ~line 192, ES ~line 267)
- Modify: `frontend/lib/i18n/en.ts` (`submissionDetail.limitation`, after `centering_partial_frame` ~line 167), `frontend/lib/i18n/es.ts` (~line 155)
- Test: `backend/tests/test_centering_placement.py` (create)

**Interfaces:**
- Produces:
  - `assessment.CENTERING_CLIENT_PLACED: str = "centering_client_placed"`
  - `assessment.CONFIDENCE_CENTERING_CLIENT_PLACED: float = 0.4`
  - `assessment.combine_assessments(front: dict | None, back: dict | None) -> dict | None` (body identical to today's `pipeline._combine_assessments`)
  - `centering.WIDTH_KEYS: tuple[str, ...] = ("left_px", "right_px", "top_px", "bottom_px")`
  - `centering.widths_from(adjustment: dict | None) -> tuple[float, float, float, float] | None`
  - `centering.placement_eligible(measurements: dict | None) -> bool`
  - `scoring.CENTERING_PLACEMENT_MAX_MM = 8.0`, `scoring.CENTERING_PLACEMENT_DEFAULT_MM = 3.0`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_centering_placement.py`:

```python
"""Placing centering lines on a side the pipeline declined to measure.

A placement is a claim by the customer, not a measurement, so it has to be
allowed only where the declined reading still stands on a trustworthy card
outline, scored through the same functions as a measurement, and labelled
everywhere as what it is.
"""

from zgrader.analysis import assessment, centering, scoring


def _declined(*limitations, px_per_mm=10.0):
    return {
        "assessment": {
            "state": "unmeasurable",
            "confidence": 0.0,
            "score_low": None,
            "score_high": None,
            "limitations": list(limitations),
        },
        "card_geometry": {"px_per_mm": px_per_mm},
    }


# --- eligibility --------------------------------------------------------


def test_a_side_with_no_printed_frame_can_be_placed():
    assert centering.placement_eligible(_declined(assessment.CENTERING_NO_FRAME)) is True


def test_a_side_whose_edges_were_not_found_cannot_be_placed():
    """The raster may be mostly desk; lines on it would score a card nobody has seen."""
    measurements = _declined(assessment.CENTERING_NO_FRAME, assessment.GEOMETRY_UNVERIFIED)
    assert centering.placement_eligible(measurements) is False


def test_a_side_declined_for_another_reason_cannot_be_placed():
    assert centering.placement_eligible(_declined(assessment.CAPTURE_TOO_LOW_RESOLUTION)) is False


def test_a_side_without_a_scale_cannot_be_placed():
    measurements = _declined(assessment.CENTERING_NO_FRAME, px_per_mm=0)
    assert centering.placement_eligible(measurements) is False


def test_a_scored_side_is_not_a_placement():
    measured = {
        "assessment": {"state": "measured", "confidence": 0.9, "limitations": []},
        "card_geometry": {"px_per_mm": 10.0},
    }
    assert centering.placement_eligible(measured) is False


def test_nothing_stored_is_not_eligible():
    assert centering.placement_eligible(None) is False


# --- widths ---------------------------------------------------------------


def test_widths_need_all_four_numbers():
    assert centering.widths_from({"left_px": 1, "right_px": 2, "top_px": 3, "bottom_px": 4}) == (1.0, 2.0, 3.0, 4.0)
    assert centering.widths_from({"left_px": 1.0}) is None
    assert centering.widths_from(None) is None
    assert centering.widths_from({"left_px": "1", "right_px": 2, "top_px": 3, "bottom_px": 4}) is None


# --- the constants the endpoint and the page share ------------------------


def test_placement_bounds_are_the_published_ones():
    assert scoring.CENTERING_PLACEMENT_MAX_MM == 8.0
    assert scoring.CENTERING_PLACEMENT_DEFAULT_MM == 3.0


def test_the_placed_code_is_a_registered_limitation():
    assert assessment.CENTERING_CLIENT_PLACED in assessment.ALL_LIMITATION_CODES
    assert assessment.CONFIDENCE_CENTERING_NO_FRAME < assessment.CONFIDENCE_CENTERING_CLIENT_PLACED
    assert assessment.CONFIDENCE_CENTERING_CLIENT_PLACED < assessment.CONFIDENCE_CENTERING_PARTIAL_FRAME


def test_the_placed_code_has_report_copy_in_both_languages():
    from zgrader.reports.strings import LIMITATION_LABELS

    assert "placed by hand" in LIMITATION_LABELS["en"][assessment.CENTERING_CLIENT_PLACED]
    assert LIMITATION_LABELS["es"][assessment.CENTERING_CLIENT_PLACED]
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_centering_placement.py -v > <scratch>/pytest.log 2>&1; echo exit=$?`
Expected: FAIL with `AttributeError: module 'zgrader.analysis.centering' has no attribute 'placement_eligible'` (and similar).

- [ ] **Step 3: Add the code and confidence to `assessment.py`**

After the `CENTERING_PARTIAL_FRAME` line:

```python
#: No printed frame was found, and the customer placed the lines by hand. A
#: claim rather than a measurement, so it is labelled wherever the score shows.
CENTERING_CLIENT_PLACED = "centering_client_placed"
```

Add `CENTERING_CLIENT_PLACED,` to `ALL_LIMITATION_CODES` directly after `CENTERING_PARTIAL_FRAME,`.

After `CONFIDENCE_CENTERING_PARTIAL_FRAME = 0.6`:

```python
#: Lines placed by the customer where no frame was found. REASONED: below a
#: partial frame, because no part of this reading was measured; above a
#: declined frame, because the customer can see a border the detector could not.
CONFIDENCE_CENTERING_CLIENT_PLACED = 0.4
```

- [ ] **Step 4: Move `_combine_assessments` into `assessment.py`**

Cut the whole `_combine_assessments` function (docstring and body) out of `pipeline.py` and paste it at the end of `assessment.py`, renamed `combine_assessments`, with `assessment.` prefixes removed inside it (`assessment.MEASURED` → `MEASURED`, `assessment.UNMEASURABLE` → `UNMEASURABLE`, `assessment.COMBINED_SINGLE_SIDE` → `COMBINED_SINGLE_SIDE`, `assessment.CONFIDENCE_SINGLE_SIDE_FACTOR` → `CONFIDENCE_SINGLE_SIDE_FACTOR`). Add one line to its docstring's first paragraph:

```text
    Lives here rather than in the pipeline because recompute rebuilds a combined
    assessment too, when a placement turns a declined side into a reading.
```

In `pipeline.py` `_persist_combined`, change the call to:

```python
        measurements["assessment"] = assessment.combine_assessments(
```

In `tests/test_combined_sides.py` replace `from zgrader.analysis.pipeline import _combine_assessments` with:

```python
from zgrader.analysis.assessment import combine_assessments as _combine_assessments
```

In `tests/test_indicative_estimate.py` replace `from zgrader.analysis.pipeline import _combine_assessments` the same way.

- [ ] **Step 5: Add the centering helpers**

In `backend/zgrader/analysis/centering.py`, directly above `def ratios_from_widths(`:

```python
#: The four border widths an adjustment or placement carries, in raster pixels.
WIDTH_KEYS = ("left_px", "right_px", "top_px", "bottom_px")


def widths_from(adjustment: dict | None) -> tuple[float, float, float, float] | None:
    """The four widths from a stored adjustment, or None if any is missing.

    Stored JSON is not a schema: a row written by an older version, or by hand,
    must be ignored rather than half-applied.
    """
    if not adjustment:
        return None
    values = [adjustment.get(key) for key in WIDTH_KEYS]
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return None
    return tuple(float(v) for v in values)  # type: ignore[return-value]


def placement_eligible(measurements: dict | None) -> bool:
    """Whether a declined side may have its centering lines placed by hand.

    Only when centering declined for want of a printed frame, and the card's
    outline itself was trusted. A side whose edge fit fell back
    (GEOMETRY_UNVERIFIED) may be a raster of mostly desk, and lines placed on it
    would publish a centering score for a card nobody has seen. The endpoint,
    recompute and the redraw all ask this one question, so they cannot disagree.
    """
    m = measurements or {}
    block = m.get("assessment") or {}
    limitations = block.get("limitations") or []
    geometry = m.get("card_geometry") or {}
    return (
        block.get("state") == assessment.UNMEASURABLE
        and assessment.CENTERING_NO_FRAME in limitations
        and not any(code in assessment.DISQUALIFYING_LIMITATIONS for code in limitations)
        and float(geometry.get("px_per_mm") or 0) > 0
    )
```

(`centering.py` already imports `assessment`; confirm with `grep -n "^from\|^import" backend/zgrader/analysis/centering.py`.)

- [ ] **Step 6: Add the constants to `scoring.py`**

Directly after `CENTERING_POINTS_PER_PCT = 1.0 / 5.0`:

```python
# ARBITRARY. How far from the card's edge a customer may place a centering
# line when detection found no printed frame. Wider than any printed border on
# the supported games, and short of letting a line be dragged across the
# artwork. Published through /catalog/branding so the page and the endpoint
# enforce one number.
CENTERING_PLACEMENT_MAX_MM = 8.0

# ARBITRARY. Where a placed line starts on a side the pipeline found nothing
# on. Only a starting position; the customer is expected to move it.
CENTERING_PLACEMENT_DEFAULT_MM = 3.0
```

- [ ] **Step 7: Add the copy**

`backend/zgrader/reports/strings.py`, in `LIMITATION_LABELS["en"]` after the `"centering_partial_frame"` entry:

```python
        "centering_client_placed": (
            "No printed border could be found on this card, so the centering lines were "
            "placed by hand rather than measured. The centering figures describe where "
            "those lines were put."
        ),
```

and in `LIMITATION_LABELS["es"]` after its `"centering_partial_frame"` entry:

```python
        "centering_client_placed": (
            "No se pudo encontrar un borde impreso en esta carta, así que las líneas de "
            "centrado se colocaron a mano en lugar de medirse. Las cifras de centrado "
            "describen dónde se pusieron esas líneas."
        ),
```

`frontend/lib/i18n/en.ts`, in `submissionDetail.limitation` after `centering_partial_frame`:

```ts
      centering_client_placed:
        "No printed border could be found, so these centering lines were placed by hand rather than measured.",
```

`frontend/lib/i18n/es.ts`, same place:

```ts
      centering_client_placed:
        "No se encontró un borde impreso, así que estas líneas de centrado se colocaron a mano en lugar de medirse.",
```

- [ ] **Step 8: Run the new tests, the moved function's tests, and the drift check**

Run: `.venv/Scripts/python.exe -m pytest tests/test_centering_placement.py tests/test_combined_sides.py tests/test_indicative_estimate.py tests/test_fixture_drift.py -v > <scratch>/pytest.log 2>&1; echo exit=$?`
Expected: all PASS, `exit=0` (no drift: nothing measured changed).

Run: `cd ../frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add backend/zgrader/analysis/assessment.py backend/zgrader/analysis/pipeline.py backend/zgrader/analysis/centering.py backend/zgrader/analysis/scoring.py backend/zgrader/reports/strings.py backend/tests/test_centering_placement.py backend/tests/test_combined_sides.py backend/tests/test_indicative_estimate.py frontend/lib/i18n/en.ts frontend/lib/i18n/es.ts
git commit -m "Add the placement primitives: code, confidence, eligibility and bounds" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Recompute scores a placement and rebuilds the combined assessment

**Files:**
- Create: `backend/tests/centering_rows.py`
- Modify: `backend/zgrader/analysis/recompute.py` (`_adjusted_side_score`, `recompute_submission`; new `placed_side`)
- Test: `backend/tests/test_centering_placement.py` (append)

**Interfaces:**
- Consumes: `centering.widths_from`, `centering.placement_eligible`, `assessment.combine_assessments`, `assessment.CENTERING_CLIENT_PLACED`, `assessment.CONFIDENCE_CENTERING_CLIENT_PLACED` (Task 2).
- Produces:
  - `recompute.placed_side(side_measurements: dict, adjustment: dict | None) -> tuple[float, float, dict] | None` — `(score, worse_side_pct, assessment_dict)` for a placed side, else `None`.
  - Combined centering rows gain `measurements["original_assessment"]` (the pipeline's combined assessment, written once).
  - `tests.centering_rows`: `PX_PER_MM`, `declined_side(*extra_limitations) -> dict`, `scored_side(left, right, top, bottom) -> dict`, `side_score(side) -> float | None`, `add_centering_rows(db, submission, front, back=None) -> None`.

This task also fixes a bug found while planning: `recompute_submission` never applied "the score follows the assessment". With the front declined and the back scored, *any* recompute (a dismissal anywhere on the card) wrote the back's score onto a combined row whose assessment says `unmeasurable`, and hoisted the back's `worse_side_pct` so centering comparisons fired. That is the SUB-00011 contradiction `_persist_combined` was fixed for, reintroduced one step later. Read from the code; the first test below is written to fail against it.

- [ ] **Step 1: Create the shared row builders**

Create `backend/tests/centering_rows.py`:

```python
"""Centering rows shaped like the pipeline's, for tests that need a declined or
scored centering side without running OpenCV.

Built by hand because `_persist_combined` needs every category's result at
once. The combined row is assembled from the same functions it uses --
`assessment.combine_assessments`, `scoring.combine_front_back`,
`scoring.combine_sides_by_name` -- and the same "score follows the assessment"
rule, so it matches what the pipeline stores.
"""

import copy

from zgrader.analysis import assessment, centering, scoring
from zgrader.models import AnalysisCategory, AnalysisResult, AnalysisSide

PX_PER_MM = 10.0


def declined_side(*extra_limitations: str) -> dict:
    """A side where no printed frame was found. Left and top were read; right
    and bottom were not, so their indicative widths are the 0.0 refusal."""
    limitations = (assessment.CENTERING_NO_FRAME, *extra_limitations)
    return {
        "indicative_estimate": {
            "left_px": 30.0,
            "right_px": 0.0,
            "top_px": 28.0,
            "bottom_px": 0.0,
            "per_side": {
                "left": {"measured": True},
                "right": {"measured": False},
                "top": {"measured": True},
                "bottom": {"measured": False},
            },
        },
        "assessment": assessment.unmeasurable(limitations).as_dict(),
        "card_geometry": {"px_per_mm": PX_PER_MM},
        "regions": [],
    }


def scored_side(left: float = 30.0, right: float = 34.0, top: float = 30.0, bottom: float = 30.0) -> dict:
    ratios = centering.ratios_from_widths(left, right, top, bottom)
    score = round(centering.score_from_worse_pct(ratios["worse_side_pct"]), 2)
    return {
        "left_px": left,
        "right_px": right,
        "top_px": top,
        "bottom_px": bottom,
        "lr_ratio": ratios["lr_ratio"],
        "tb_ratio": ratios["tb_ratio"],
        "worse_side_pct": ratios["worse_side_pct"],
        "assessment": assessment.measured(score, assessment.CONFIDENCE_CENTERING_CLEAN_FRAME).as_dict(),
        "card_geometry": {"px_per_mm": PX_PER_MM},
        "regions": [],
    }


def side_score(side: dict | None) -> float | None:
    if side is None or side["assessment"]["state"] != assessment.MEASURED:
        return None
    return round(centering.score_from_worse_pct(side["worse_side_pct"]), 2)


def add_centering_rows(db, submission, front: dict, back: dict | None = None) -> None:
    for side_enum, measurements in ((AnalysisSide.front, front), (AnalysisSide.back, back)):
        if measurements is None:
            continue
        db.add(
            AnalysisResult(
                submission_id=submission.id,
                category=AnalysisCategory.centering,
                side=side_enum,
                raw_score=side_score(measurements),
                measurements=copy.deepcopy(measurements),
                flags={},
            )
        )

    combined: dict = {"front": copy.deepcopy(front)}
    if back is not None:
        combined["back"] = copy.deepcopy(back)
    if front.get("worse_side_pct") is not None:
        combined["worse_side_pct"] = round(
            scoring.combine_front_back(front["worse_side_pct"], (back or {}).get("worse_side_pct")), 1
        )
        combined["original_worse_side_pct"] = combined["worse_side_pct"]
    combined["assessment"] = assessment.combine_assessments(
        front["assessment"], back["assessment"] if back else None
    )
    scores = {
        name: score
        for name, score in (("front", side_score(front)), ("back", side_score(back)))
        if score is not None
    }
    raw = (
        scoring.combine_sides_by_name(scores)
        if combined["assessment"]["state"] == assessment.MEASURED
        else None
    )
    combined["original_raw_score"] = raw
    db.add(
        AnalysisResult(
            submission_id=submission.id,
            category=AnalysisCategory.centering,
            side=AnalysisSide.combined,
            raw_score=raw,
            measurements=combined,
            flags={},
        )
    )
    db.flush()
```

- [ ] **Step 2: Append the failing tests**

Append to `backend/tests/test_centering_placement.py`, moving the import block below up to join the file's existing imports at the top:

```python
# --- recompute: a placement becomes a reading, and clearing undoes it -----

import copy

from zgrader.analysis import recompute
from zgrader.auth.security import hash_password
from zgrader.models import (
    AnalysisCategory,
    AnalysisResult,
    AnalysisSide,
    GradingCompanyComparison,
    Submission,
    SubmissionLanguage,
    SubmissionStatus,
    User,
)

from tests.centering_rows import add_centering_rows, declined_side, scored_side, side_score

#: T/B 25/35 is a 41.7/58.3 split; L/R is even. So the worse side is 58.3.
PLACED = {"left_px": 30.0, "right_px": 30.0, "top_px": 25.0, "bottom_px": 35.0}


def _placed_score() -> tuple[float, float]:
    worse = centering.ratios_from_widths(*centering.widths_from(PLACED))["worse_side_pct"]
    return round(centering.score_from_worse_pct(worse), 2), worse


def _submission(db_session, code: str) -> Submission:
    user = User(email=f"{code.lower()}@example.com", hashed_password=hash_password("hunter2pass"), is_verified=True)
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code=code,
        user_id=user.id,
        status=SubmissionStatus.draft_ready,
        language=SubmissionLanguage.en,
    )
    db_session.add(submission)
    db_session.flush()
    return submission


def _with_rows(db_session, code, front, back=None) -> Submission:
    submission = _submission(db_session, code)
    add_centering_rows(db_session, submission, front, back)
    db_session.commit()
    db_session.refresh(submission)
    return submission


def _combined(db_session, submission) -> AnalysisResult:
    db_session.expire_all()
    return (
        db_session.query(AnalysisResult)
        .filter_by(submission_id=submission.id, category=AnalysisCategory.centering, side=AnalysisSide.combined)
        .one()
    )


def _centering_comparisons(db_session, submission) -> int:
    return (
        db_session.query(GradingCompanyComparison)
        .filter_by(submission_id=submission.id, category="centering")
        .count()
    )


def _set_adjustment(db_session, submission, side, widths) -> None:
    adjustments = dict(submission.centering_adjustments or {})
    if widths is None:
        adjustments.pop(side, None)
    else:
        adjustments[side] = dict(widths)
    submission.centering_adjustments = adjustments or None
    recompute.recompute_submission(db_session, submission)
    db_session.commit()


def test_recompute_never_resurrects_a_score_the_front_declined(db_session):
    """Front declined, back scored: the combined reading is unmeasurable, and a
    recompute for any reason must leave it that way -- no number, no hoisted
    worse_side_pct, no centering comparisons."""
    submission = _with_rows(db_session, "SUB-PLC00", declined_side(), scored_side())
    assert _combined(db_session, submission).raw_score is None

    recompute.recompute_submission(db_session, submission)
    db_session.commit()

    row = _combined(db_session, submission)
    assert row.raw_score is None
    assert "worse_side_pct" not in row.measurements
    assert _centering_comparisons(db_session, submission) == 0


def test_placing_a_declined_front_scores_the_combined_row(db_session):
    submission = _with_rows(db_session, "SUB-PLC01", declined_side())

    _set_adjustment(db_session, submission, "front", PLACED)

    row = _combined(db_session, submission)
    score, worse = _placed_score()
    block = row.measurements["assessment"]
    assert float(row.raw_score) == score
    assert block["state"] == "measured"
    assert block["limitations"] == [assessment.CENTERING_CLIENT_PLACED]
    assert block["confidence"] == assessment.CONFIDENCE_CENTERING_CLIENT_PLACED
    assert row.measurements["worse_side_pct"] == round(worse, 1)
    assert _centering_comparisons(db_session, submission) > 0


def test_clearing_a_placement_restores_the_original_exactly(db_session):
    """The reverse direction, which is where the equivalent bugs lived. The
    helper's rows carry no `original_assessment`, like every row analysed
    before this shipped, so this also covers the first-recompute case."""
    submission = _with_rows(db_session, "SUB-PLC02", declined_side())
    original = copy.deepcopy(_combined(db_session, submission).measurements["assessment"])

    _set_adjustment(db_session, submission, "front", PLACED)
    _set_adjustment(db_session, submission, "front", None)

    row = _combined(db_session, submission)
    assert row.raw_score is None
    assert row.measurements["assessment"] == original
    assert row.measurements["original_assessment"] == original
    assert "worse_side_pct" not in row.measurements
    assert _centering_comparisons(db_session, submission) == 0


def test_a_side_whose_edges_were_not_found_is_not_placed(db_session):
    submission = _with_rows(db_session, "SUB-PLC03", declined_side(assessment.GEOMETRY_UNVERIFIED))

    _set_adjustment(db_session, submission, "front", PLACED)

    assert _combined(db_session, submission).raw_score is None


def test_a_placed_back_combines_with_a_scored_front(db_session):
    front = scored_side()
    submission = _with_rows(db_session, "SUB-PLC04", front, declined_side())

    _set_adjustment(db_session, submission, "back", PLACED)

    row = _combined(db_session, submission)
    block = row.measurements["assessment"]
    assert block["state"] == "measured"
    assert assessment.CENTERING_CLIENT_PLACED in block["limitations"]
    assert block["confidence"] == assessment.CONFIDENCE_CENTERING_CLIENT_PLACED
    assert float(row.raw_score) == scoring.combine_sides_by_name(
        {"front": side_score(front), "back": _placed_score()[0]}
    )


def test_a_placed_front_with_an_unplaced_declined_back_is_a_single_side_reading(db_session):
    submission = _with_rows(db_session, "SUB-PLC05", declined_side(), declined_side())

    _set_adjustment(db_session, submission, "front", PLACED)

    block = _combined(db_session, submission).measurements["assessment"]
    assert block["state"] == "measured"
    assert assessment.COMBINED_SINGLE_SIDE in block["limitations"]
    assert block["confidence"] == round(
        assessment.CONFIDENCE_CENTERING_CLIENT_PLACED * assessment.CONFIDENCE_SINGLE_SIDE_FACTOR, 2
    )


def test_placed_side_needs_an_axis_with_both_lines_inside_the_card():
    """Every line at the card's edge leaves no axis at all, and
    ratios_from_widths would fall back to a perfect 50/50."""
    zeros = {"left_px": 0, "right_px": 0, "top_px": 0, "bottom_px": 0}
    assert recompute.placed_side(declined_side(), zeros) is None
    assert recompute.placed_side(declined_side(), PLACED) is not None
```

- [ ] **Step 3: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_centering_placement.py -v > <scratch>/pytest.log 2>&1; echo exit=$?`
Expected: the Task 2 tests pass; every new test FAILS — `test_recompute_never_resurrects...` on `assert row.raw_score is None` (a number is written), the rest on missing placement behaviour or `AttributeError: ... 'placed_side'`.

- [ ] **Step 4: Add `placed_side` and the branch in `_adjusted_side_score`**

In `backend/zgrader/analysis/recompute.py`, add above `_adjusted_side_score`:

```python
def placed_side(side_measurements: dict, adjustment: dict | None) -> tuple[float, float, dict] | None:
    """Score, worse-side percentage and assessment for a side whose centering
    lines the customer placed by hand; None if this side is not a placement.

    A placement exists only where the pipeline declined for want of a printed
    frame on a trusted card outline (`centering.placement_eligible`). The widths
    are scored through the same functions as a measurement, and the assessment
    says plainly that nobody measured them.
    """
    widths = centering.widths_from(adjustment)
    if widths is None or not centering.placement_eligible(side_measurements):
        return None
    left, right, top, bottom = widths
    ratios = centering.ratios_from_widths(
        left, right, top, bottom, have_lr=left + right > 0, have_tb=top + bottom > 0
    )
    if ratios["measured_axes"] == 0:
        return None
    worse = float(ratios["worse_side_pct"])
    score = round(centering.score_from_worse_pct(worse), 2)
    block = assessment.measured(
        score,
        assessment.CONFIDENCE_CENTERING_CLIENT_PLACED,
        (assessment.CENTERING_CLIENT_PLACED,),
    ).as_dict()
    return score, worse, block
```

In `_adjusted_side_score`, insert at the very top of the body (after the docstring, before `state = ...`):

```python
    # A placement turns a declined centering side into a reading, so it has to
    # be checked before the guard below, which exists to keep every *other*
    # declined state declined -- including ones nobody has written yet.
    if category == "centering":
        placed = placed_side(side_measurements, centering_adjustment)
        if placed is not None:
            return placed[0], placed[1]
```

- [ ] **Step 5: Rebuild the combined assessment and make the score follow it**

In `recompute_submission`, replace the per-row body from `scores_by_side: dict[str, float] = {}` down to and including `row.measurements = measurements  # reassign so SQLAlchemy tracks the JSONB change` with:

```python
        scores_by_side: dict[str, float] = {}
        worse_by_side: dict[str, float] = {}
        # The assessment in force per side: a placement's, or what was stored.
        effective: dict[str, dict | None] = {}
        for side in ("front", "back"):
            side_m = measurements.get(side)
            if side_m is None:
                continue
            adjustment = adjustments.get(side) if category == "centering" else None
            placed = placed_side(side_m, adjustment) if category == "centering" else None
            effective[side] = placed[2] if placed else side_m.get("assessment")
            score, worse = _adjusted_side_score(
                category,
                side_m,
                dismissed.get((side, category), set()),
                adjustment,
            )
            if score is None:
                score = stored_side_scores.get((side, category))
                worse = side_m.get("worse_side_pct")
            if score is None:
                continue
            scores_by_side[side] = score
            if worse is not None:
                worse_by_side[side] = float(worse)

        if category == "centering":
            # A placement can turn a declined side into a reading, so the
            # combined assessment is rebuilt from what is in force. The
            # pipeline's own is kept the first time this runs -- rows analysed
            # before placement existed have none -- so clearing restores it.
            measurements.setdefault("original_assessment", measurements.get("assessment"))
            measurements["assessment"] = assessment.combine_assessments(
                effective.get("front"), effective.get("back")
            )

        combined = scoring.combine_sides_by_name(scores_by_side)
        state = (measurements.get("assessment") or {}).get("state")
        if state is not None and state != assessment.MEASURED:
            # The score follows the assessment, as in pipeline._persist_combined.
            # Without this a front-declined card with a scored back took the
            # back's number on every recompute -- the SUB-00011 contradiction.
            combined = None
        elif combined is None:
            # Nothing derivable and nothing saying otherwise: leave the row.
            continue

        row.raw_score = combined
        if category == "centering":
            if combined is None:
                # No reading, so nothing for the rules engine to compare.
                measurements.pop("worse_side_pct", None)
            elif worse_by_side:
                combined_worse = scoring.combine_sides_by_name(worse_by_side)
                if combined_worse is not None:
                    measurements["worse_side_pct"] = round(combined_worse, 1)
            row.measurements = measurements  # reassign so SQLAlchemy tracks the JSONB change
```

- [ ] **Step 6: Run the placement tests and every recompute consumer**

Run: `.venv/Scripts/python.exe -m pytest tests/test_centering_placement.py tests/test_centering_adjust.py tests/test_recompute.py tests/test_unmeasurable.py tests/test_combined_sides.py -v > <scratch>/pytest.log 2>&1; echo exit=$?`
Expected: all PASS, `exit=0`. `test_an_unmeasurable_side_is_not_rescued_by_an_adjustment` still passes: its assessment carries no `centering_no_frame`, so it is not placement-eligible.

- [ ] **Step 7: Commit**

```bash
git add backend/zgrader/analysis/recompute.py backend/tests/centering_rows.py backend/tests/test_centering_placement.py
git commit -m "Score a placed centering side and keep the combined score behind its assessment" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: The endpoint — place mode, bounds, draft-only gate, DELETE, published bounds

**Files:**
- Modify: `backend/zgrader/api/routers/submissions.py` (imports line 11; `adjust_centering` ~lines 815–935; new helpers and route)
- Modify: `backend/zgrader/schemas/catalog.py` (`BrandingOut`, ~line 36), `backend/zgrader/api/routers/catalog.py` (`get_branding`, ~line 85)
- Modify (only if Step 6 finds any): `backend/tests/test_api_submissions.py`
- Test: `backend/tests/test_centering_placement_api.py` (create), `backend/tests/test_api_catalog.py` (append)

**Interfaces:**
- Consumes: `centering.placement_eligible`, `recompute.placed_side`, `scoring.CENTERING_PLACEMENT_MAX_MM`, `scoring.CENTERING_PLACEMENT_DEFAULT_MM`; `tests.centering_rows` (Task 3).
- Produces:
  - `POST /submissions/{code}/centering-adjust` — body unchanged (`CenteringAdjustIn`); place mode on eligible declined sides.
  - `DELETE /submissions/{code}/centering-adjust/{side}` → `SubmissionDetail`.
  - Audit actions `centering_placed`, `centering_placement_cleared` (beside existing `centering_adjusted`, `centering_adjust_cleared`).
  - `GET /catalog/branding` gains `centering_placement_max_mm: float` and `centering_placement_default_mm: float`.

- [ ] **Step 1: Write the failing API tests**

Create `backend/tests/test_centering_placement_api.py`:

```python
"""The centering-adjust endpoint: place mode, its bounds, and the draft-only gate.

The bounds are enforced here, not only in the page: a limit that lives in the
browser is a suggestion. And adjusting is refused once a report leaves review,
because the public share page renders from the database -- an adjustment after
publication would change what a stranger sees with no operator review.
"""

import pytest
from fastapi.testclient import TestClient

from zgrader.analysis import assessment, scoring
from zgrader.api.main import app
from zgrader.db import SessionLocal
from zgrader.models import AuditLog, Submission, SubmissionStatus
from zgrader.models.settings import get_or_create_settings

from tests.centering_rows import PX_PER_MM, add_centering_rows, declined_side, scored_side
from tests.conftest import register_and_verify

client = TestClient(app)

PLACED = {"left_px": 30.0, "right_px": 30.0, "top_px": 25.0, "bottom_px": 35.0}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _owned_submission(email, front, back=None, status=SubmissionStatus.draft_ready) -> tuple[str, str]:
    token = register_and_verify(client, email)
    resp = client.post("/submissions", json={"game": "Pokemon", "card_name": "Snorlax"}, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    code = resp.json()["submission_code"]
    with SessionLocal() as db:
        submission = db.query(Submission).filter(Submission.submission_code == code).one()
        submission.status = status
        add_centering_rows(db, submission, front, back)
        db.commit()
    return token, code


def _post(token, code, side="front", widths=PLACED):
    return client.post(
        f"/submissions/{code}/centering-adjust", json={"side": side, **widths}, headers=_auth(token)
    )


def _delete(token, code, side="front"):
    return client.delete(f"/submissions/{code}/centering-adjust/{side}", headers=_auth(token))


def _combined_centering(body: dict) -> dict:
    return next(
        r for r in body["analysis_results"] if r["category"] == "centering" and r["side"] == "combined"
    )


def test_a_declined_side_accepts_a_placement(db_session):
    token, code = _owned_submission("place-ok@example.com", declined_side())

    resp = _post(token, code)

    assert resp.status_code == 200, resp.text
    combined = _combined_centering(resp.json())
    assert combined["raw_score"] is not None
    assert assessment.CENTERING_CLIENT_PLACED in combined["measurements"]["assessment"]["limitations"]
    assert resp.json()["centering_adjustments"]["front"] == PLACED


def test_a_line_further_than_the_bound_is_refused(db_session):
    token, code = _owned_submission("place-far@example.com", declined_side())
    too_far = {**PLACED, "top_px": (scoring.CENTERING_PLACEMENT_MAX_MM + 0.5) * PX_PER_MM}

    assert _post(token, code, widths=too_far).status_code == 400


def test_a_placement_with_no_axis_inside_the_card_is_refused(db_session):
    token, code = _owned_submission("place-zero@example.com", declined_side())
    zeros = {"left_px": 0.0, "right_px": 0.0, "top_px": 0.0, "bottom_px": 0.0}

    assert _post(token, code, widths=zeros).status_code == 400


def test_a_side_whose_edges_were_not_found_is_refused(db_session):
    token, code = _owned_submission(
        "place-unverified@example.com", declined_side(assessment.GEOMETRY_UNVERIFIED)
    )

    assert _post(token, code).status_code == 409


def test_the_kill_switch_disables_placement_too(db_session):
    token, code = _owned_submission("place-off@example.com", declined_side())
    with SessionLocal() as db:
        get_or_create_settings(db).centering_adjust_limit_mm = 0
        db.commit()

    assert _post(token, code).status_code == 403


@pytest.mark.parametrize("status", [SubmissionStatus.published, SubmissionStatus.awaiting_scans])
def test_adjusting_is_refused_outside_draft_review(db_session, status):
    token, code = _owned_submission(f"place-{status.value}@example.com", declined_side(), status=status)

    assert _post(token, code).status_code == 409
    assert _delete(token, code).status_code == 409


def test_nudging_is_refused_after_publication_too(db_session):
    token, code = _owned_submission(
        "nudge-published@example.com", scored_side(), status=SubmissionStatus.published
    )
    nudged = {"left_px": 31.0, "right_px": 34.0, "top_px": 30.0, "bottom_px": 30.0}

    assert _post(token, code, widths=nudged).status_code == 409


def test_nudging_a_scored_side_still_works(db_session):
    token, code = _owned_submission("nudge-ok@example.com", scored_side())
    nudged = {"left_px": 31.0, "right_px": 34.0, "top_px": 30.0, "bottom_px": 30.0}

    resp = _post(token, code, widths=nudged)

    assert resp.status_code == 200, resp.text
    assert resp.json()["centering_adjustments"]["front"] == nudged


def test_delete_clears_a_placement_and_records_both_actions(db_session):
    token, code = _owned_submission("place-clear@example.com", declined_side())
    assert _post(token, code).status_code == 200

    resp = _delete(token, code)

    assert resp.status_code == 200, resp.text
    assert _combined_centering(resp.json())["raw_score"] is None
    assert not resp.json()["centering_adjustments"]
    with SessionLocal() as db:
        submission = db.query(Submission).filter(Submission.submission_code == code).one()
        actions = {a.action for a in db.query(AuditLog).filter(AuditLog.submission_id == submission.id)}
    assert {"centering_placed", "centering_placement_cleared"} <= actions


def test_deleting_with_nothing_stored_is_a_no_op(db_session):
    token, code = _owned_submission("place-noop@example.com", declined_side())

    resp = _delete(token, code)

    assert resp.status_code == 200, resp.text
    assert _combined_centering(resp.json())["raw_score"] is None
```

Append to `backend/tests/test_api_catalog.py`:

```python
def test_branding_publishes_the_placement_bounds(db_session):
    """The page bounds the drag handles with the numbers the endpoint enforces,
    so it must be given them rather than keeping its own copy."""
    from zgrader.analysis import scoring

    body = client.get("/catalog/branding").json()

    assert body["centering_placement_max_mm"] == scoring.CENTERING_PLACEMENT_MAX_MM
    assert body["centering_placement_default_mm"] == scoring.CENTERING_PLACEMENT_DEFAULT_MM
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_centering_placement_api.py tests/test_api_catalog.py -v > <scratch>/pytest.log 2>&1; echo exit=$?`
Expected: FAIL — placements answer 409 (today's refusal), DELETE answers 405, the published-status tests get 200, the branding keys are missing. `test_nudging_a_scored_side_still_works` and `test_a_side_whose_edges_were_not_found_is_refused` already pass.

- [ ] **Step 3: Add the gate and row helpers, and the imports**

In `backend/zgrader/api/routers/submissions.py`, change the analysis import to:

```python
from zgrader.analysis import artifacts, assessment, centering, pipeline, preprocessing, recompute, scale, scoring
```

Add directly above the `@router.post("/{code}/centering-adjust", ...)` decorator:

```python
def _require_draft_under_review(submission: Submission) -> None:
    """Centering lines can only move while the draft is under review.

    The public share page renders from the database, not the PDF, so an
    adjustment after publication would change what a stranger sees with no
    operator review, and leave the published PDF disagreeing with the page.
    The same gate as toggle_region.
    """
    if submission.status != SubmissionStatus.draft_ready:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Submission is '{submission.status.value}' -- centering can only be adjusted while the draft is under review",
        )


def _centering_side_row(submission: Submission, side: str):
    return next(
        (
            r
            for r in submission.analysis_results
            if r.category == AnalysisCategory.centering and r.side.value == side
        ),
        None,
    )
```

- [ ] **Step 4: Rewrite the body of `adjust_centering`**

Keep the decorator, signature and docstring; append to the docstring:

```text
    On a side the pipeline declined for want of a printed frame, this places the
    lines instead (`centering.placement_eligible`): there is no detected line to
    bound against, so each line must sit within CENTERING_PLACEMENT_MAX_MM of the
    card's edge, and the result is scored and labelled as placed by hand.
```

Replace everything from `submission = _get_owned_submission(code, user, db)` to the end of the function with:

```python
    submission = _get_owned_submission(code, user, db)
    _require_draft_under_review(submission)

    side_row = _centering_side_row(submission, payload.side)
    if side_row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"No centering analysis for the {payload.side}"
        )

    measured = side_row.measurements or {}
    placing = side_row.raw_score is None and centering.placement_eligible(measured)
    # An unscored side that is not placeable -- above all one whose card edges
    # were never found -- has nothing trustworthy to put lines on. Accepting
    # would invent centering for a card the pipeline could not locate.
    if side_row.raw_score is None and not placing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Centering could not be measured on this side, so its lines cannot be adjusted.",
        )

    settings = get_or_create_settings(db)
    limit_mm = float(settings.centering_adjust_limit_mm or 0)
    if limit_mm <= 0:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Adjusting the centering lines is currently disabled."
        )

    geometry = measured.get("card_geometry") or {}
    px_per_mm = float(geometry.get("px_per_mm") or 0)
    if px_per_mm <= 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This submission has no recorded scale to bound the move against."
        )

    proposed = {
        "left_px": payload.left_px,
        "right_px": payload.right_px,
        "top_px": payload.top_px,
        "bottom_px": payload.bottom_px,
    }
    rounded = {k: round(v, 1) for k, v in proposed.items()}

    if placing:
        max_mm = scoring.CENTERING_PLACEMENT_MAX_MM
        for key, value in proposed.items():
            if value > max_mm * px_per_mm + 1e-6:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"{key} is further than {max_mm:g}mm from the card's edge.",
                )
        if recompute.placed_side(measured, rounded) is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Place at least one pair of opposite lines inside the card's edge.",
            )
        detected_rounded = None
        cleared = False
    else:
        limit_px = limit_mm * px_per_mm
        for key, value in proposed.items():
            detected = measured.get(key)
            if detected is None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, f"No detected {key} to adjust from on this side."
                )
            if abs(value - float(detected)) > limit_px + 1e-6:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"{key} moved further than the {limit_mm:g}mm allowed.",
                )
        detected_rounded = {k: round(float(measured[k]), 1) for k in proposed}
        # Putting every line back where detection had it is not an adjustment,
        # so it clears rather than stores one -- see DELETE below for the
        # explicit form, which is the only one a placement has.
        cleared = rounded == detected_rounded

    adjustments = dict(submission.centering_adjustments or {})
    if cleared:
        adjustments.pop(payload.side, None)
    else:
        adjustments[payload.side] = rounded
    # NULL rather than {} when nothing is left, so `client_adjusted` (a plain
    # truthiness check) reads False again.
    submission.centering_adjustments = adjustments or None

    action = (
        "centering_placed"
        if placing
        else "centering_adjust_cleared" if cleared else "centering_adjusted"
    )
    db.add(
        AuditLog(
            submission_id=submission.id,
            user_id=user.id,
            action=action,
            detail={
                "side": payload.side,
                "detected": detected_rounded,
                "adjusted": None if cleared else rounded,
            },
        )
    )
    db.flush()

    recompute.recompute_submission(db, submission)
    db.commit()
    db.refresh(submission)
    return submission
```

Before replacing, diff the old body against this: the nudge branch must keep the existing messages and bounds exactly. Only the gate, the place branch and the audit action are new.

- [ ] **Step 5: Add the DELETE route**

Directly after `adjust_centering`:

```python
@router.delete(
    "/{code}/centering-adjust/{side}",
    response_model=SubmissionDetail,
    dependencies=[Depends(_submission_adjust_limit)],
)
def clear_centering_adjustment(
    code: str,
    side: Literal["front", "back"],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Submission:
    """Remove one side's centering adjustment or placement, and rescore.

    A placement has no detected lines to move back to, so "put every line where
    it was" cannot clear it the way it clears a nudge; this is the explicit way,
    and it works for both. Clearing a side with nothing stored changes nothing.
    """
    submission = _get_owned_submission(code, user, db)
    _require_draft_under_review(submission)

    adjustments = dict(submission.centering_adjustments or {})
    if side in adjustments:
        adjustments.pop(side)
        submission.centering_adjustments = adjustments or None
        side_row = _centering_side_row(submission, side)
        was_placement = side_row is not None and side_row.raw_score is None
        db.add(
            AuditLog(
                submission_id=submission.id,
                user_id=user.id,
                action="centering_placement_cleared" if was_placement else "centering_adjust_cleared",
                detail={"side": side},
            )
        )
        db.flush()
        recompute.recompute_submission(db, submission)

    db.commit()
    db.refresh(submission)
    return submission
```

- [ ] **Step 6: Publish the bounds**

In `backend/zgrader/schemas/catalog.py` `BrandingOut`, directly after `centering_adjust_limit_mm: float`:

```python
    # Where a hand-placed centering line may sit (0 to max mm from the card's
    # edge) and where an unfound side's line starts. Constants in
    # analysis/scoring.py rather than settings, published so the page bounds
    # its handles with the numbers the endpoint enforces.
    centering_placement_max_mm: float
    centering_placement_default_mm: float
```

In `backend/zgrader/api/routers/catalog.py`, add `from zgrader.analysis import scoring` to the imports, add above `get_branding`:

```python
# BrandingOut fields that do not come from the Settings row.
_NOT_FROM_SETTINGS = {
    "grading_companies",
    "centering_placement_max_mm",
    "centering_placement_default_mm",
}
```

and replace the `return BrandingOut(...)` in `get_branding` with:

```python
    return BrandingOut(
        **{
            field: getattr(settings, field)
            for field in BrandingOut.model_fields
            if field not in _NOT_FROM_SETTINGS
        },
        grading_companies=_active_grading_companies(db),
        centering_placement_max_mm=scoring.CENTERING_PLACEMENT_MAX_MM,
        centering_placement_default_mm=scoring.CENTERING_PLACEMENT_DEFAULT_MM,
    )
```

- [ ] **Step 7: Find existing tests that adjust outside draft review**

Run: `grep -rn "centering-adjust" backend/tests --include=*.py`
For each hit outside the two new files, read its setup. If it POSTs to `centering-adjust` on a submission not in `draft_ready`, add `submission.status = SubmissionStatus.draft_ready` to that setup before the POST. This is the confirmed behaviour change; do not weaken the gate to make an old test pass.

- [ ] **Step 8: Run the endpoint tests, the route-coverage test and the related suites**

Run: `.venv/Scripts/python.exe -m pytest tests/test_centering_placement_api.py tests/test_api_catalog.py tests/test_rate_limit_coverage.py tests/test_api_submissions.py tests/test_centering_adjust.py tests/test_centering_placement.py -v > <scratch>/pytest.log 2>&1; echo exit=$?`
Expected: all PASS, `exit=0`. `test_rate_limit_coverage` passes because the DELETE carries `_submission_adjust_limit`.

- [ ] **Step 9: Commit**

```bash
git add backend/zgrader/api/routers/submissions.py backend/zgrader/schemas/catalog.py backend/zgrader/api/routers/catalog.py backend/tests/test_centering_placement_api.py backend/tests/test_api_catalog.py backend/tests/test_api_submissions.py
git commit -m "Place centering lines on a declined side, gate adjusting to draft review, add DELETE" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: The drawing and the PDF carry the placement

**Files:**
- Modify: `backend/zgrader/analysis/recompute.py` (`redraw_centering_annotations`, ~line 201)
- Test: `backend/tests/test_centering_annotation_redraw.py` (append), `backend/tests/test_centering_placement_end_to_end.py` (create)

**Interfaces:**
- Consumes: `centering.placement_eligible`, `centering.widths_from`, `centering.WIDTH_KEYS` (Task 2); `recompute_submission` placement behaviour (Task 3); `builder` watermark fix (Task 1).
- Produces: `redraw_centering_annotations` rewrites a placement-eligible declined row's image — the placed lines when a placement exists, the plain card when not.

- [ ] **Step 1: Append the failing redraw test**

Append to `backend/tests/test_centering_annotation_redraw.py`. It reuses the file's `_submission_with_analysis` and `_centering_row`; read `_centering_row` first — it must return the **front** per-side row, so if its filter does not already include `AnalysisResult.side == AnalysisSide.front`, add that.

```python
def _full_art_scan(tmp_path):
    """A card with no printed frame: centering declines with centering_no_frame
    while the edge fit holds, which is exactly the placeable case."""
    import cv2

    from tests.fixtures.generate_samples import build_fixture

    path = tmp_path / "full_art_centered.png"
    cv2.imwrite(str(path), build_fixture("full_art_centered"))
    return path


def _pixels(path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.int16)


def _changed(a: np.ndarray, b: np.ndarray) -> int:
    """Pixels that differ by more than JPEG noise."""
    return int((np.abs(a - b).max(axis=2) > 60).sum())


def test_a_placed_side_is_drawn_from_the_placement_and_cleared_back_to_plain(db_session, tmp_path):
    from zgrader.analysis import centering

    submission = _submission_with_analysis(db_session, "SUB-PLD01", _full_art_scan(tmp_path), tmp_path)
    row = _centering_row(db_session, submission)
    assert row.raw_score is None
    assert centering.placement_eligible(row.measurements)
    plain = _pixels(row.annotated_image_path)
    ppm = row.measurements["card_geometry"]["px_per_mm"]

    submission.centering_adjustments = {
        "front": {"left_px": 2.5 * ppm, "right_px": 3.5 * ppm, "top_px": 3.0 * ppm, "bottom_px": 3.0 * ppm}
    }
    db_session.commit()
    assert recompute.redraw_centering_annotations(db_session, submission) == [row.annotated_image_path]
    assert _changed(_pixels(row.annotated_image_path), plain) > 500, "the placed frame was not drawn"

    submission.centering_adjustments = None
    db_session.commit()
    recompute.redraw_centering_annotations(db_session, submission)
    assert _changed(_pixels(row.annotated_image_path), plain) < 50, "clearing left the placed lines behind"
```

- [ ] **Step 2: Create the failing end-to-end test**

Create `backend/tests/test_centering_placement_end_to_end.py`:

```python
"""A placed centering must reach the combined row, the comparisons and the PDF.

Goes through run_dev_trigger -- the whole pipeline on a full-art fixture whose
centering declines -- then places lines and generates the report, rather than
trusting each piece separately. AGENTS.md: every time a category gained the
ability to decline, something downstream assumed it could not; this is the
first time a declined category can be un-declined, and the same applies.
"""

import cv2
from pypdf import PdfReader

from tests.fixtures.generate_samples import build_fixture
from zgrader.analysis import assessment, centering, recompute
from zgrader.dev_trigger import run_dev_trigger
from zgrader.models import (
    AnalysisCategory,
    AnalysisResult,
    AnalysisSide,
    GradingCompanyComparison,
    Submission,
)
from zgrader.reports import builder


def _pdf_text(path) -> str:
    return " ".join(" ".join(page.extract_text().split()) for page in PdfReader(str(path)).pages)


def test_a_placed_centering_reaches_the_report(db_session, tmp_path):
    front = tmp_path / "full_art_front.png"
    cv2.imwrite(str(front), build_fixture("full_art_centered"))
    result = run_dev_trigger(
        front_path=str(front),
        back_path=None,
        game="Pokemon",
        card_name="Full Art",
        user_email="placed@example.com",
        submission_code="SUB-PLACE1",
    )
    assert result["status"] == "draft_ready"

    submission = db_session.query(Submission).filter_by(submission_code="SUB-PLACE1").one()
    front_row = (
        db_session.query(AnalysisResult)
        .filter_by(submission_id=submission.id, side=AnalysisSide.front, category=AnalysisCategory.centering)
        .one()
    )
    assert front_row.raw_score is None
    assert centering.placement_eligible(front_row.measurements)

    ppm = front_row.measurements["card_geometry"]["px_per_mm"]
    submission.centering_adjustments = {
        "front": {
            "left_px": round(2.5 * ppm, 1),
            "right_px": round(3.5 * ppm, 1),
            "top_px": round(3.0 * ppm, 1),
            "bottom_px": round(3.0 * ppm, 1),
        }
    }
    recompute.recompute_submission(db_session, submission)
    db_session.commit()

    db_session.expire_all()
    combined = (
        db_session.query(AnalysisResult)
        .filter_by(submission_id=submission.id, side=AnalysisSide.combined, category=AnalysisCategory.centering)
        .one()
    )
    assert combined.raw_score is not None
    assert assessment.CENTERING_CLIENT_PLACED in combined.measurements["assessment"]["limitations"]
    assert (
        db_session.query(GradingCompanyComparison)
        .filter_by(submission_id=submission.id, category="centering")
        .count()
        > 0
    )

    report = builder.generate_report(db_session, submission)
    db_session.commit()
    assert report.pdf_path.endswith("_client_adjusted.pdf")
    assert "placed by hand" in _pdf_text(report.pdf_path)
```

- [ ] **Step 3: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_centering_annotation_redraw.py tests/test_centering_placement_end_to_end.py -v > <scratch>/pytest.log 2>&1; echo exit=$?`
Expected: the redraw test FAILS (`redraw_centering_annotations` returns `[]` for the unscored row). The end-to-end test should already get as far as the PDF: if it passes at this point, that is Tasks 1–3 doing their job, and it still guards the chain.

PDF tests need WeasyPrint's Pango on Windows (see AGENTS.md). If the log shows a Pango/`0x7e` import error instead of an assertion, fix the environment per AGENTS.md; do not skip the test.

- [ ] **Step 4: Teach the redraw about placeable rows**

In `redraw_centering_annotations`, add `centering` to the function's local imports if absent (`from zgrader.analysis import annotate, centering, pipeline, scale`), then replace the loop body — from `if not row.annotated_image_path or row.raw_score is None:` to `rewritten.append(row.annotated_image_path)` — with:

```python
        if not row.annotated_image_path:
            continue
        measurements = row.measurements or {}
        # A declined side is drawn only when it can be placed. With a placement
        # it shows the customer's lines; without one, the plain card -- which is
        # what analysis saved -- so clearing a placement leaves nothing behind.
        # Any other unscored side stays undrawn: build_regions and
        # _annotate_category decline together, and a redraw here would assert a
        # border analysis refused to claim.
        placeable = row.raw_score is None and centering.placement_eligible(measurements)
        if row.raw_score is None and not placeable:
            continue

        scan = scans.get(ScanSide(row.side.value))
        if scan is None or (not placeable and "left_px" not in measurements):
            continue

        try:
            rectified = pipeline.load_deskewed_card(scan, width_mm, height_mm)
        except ValueError:
            # A scan that no longer rectifies must not stop a report being
            # generated; the previous drawing stays.
            continue

        if placeable:
            widths = centering.widths_from(adjustments.get(row.side.value))
            if widths is None:
                image = annotate.to_pil(rectified.image)
            else:
                merged = dict(zip(centering.WIDTH_KEYS, widths))
                left, right, top, bottom = widths
                ratios = centering.ratios_from_widths(
                    left, right, top, bottom, have_lr=left + right > 0, have_tb=top + bottom > 0
                )
                # An axis the customer left at the card's edge has no split; the
                # label then reads 50/50 for it, which the placed-by-hand note
                # beside the score qualifies.
                merged["lr_ratio"] = ratios["lr_ratio"] or [50.0, 50.0]
                merged["tb_ratio"] = ratios["tb_ratio"] or [50.0, 50.0]
                image = annotate.annotate_centering(rectified.image, merged)
        else:
            merged = dict(measurements)
            merged.update(adjustments.get(row.side.value) or {})
            # Ratios from the same function the score routes through, so the
            # numbers printed on the drawing cannot disagree with the ones beside it.
            ratios = centering.ratios_from_widths(
                merged["left_px"], merged["right_px"], merged["top_px"], merged["bottom_px"]
            )
            merged["lr_ratio"] = ratios["lr_ratio"]
            merged["tb_ratio"] = ratios["tb_ratio"]
            image = annotate.annotate_centering(rectified.image, merged)

        # Written back to the path the row already holds, in whatever format
        # that path names -- a submission analysed before derived images became
        # JPEG keeps its PNG, because the row still points at it.
        artifacts.save_to(image, Path(row.annotated_image_path))
        rewritten.append(row.annotated_image_path)
```

Update the docstring's first line to: `"""Redraw each side's centering overlay from detected widths, adjustment or placement.`

- [ ] **Step 5: Run the redraw and end-to-end tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_centering_annotation_redraw.py tests/test_centering_placement_end_to_end.py tests/test_corners_decline_end_to_end.py -v > <scratch>/pytest.log 2>&1; echo exit=$?`
Expected: all PASS, `exit=0`.

- [ ] **Step 6: Commit**

```bash
git add backend/zgrader/analysis/recompute.py backend/tests/test_centering_annotation_redraw.py backend/tests/test_centering_placement_end_to_end.py
git commit -m "Draw a placed centering in the report, and carry it through to the PDF" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: The share page payload and the link-preview fingerprint

**Files:**
- Test: `backend/tests/test_public_share.py` (refactor the allowlist literal into a constant; append), `backend/tests/test_og_image.py` (append)
- Modify: none expected. If a test fails, the fix goes in `schemas/public_report.py` or `analysis/og_image.py`, after answering "should a stranger see this?" for any new key.

**Interfaces:**
- Consumes: `tests.centering_rows` (Task 3); the POST endpoint (Task 4).
- Produces: `test_public_share._PUBLIC_KEYS` — the allowlist as a module constant.

- [ ] **Step 1: Lift the allowlist into a constant**

In `backend/tests/test_public_share.py`, move the literal set asserted in `test_public_payload_key_allowlist` (with its comments) into a module-level constant directly above that test:

```python
#: Every key the public payload may contain. See the test below for why it is a
#: literal, and what to ask before adding to it.
_PUBLIC_KEYS = {
    # ... the existing literal, unchanged ...
}
```

and make the test end `assert keys == _PUBLIC_KEYS`.

- [ ] **Step 2: Append the share-page test**

```python
def test_a_placed_centering_is_published_with_its_label(db_session):
    """A placement reaches the public page as a score with its placed-by-hand
    limitation beside it, marks the report adjusted, and adds no new key."""
    from zgrader.models import SubmissionStatus
    from tests.centering_rows import add_centering_rows, declined_side

    auth_token = register_and_verify(client, "placer@example.com")
    code = _create_submission(auth_token)
    with SessionLocal() as db:
        submission = db.query(Submission).filter(Submission.submission_code == code).one()
        submission.status = SubmissionStatus.draft_ready
        add_centering_rows(db, submission, declined_side())
        db.commit()

    placed = {"left_px": 30.0, "right_px": 30.0, "top_px": 25.0, "bottom_px": 35.0}
    resp = client.post(
        f"/submissions/{code}/centering-adjust", json={"side": "front", **placed}, headers=_auth(auth_token)
    )
    assert resp.status_code == 200, resp.text

    with SessionLocal() as db:
        submission = db.query(Submission).filter(Submission.submission_code == code).one()
        _publish(db, submission)
        submission.status = SubmissionStatus.published
        db.commit()
    share = client.post(f"/submissions/{code}/share", headers=_auth(auth_token))
    assert share.status_code == 200, share.text
    token = share.json()["url"].rsplit("/", 1)[-1]

    body = client.get(f"/public/reports/{token}").json()

    combined = next(r for r in body["results"] if r["category"] == "centering" and r["side"] == "combined")
    assert combined["raw_score"] is not None
    assert "centering_client_placed" in combined["measurements"]["assessment"]["limitations"]
    assert body["centering_adjustments"]["front"] == placed
    assert body["client_adjusted"] is True
    keys: set = set()
    _walk(body, keys, set())
    assert keys <= _PUBLIC_KEYS
```

- [ ] **Step 3: Append the fingerprint test**

Append to `backend/tests/test_og_image.py`:

```python
def test_a_placement_moves_the_fingerprint_and_clearing_it_moves_it_back(db_session):
    """Placement changes the combined score through recompute, not only the
    stored adjustment -- so the reverse direction has to be checked through
    recompute too."""
    from zgrader.analysis import recompute
    from tests.centering_rows import add_centering_rows, declined_side

    user = User(email="sub-70090@example.com", hashed_password="x", role=UserRole.client)
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code="SUB-70090",
        user_id=user.id,
        status=SubmissionStatus.draft_ready,
        language=SubmissionLanguage.en,
    )
    db_session.add(submission)
    db_session.flush()
    db_session.add(Card(submission_id=submission.id, game="Pokemon", card_name="Snorlax"))
    add_centering_rows(db_session, submission, declined_side())
    db_session.commit()
    db_session.refresh(submission)
    original = og_image.fingerprint(submission)

    submission.centering_adjustments = {
        "front": {"left_px": 30.0, "right_px": 30.0, "top_px": 25.0, "bottom_px": 35.0}
    }
    recompute.recompute_submission(db_session, submission)
    db_session.commit()
    assert og_image.fingerprint(submission) != original

    submission.centering_adjustments = None
    recompute.recompute_submission(db_session, submission)
    db_session.commit()
    db_session.refresh(submission)
    assert og_image.fingerprint(submission) == original
```

- [ ] **Step 4: Run both files**

Run: `.venv/Scripts/python.exe -m pytest tests/test_public_share.py tests/test_og_image.py -v > <scratch>/pytest.log 2>&1; echo exit=$?`
Expected: all PASS, `exit=0` — the spec expected no production change here. If `keys <= _PUBLIC_KEYS` fails, read which key is new and decide deliberately whether a stranger should see it before changing either file.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_public_share.py backend/tests/test_og_image.py
git commit -m "Pin a placed centering on the share page and in the link-preview key" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: Frontend foundations — types, DELETE call, strings, and the hook's place mode

**Files:**
- Modify: `frontend/lib/api.ts` (`PublicContact` ~line 268; after `adjustCentering` ~line 1042)
- Modify: `frontend/lib/branding-context.tsx` (`DEFAULT_BRANDING`)
- Modify: `frontend/lib/i18n/en.ts`, `frontend/lib/i18n/es.ts` (`submissionDetail`, `publicReport`, `centeringAdjust`)
- Replace: `frontend/lib/use-centering-adjust.ts`

**Interfaces:**
- Consumes: `GET /catalog/branding` fields and `DELETE /submissions/{code}/centering-adjust/{side}` (Task 4).
- Produces (used by Tasks 8–9):
  - `api.clearCentering(token: string, code: string, side: ScanSide): Promise<SubmissionDetail>`
  - `Branding.centering_placement_max_mm: number`, `Branding.centering_placement_default_mm: number`
  - `type CenteringMode = "nudge" | "place"`
  - `interface CenteringHandles { mode: CenteringMode; detected: CenteringWidths; measured: Record<keyof CenteringWidths, boolean>; pxPerMm: number }`
  - `centeringHandles(results: AnalysisResult[]): CenteringHandles | null`
  - `startingWidths(handles: CenteringHandles, defaultMm: number): CenteringWidths`
  - `ratiosFromWidths(widths)` — unchanged
  - `useCenteringAdjust({ token, code, side, handles, applied, raster, onAdjusted })` returning `{ mode, widths, setWidth, nudgeBy, reset, apply, applying, clear, clearing, moved, showControls, enabled, pxPerMm, boundsMm, ratios }` — `boundsMm(key): [number, number]`
  - i18n keys listed in Step 3.

- [ ] **Step 1: API types and the DELETE call**

In `frontend/lib/api.ts` `PublicContact`, directly after `centering_adjust_limit_mm: number;`:

```ts
  /** How far from the card's edge a hand-placed centering line may sit, in mm,
   *  when detection found no printed border. Enforced by the server too. */
  centering_placement_max_mm: number;
  /** Where a placed line starts on a side detection found nothing on, in mm. */
  centering_placement_default_mm: number;
```

After `adjustCentering`:

```ts
/** Remove one side's centering adjustment or placement and rescore. The only
 *  way to clear a placement: it has no detected lines to move back to. */
export async function clearCentering(
  token: string,
  code: string,
  side: ScanSide
): Promise<SubmissionDetail> {
  return request(`/submissions/${code}/centering-adjust/${side}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}
```

In `frontend/lib/branding-context.tsx` `DEFAULT_BRANDING`, after `centering_adjust_limit_mm: 4,`:

```ts
  // Match analysis/scoring.py; replaced by the real values on first load.
  centering_placement_max_mm: 8,
  centering_placement_default_mm: 3,
```

- [ ] **Step 2: Check it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors. (If any other object literal is typed as `Branding`/`PublicContact`, it now errors; add the two fields there with the same values.)

- [ ] **Step 3: Add every new string, in both languages**

`en.ts` → `submissionDetail`, after `adjustedChip: "Adjusted",`:

```ts
    // Beside a centering score whose lines the customer placed by hand.
    placedChip: "placed by you",
    placeLinesLink: "Place the lines yourself",
    adjustLinesLink: "Adjust your lines",
```

`es.ts` → `submissionDetail`, after `adjustedChip: "Ajustado",`:

```ts
    placedChip: "colocado por usted",
    placeLinesLink: "Coloque usted las líneas",
    adjustLinesLink: "Ajustar sus líneas",
```

`en.ts` → `publicReport` (add as the last key of that block):

```ts
    // The owner placed the centering lines; a stranger is reading this.
    placedChip: "placed by owner",
```

`es.ts` → `publicReport`, same place:

```ts
    placedChip: "colocado por el propietario",
```

`en.ts` → `centeringAdjust`, after `reset: "Back to detected",`:

```ts
    placeToggle: "Place centering lines",
    placeInstructions:
      "No printed border was found on this side, so place each line yourself: drag it onto the inner edge of the card's printed border. A magnifier appears while you drag, and you can tap a line to nudge it precisely. The score is worked out when you apply, and the report says the lines were placed by hand.",
    placeApply: "Apply and score",
    placeApplied: "Centering scored from the lines you placed.",
    placeReset: "Back to the starting lines",
    clear: "Clear my lines",
    cleared: "Your centering lines were cleared.",
    clearFailed: "Couldn't clear the lines.",
    nudge: {
      up: "Move up 0.1mm",
      down: "Move down 0.1mm",
      left: "Move left 0.1mm",
      right: "Move right 0.1mm",
    },
```

`es.ts` → `centeringAdjust`, after `reset: "Volver a lo detectado",`:

```ts
    placeToggle: "Colocar líneas de centrado",
    placeInstructions:
      "No se encontró un borde impreso en este lado, así que coloque usted cada línea: arrástrela hasta el filo interior del borde impreso de la carta. Aparece una lupa mientras arrastra, y puede tocar una línea para moverla con precisión. La puntuación se calcula al aplicar, y el informe indica que las líneas se colocaron a mano.",
    placeApply: "Aplicar y puntuar",
    placeApplied: "Centrado puntuado con las líneas que ha colocado.",
    placeReset: "Volver a las líneas iniciales",
    clear: "Borrar mis líneas",
    cleared: "Se borraron sus líneas de centrado.",
    clearFailed: "No se pudieron borrar las líneas.",
    nudge: {
      up: "Subir 0,1 mm",
      down: "Bajar 0,1 mm",
      left: "Mover a la izquierda 0,1 mm",
      right: "Mover a la derecha 0,1 mm",
    },
```

- [ ] **Step 4: Replace the hook**

Replace `frontend/lib/use-centering-adjust.ts` with:

```ts
"use client";

import { useState } from "react";
import { toastError, toastSuccess } from "@/lib/toast";
import { useBranding } from "@/lib/branding-context";
import { useTranslations } from "@/lib/i18n/context";
import * as api from "@/lib/api";

/** The four border widths, in pixels of the rectified card raster. */
type Widths = api.CenteringWidths;
type WidthKey = keyof Widths;

const KEYS = ["left_px", "right_px", "top_px", "bottom_px"] as const;
const SIDE_NAMES: Record<WidthKey, "left" | "right" | "top" | "bottom"> = {
  left_px: "left",
  right_px: "right",
  top_px: "top",
  bottom_px: "bottom",
};
const NO_WIDTHS: Widths = { left_px: 0, right_px: 0, top_px: 0, bottom_px: 0 };

/**
 * "nudge": detection found the border and the customer moves its lines, within
 * the operator's limit either side of where they were found.
 * "place": detection found no printed border, and the customer places the lines
 * by hand, anywhere within the placement bound of the card's edge. The result
 * is scored and labelled as placed by hand.
 */
export type CenteringMode = "nudge" | "place";

export interface CenteringHandles {
  mode: CenteringMode;
  /** nudge: where detection put each line. place: the pipeline's rough
   *  estimate for sides it read, 0 for sides it did not (see `measured`). */
  detected: Widths;
  /** Which entries of `detected` came from the image. All true when nudging. */
  measured: Record<WidthKey, boolean>;
  pxPerMm: number;
}

/**
 * Mirrors `centering.placement_eligible` on the backend, which is the authority
 * and refuses anything this lets through: declined for want of a printed frame,
 * on a card outline that was trusted. `geometry_unverified` is the one
 * disqualifying limitation (`assessment.DISQUALIFYING_LIMITATIONS`).
 */
function placementEligible(m: Record<string, unknown>): boolean {
  const block = m.assessment as api.Assessment | undefined;
  if (!block || block.state === "measured") return false;
  return (
    block.limitations.includes("centering_no_frame") &&
    !block.limitations.includes("geometry_unverified")
  );
}

/**
 * What the centering adjuster needs for a side, or null if it cannot be shown.
 *
 * A scored side is nudged from detection. A side that declined for want of a
 * printed frame is placed by hand. Anything else -- no centering result, or a
 * side whose card outline itself could not be found -- offers nothing, and the
 * endpoint would refuse it. Without `px_per_mm` neither mode can turn the
 * millimetre bounds the server enforces into pixels, so that declines too.
 */
export function centeringHandles(results: api.AnalysisResult[]): CenteringHandles | null {
  const result = results.find((r) => r.category === "centering");
  if (!result) return null;
  const m = (result.measurements ?? {}) as Record<string, unknown>;
  const pxPerMm = (m.card_geometry as { px_per_mm?: number } | undefined)?.px_per_mm;
  if (typeof pxPerMm !== "number" || pxPerMm <= 0) return null;
  const allMeasured = { left_px: true, right_px: true, top_px: true, bottom_px: true };

  if (result.raw_score !== null) {
    const widths = KEYS.map((k) => m[k]);
    if (!widths.every((v) => typeof v === "number")) return null;
    const [left_px, right_px, top_px, bottom_px] = widths as number[];
    return { mode: "nudge", detected: { left_px, right_px, top_px, bottom_px }, measured: allMeasured, pxPerMm };
  }

  if (!placementEligible(m)) return null;
  const estimate = (m.indicative_estimate ?? {}) as Record<string, unknown>;
  const perSide = (estimate.per_side ?? {}) as Record<string, { measured?: boolean } | undefined>;
  const detected = { ...NO_WIDTHS };
  const measured = { left_px: false, right_px: false, top_px: false, bottom_px: false };
  for (const key of KEYS) {
    const value = estimate[key];
    // A width of 0 is the pipeline's refusal, not a reading.
    if (typeof value === "number" && value > 0 && perSide[SIDE_NAMES[key]]?.measured === true) {
      detected[key] = value;
      measured[key] = true;
    }
  }
  return { mode: "place", detected, measured, pxPerMm };
}

/** Where the lines open: detection's for a nudge; for a placement, the rough
 *  estimate where a side was read and `defaultMm` from the edge where not. */
export function startingWidths(handles: CenteringHandles, defaultMm: number): Widths {
  if (handles.mode === "nudge") return handles.detected;
  const start = { ...NO_WIDTHS };
  for (const key of KEYS) {
    start[key] = handles.measured[key] ? handles.detected[key] : defaultMm * handles.pxPerMm;
  }
  return start;
}

/**
 * The two centering ratios and the worse side, from four border widths.
 *
 * Extracted so the drag overlay and the scorecard cannot disagree about what a
 * set of widths means -- the same reason `centering.ratios_from_widths` exists
 * on the backend. This is the arithmetic half only: pure, so it can be applied
 * to detected widths, adjusted ones, or a mix, wherever a ratio is displayed.
 *
 * The score is still never computed here. That lives in `analysis/scoring.py`,
 * and a second copy in TypeScript is the divergence that has already caught
 * `recompute.py` twice.
 */
export function ratiosFromWidths(widths: Widths): {
  lr: [number, number];
  tb: [number, number];
  worse: number;
} {
  const lr = widths.left_px + widths.right_px;
  const tb = widths.top_px + widths.bottom_px;
  const lrRatio: [number, number] =
    lr > 0 ? [(100 * widths.left_px) / lr, (100 * widths.right_px) / lr] : [50, 50];
  const tbRatio: [number, number] =
    tb > 0 ? [(100 * widths.top_px) / tb, (100 * widths.bottom_px) / tb] : [50, 50];
  return { lr: lrRatio, tb: tbRatio, worse: Math.max(...lrRatio, ...tbRatio) };
}

/**
 * Drag state for the four centering lines, and the calls that rescore.
 *
 * **The ratio updates live; the score does not.** The ratio is arithmetic on
 * the handle positions, so computing it here cannot drift from anything. The
 * score is a mapping that lives in `analysis/scoring.py`, and every consumer
 * must route through it, so the server computes it on apply, once.
 */
export function useCenteringAdjust({
  token,
  code,
  side,
  handles,
  applied,
  raster,
  onAdjusted,
}: {
  token: string;
  code: string;
  side: api.ScanSide;
  /** From `centeringHandles`; null when this side offers no adjustment. */
  handles: CenteringHandles | null;
  /** The adjustment or placement already applied, if any. The handles open
   *  there rather than silently reverting to where they started. */
  applied?: Widths | null;
  /** Natural pixel size of the displayed photo, once it has loaded. */
  raster: { w: number; h: number } | null;
  onAdjusted: (updated: api.SubmissionDetail) => void;
}) {
  const t = useTranslations();
  const {
    centering_adjust_limit_mm: limitMm,
    centering_placement_max_mm: placeMaxMm,
    centering_placement_default_mm: placeDefaultMm,
  } = useBranding();
  const mode: CenteringMode = handles?.mode ?? "nudge";
  const pxPerMm = handles?.pxPerMm ?? 0;
  const detected = handles?.detected ?? NO_WIDTHS;
  const start = handles ? startingWidths(handles, placeDefaultMm) : NO_WIDTHS;

  const [widths, setWidths] = useState<Widths>(applied ?? start);
  const [applying, setApplying] = useState(false);
  const [clearing, setClearing] = useState(false);

  const limitPx = Math.max(0, limitMm) * pxPerMm;
  const placeMaxPx = Math.max(0, placeMaxMm) * pxPerMm;
  // The operator's limit is the kill switch for both modes.
  const enabled = limitMm > 0 && pxPerMm > 0 && raster !== null;

  const { lr: lrRatio, tb: tbRatio, worse } = ratiosFromWidths(widths);

  const moved = KEYS.some((k) => Math.abs(widths[k] - start[k]) > 0.05);
  // Controls also show when something is already live on the server, so moving
  // back to the start leaves a way to commit or clear that.
  const showControls = moved || applied != null;

  /** Nudges are bounded against where *detection* put the line, not the last
   *  drag, so small moves cannot walk past the limit. A placement has no
   *  detected line, so it is bounded against the card's edge instead. */
  function boundsPx(key: WidthKey): [number, number] {
    const span = !raster ? Infinity : key === "left_px" || key === "right_px" ? raster.w : raster.h;
    if (mode === "place") return [0, Math.min(span / 2, placeMaxPx)];
    return [Math.max(0, detected[key] - limitPx), Math.min(span / 2, detected[key] + limitPx)];
  }

  function clamp(key: WidthKey, next: number): number {
    if (!raster) return next;
    const [lo, hi] = boundsPx(key);
    return Math.min(hi, Math.max(lo, next));
  }

  /** The same bounds in millimetres, for the handles' aria-valuemin/max. */
  function boundsMm(key: WidthKey): [number, number] {
    const [lo, hi] = boundsPx(key);
    const mm = (px: number) =>
      pxPerMm > 0 && Number.isFinite(px) ? Math.round((px / pxPerMm) * 10) / 10 : 0;
    return [mm(lo), mm(hi)];
  }

  /** Move one line, given a position already converted into raster pixels. */
  function setWidth(key: WidthKey, rasterPx: number) {
    setWidths((prev) => ({ ...prev, [key]: clamp(key, rasterPx) }));
  }

  /** Move one line by a signed number of millimetres of border width. */
  function nudgeBy(key: WidthKey, mm: number) {
    setWidths((prev) => ({ ...prev, [key]: clamp(key, prev[key] + mm * pxPerMm) }));
  }

  async function apply() {
    setApplying(true);
    try {
      const updated = await api.adjustCentering(token, code, side, {
        left_px: Math.round(widths.left_px * 10) / 10,
        right_px: Math.round(widths.right_px * 10) / 10,
        top_px: Math.round(widths.top_px * 10) / 10,
        bottom_px: Math.round(widths.bottom_px * 10) / 10,
      });
      onAdjusted(updated);
      toastSuccess(mode === "place" ? t.centeringAdjust.placeApplied : t.centeringAdjust.applied);
    } catch (err) {
      // The server enforces the same bounds independently, so a rejection is
      // worth showing rather than swallowing -- it means the two disagree.
      toastError(err instanceof api.ApiError ? err.message : t.centeringAdjust.applyFailed);
    } finally {
      setApplying(false);
    }
  }

  async function clear() {
    setClearing(true);
    try {
      const updated = await api.clearCentering(token, code, side);
      setWidths(start);
      onAdjusted(updated);
      toastSuccess(t.centeringAdjust.cleared);
    } catch (err) {
      toastError(err instanceof api.ApiError ? err.message : t.centeringAdjust.clearFailed);
    } finally {
      setClearing(false);
    }
  }

  return {
    mode,
    widths,
    setWidth,
    nudgeBy,
    reset: () => setWidths(start),
    apply,
    applying,
    clear,
    clearing,
    moved,
    showControls,
    enabled,
    pxPerMm,
    boundsMm,
    ratios: { lr: lrRatio, tb: tbRatio, worse },
  };
}
```

- [ ] **Step 5: Rewire the hook's one caller, minimally**

`components/AnnotatedPhoto.tsx` still passes `detected`/`pxPerMm`. Replace its `useCenteringAdjust({ ... })` call with:

```tsx
  const adjust = useCenteringAdjust({
    token,
    code,
    side,
    handles: centering,
    applied: centeringApplied,
    raster,
    onAdjusted: onAdjusted ?? (() => {}),
  });
```

and delete the now-unused `NO_WIDTHS` constant (and its comment) at the top of that file. Nothing else in the file changes in this task; Task 9 does the rest.

- [ ] **Step 6: Compile and build**

Run: `npx tsc --noEmit && npx next build`
Expected: both succeed. `SubmissionOverview`'s use of `centeringHandles(...).detected` still type-checks; its place-mode behaviour is fixed in Task 9.

- [ ] **Step 7: Commit**

```bash
git add frontend/lib/api.ts frontend/lib/branding-context.tsx frontend/lib/i18n/en.ts frontend/lib/i18n/es.ts frontend/lib/use-centering-adjust.ts frontend/components/AnnotatedPhoto.tsx
git commit -m "Give the centering hook a place mode, bounds from the catalog, and a clear call" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: CenteringLines — selection, keyboard, the loupe, and the placed style

**Files:**
- Replace: `frontend/components/CenteringLines.tsx`

**Interfaces:**
- Consumes: nothing new; the hook's `nudgeBy`, `pxPerMm` and `boundsMm` are passed in by Task 9.
- Produces (all new props optional, so today's two call sites keep compiling):
  - `export type LineKey = keyof CenteringWidths`, `export type Direction = "up" | "down" | "left" | "right"`
  - `export function arrowDeltaMm(key: LineKey, direction: Direction, stepMm: number): number`
  - `export function directionsFor(key: LineKey): [Direction, Direction]`
  - props: `variant?: "detected" | "placed"`, `photoUrl?: string | null`, `selected?: LineKey | null`, `onSelect?: (key: LineKey) => void`, `onNudge?: (key: LineKey, mm: number) => void`, `pxPerMm?: number`, `boundsMm?: (key: LineKey) => [number, number]`

- [ ] **Step 1: Replace the component**

Replace `frontend/components/CenteringLines.tsx` with:

```tsx
"use client";

import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import type { CenteringWidths } from "@/lib/api";

export type LineKey = keyof CenteringWidths;
export type Direction = "up" | "down" | "left" | "right";

const HANDLES: { key: LineKey; cursor: string }[] = [
  { key: "left_px", cursor: "ew-resize" },
  { key: "right_px", cursor: "ew-resize" },
  { key: "top_px", cursor: "ns-resize" },
  { key: "bottom_px", cursor: "ns-resize" },
];

const ARROW_KEYS: Record<string, Direction> = {
  ArrowUp: "up",
  ArrowDown: "down",
  ArrowLeft: "left",
  ArrowRight: "right",
};

/** Loupe diameter, and its gap from the pointer, in CSS pixels. Offset so a
 *  finger never covers the line it is placing. */
const LOUPE_PX = 96;
const LOUPE_GAP_PX = 28;
/** The base photo is at most 1600px on its long side
 *  (`artifacts.MAX_DERIVED_PX`), so past about twice its natural resolution a
 *  loupe only magnifies blur. */
const MAX_LOUPE_ZOOM = 4;

/**
 * Millimetres of border width to add for an arrow pressed on a line.
 *
 * Widths are measured from the card's edge inward, so moving the right line to
 * the right *shrinks* its width, and the bottom line down shrinks its width. An
 * arrow along the line's own length (up/down on a vertical line) does nothing.
 */
export function arrowDeltaMm(key: LineKey, direction: Direction, stepMm: number): number {
  switch (key) {
    case "left_px":
      return direction === "left" ? -stepMm : direction === "right" ? stepMm : 0;
    case "right_px":
      return direction === "right" ? -stepMm : direction === "left" ? stepMm : 0;
    case "top_px":
      return direction === "up" ? -stepMm : direction === "down" ? stepMm : 0;
    case "bottom_px":
      return direction === "down" ? -stepMm : direction === "up" ? stepMm : 0;
  }
}

/** The two arrows that move a line: across its own axis only. */
export function directionsFor(key: LineKey): [Direction, Direction] {
  return key === "left_px" || key === "right_px" ? ["left", "right"] : ["up", "down"];
}

/**
 * The four centering lines and their drag handles, drawn over the analysed
 * photo.
 *
 * Absolutely positioned to fill its parent, which is the same `relative`
 * container holding the photo and `RegionOverlay` -- so this element's bounding
 * rect *is* the displayed photo's, and pointer positions convert straight into
 * raster pixels against it.
 *
 * Rendered after `RegionOverlay` so the handles sit above its numbered badges;
 * a badge landing on a handle would otherwise swallow the drag.
 *
 * While a handle is dragged -- or a line is selected for nudging -- a loupe
 * shows the photo magnified around the line, beside the pointer rather than
 * under it. It reads the same photo as a CSS background, so it costs no second
 * fetch, and its zoom is capped by what that photo actually holds.
 */
export default function CenteringLines({
  widths,
  raster,
  enabled,
  handleLabels,
  onDrag,
  variant = "detected",
  photoUrl = null,
  selected = null,
  onSelect,
  onNudge,
  pxPerMm = 0,
  boundsMm,
}: {
  widths: CenteringWidths;
  raster: { w: number; h: number };
  /** False when adjustment is off -- lines still draw, so the customer can see
   *  where the border is, but nothing moves. */
  enabled: boolean;
  handleLabels: Record<LineKey, string>;
  onDrag: (key: LineKey, rasterPx: number) => void;
  /** "placed" draws lines the customer placed by hand: dashed pink, so a
   *  placement can never be mistaken for a measurement at a glance. */
  variant?: "detected" | "placed";
  /** The displayed photo, for the loupe. No loupe without it. */
  photoUrl?: string | null;
  selected?: LineKey | null;
  onSelect?: (key: LineKey) => void;
  /** Keyboard nudge, in millimetres of border width (see `arrowDeltaMm`). */
  onNudge?: (key: LineKey, mm: number) => void;
  pxPerMm?: number;
  boundsMm?: (key: LineKey) => [number, number];
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState<{ w: number; h: number } | null>(null);
  const [dragKey, setDragKey] = useState<LineKey | null>(null);
  const [pointer, setPointer] = useState<{ x: number; y: number } | null>(null);

  // The loupe needs the box's CSS size while rendering, and a ref read during
  // render is stale by definition -- so it is tracked in state.
  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) =>
      setBox({ w: entry.contentRect.width, h: entry.contentRect.height })
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Fractions of the raster, which is the space the overlay is positioned in.
  const fx = widths.left_px / raster.w;
  const fr = 1 - widths.right_px / raster.w;
  const fy = widths.top_px / raster.h;
  const fb = 1 - widths.bottom_px / raster.h;
  const lineFraction: Record<LineKey, number> = { left_px: fx, right_px: fr, top_px: fy, bottom_px: fb };

  const position: Record<LineKey, { left: string; top: string }> = {
    left_px: { left: `${fx * 100}%`, top: "50%" },
    right_px: { left: `${fr * 100}%`, top: "50%" },
    top_px: { left: "50%", top: `${fy * 100}%` },
    bottom_px: { left: "50%", top: `${fb * 100}%` },
  };

  const lines: { key: LineKey; x1: number; y1: number; x2: number; y2: number }[] = [
    { key: "left_px", x1: fx, y1: 0, x2: fx, y2: 1 },
    { key: "right_px", x1: fr, y1: 0, x2: fr, y2: 1 },
    { key: "top_px", x1: 0, y1: fy, x2: 1, y2: fy },
    { key: "bottom_px", x1: 0, y1: fb, x2: 1, y2: fb },
  ];

  /** The photo is scaled from the raster, so the pointer is converted back into
   *  raster pixels rather than CSS pixels -- otherwise the millimetre bounds
   *  would mean something different on every screen. */
  function toRasterPx(key: LineKey, clientX: number, clientY: number, rect: DOMRect): number {
    if (key === "left_px") return ((clientX - rect.left) / rect.width) * raster.w;
    if (key === "right_px") return ((rect.right - clientX) / rect.width) * raster.w;
    if (key === "top_px") return ((clientY - rect.top) / rect.height) * raster.h;
    return ((rect.bottom - clientY) / rect.height) * raster.h;
  }

  function handleMove(event: ReactPointerEvent<HTMLSpanElement>) {
    if (!dragKey || !boxRef.current) return;
    const rect = boxRef.current.getBoundingClientRect();
    setPointer({ x: event.clientX - rect.left, y: event.clientY - rect.top });
    onDrag(dragKey, toRasterPx(dragKey, event.clientX, event.clientY, rect));
  }

  function endDrag(event: ReactPointerEvent<HTMLSpanElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setDragKey(null);
    setPointer(null);
  }

  function handleKeyDown(key: LineKey, event: ReactKeyboardEvent<HTMLSpanElement>) {
    const direction = ARROW_KEYS[event.key];
    if (!direction || !onNudge) return;
    const mm = arrowDeltaMm(key, direction, event.shiftKey ? 1 : 0.1);
    if (mm === 0) return;
    // Arrows would otherwise scroll the page as well as move the line.
    event.preventDefault();
    onNudge(key, mm);
  }

  // Where the loupe looks and where it sits, in the box's CSS pixels.
  const loupeKey = dragKey ?? selected;
  const loupe = (() => {
    if (!enabled || !loupeKey || !photoUrl || !box) return null;
    const vertical = loupeKey === "left_px" || loupeKey === "right_px";
    // Along the line: under the pointer while dragging, the handle otherwise.
    const along = dragKey && pointer ? (vertical ? pointer.y : pointer.x) : vertical ? box.h / 2 : box.w / 2;
    const cx = vertical ? lineFraction[loupeKey] * box.w : along;
    const cy = vertical ? along : lineFraction[loupeKey] * box.h;
    const zoom = Math.min(MAX_LOUPE_ZOOM, Math.max(1, (2 * raster.w) / box.w));
    const above = cy - LOUPE_GAP_PX - LOUPE_PX;
    // Flip below the line near the top of the photo; keep at least half of it
    // over the photo horizontally.
    const top = above >= 0 ? above : cy + LOUPE_GAP_PX;
    const left = Math.min(Math.max(cx - LOUPE_PX / 2, -LOUPE_PX / 2), box.w - LOUPE_PX / 2);
    return { vertical, cx, cy, zoom, top, left };
  })();

  return (
    <div ref={boxRef} className="absolute inset-0 touch-none select-none">
      <svg
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
        className="pointer-events-none absolute inset-0 h-full w-full"
      >
        {lines.map((l) =>
          variant === "placed" ? (
            <line
              key={l.key}
              x1={l.x1}
              y1={l.y1}
              x2={l.x2}
              y2={l.y2}
              stroke="var(--neon-pink)"
              strokeWidth={2}
              strokeDasharray="6 4"
              vectorEffect="non-scaling-stroke"
            />
          ) : (
            <line
              key={l.key}
              x1={l.x1}
              y1={l.y1}
              x2={l.x2}
              y2={l.y2}
              stroke={selected === l.key ? "var(--neon-pink)" : "var(--grade-gem)"}
              strokeWidth={0.004}
            />
          )
        )}
      </svg>

      {enabled &&
        HANDLES.map((h) => {
          const mm = pxPerMm > 0 ? Math.round((widths[h.key] / pxPerMm) * 10) / 10 : null;
          const [minMm, maxMm] = boundsMm ? boundsMm(h.key) : [undefined, undefined];
          const isSelected = selected === h.key;
          return (
            <span
              key={h.key}
              role="slider"
              aria-label={handleLabels[h.key]}
              aria-orientation={h.key === "left_px" || h.key === "right_px" ? "horizontal" : "vertical"}
              aria-valuenow={mm ?? Math.round(widths[h.key])}
              aria-valuemin={minMm}
              aria-valuemax={maxMm}
              aria-valuetext={mm !== null ? `${mm} mm` : undefined}
              tabIndex={0}
              onFocus={() => onSelect?.(h.key)}
              onKeyDown={(e) => handleKeyDown(h.key, e)}
              onPointerDown={(e) => {
                e.currentTarget.setPointerCapture(e.pointerId);
                setDragKey(h.key);
                onSelect?.(h.key);
                const rect = boxRef.current?.getBoundingClientRect();
                if (rect) setPointer({ x: e.clientX - rect.left, y: e.clientY - rect.top });
              }}
              onPointerMove={handleMove}
              onPointerUp={endDrag}
              onPointerCancel={endDrag}
              // 44px of transparent hit area around a 20px dot: the dot marks
              // where the line sits, so it stays small, and the target does not.
              className="absolute flex h-11 w-11 -translate-x-1/2 -translate-y-1/2 touch-none items-center justify-center"
              style={{ left: position[h.key].left, top: position[h.key].top, cursor: h.cursor }}
            >
              <span
                aria-hidden="true"
                className="h-5 w-5 rounded-full border-2 border-white shadow-md"
                style={{ backgroundColor: isSelected ? "var(--neon-pink)" : "var(--grade-gem)" }}
              />
            </span>
          );
        })}

      {loupe && box && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute overflow-hidden rounded-full shadow-lg"
          style={{
            width: LOUPE_PX,
            height: LOUPE_PX,
            left: loupe.left,
            top: loupe.top,
            // An outline rather than a border, so the background's origin is the
            // circle's own edge and the maths below needs no inset.
            outline: "3px solid white",
            backgroundImage: `url(${photoUrl})`,
            backgroundRepeat: "no-repeat",
            backgroundSize: `${box.w * loupe.zoom}px ${box.h * loupe.zoom}px`,
            backgroundPosition: `${LOUPE_PX / 2 - loupe.cx * loupe.zoom}px ${LOUPE_PX / 2 - loupe.cy * loupe.zoom}px`,
          }}
        >
          <span
            className="absolute"
            style={
              loupe.vertical
                ? { left: LOUPE_PX / 2 - 1, top: 0, bottom: 0, width: 2, backgroundColor: "var(--neon-pink)" }
                : { top: LOUPE_PX / 2 - 1, left: 0, right: 0, height: 2, backgroundColor: "var(--neon-pink)" }
            }
          />
          <span
            className="absolute h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white"
            style={{ left: LOUPE_PX / 2, top: LOUPE_PX / 2 }}
          />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Compile, lint and build**

Run: `cd frontend && npx tsc --noEmit && npx eslint components/CenteringLines.tsx && npx next build`
Expected: all succeed. The existing call sites in `AnnotatedPhoto.tsx` pass only the original five props, which are unchanged.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/CenteringLines.tsx
git commit -m "Add a loupe, line selection, keyboard nudges and a placed style to the centering lines" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: Wire it into the results page and the share page

**Files:**
- Modify: `frontend/components/AnnotatedPhoto.tsx`, `frontend/components/SubmissionOverview.tsx`, `frontend/components/PublicReport.tsx`

**Interfaces:**
- Consumes: `centeringHandles`, `useCenteringAdjust` (Task 7); `CenteringLines`, `arrowDeltaMm`, `directionsFor`, `LineKey` (Task 8); i18n keys (Task 7).
- Produces: the anchor `#place-centering-{side}` on each side's photo, which opens its adjuster.

Every edit below names the existing text it replaces. Where an anchor does not match exactly, stop and re-read the file; do not improvise a different location.

- [ ] **Step 1: AnnotatedPhoto — imports, state, and the link target**

Replace `import CenteringLines from "@/components/CenteringLines";` with:

```tsx
import CenteringLines, { arrowDeltaMm, directionsFor, type LineKey } from "@/components/CenteringLines";
```

Below the `COLLAPSE_STORAGE_PREFIX` constant add:

```tsx
const ARROW_GLYPHS = { up: "▲", down: "▼", left: "◀", right: "▶" } as const;
```

Directly after `const [raster, setRaster] = useState<{ w: number; h: number } | null>(null);` add:

```tsx
  // The line picked for fine nudges, by tap, click or keyboard focus.
  const [selected, setSelected] = useState<LineKey | null>(null);
```

Directly after `const canAdjust = centering !== null && onAdjusted !== undefined;` add:

```tsx
  const placing = centering?.mode === "place";

  // The scorecard's "Place the lines yourself" link points here, and opening
  // the adjuster on arrival saves hunting for the toggle.
  useEffect(() => {
    if (!canAdjust) return;
    const openFromHash = () => {
      if (window.location.hash === `#place-centering-${side}`) setAdjusting(true);
    };
    openFromHash();
    window.addEventListener("hashchange", openFromHash);
    return () => window.removeEventListener("hashchange", openFromHash);
  }, [canAdjust, side]);
```

On the component's root element, `<div ref={wrapperRef} className="relative grid grid-cols-1 items-start gap-4 lg:grid-cols-[1fr_320px]">`, add `id={`place-centering-${side}`}`.

- [ ] **Step 2: AnnotatedPhoto — what is drawn read-only**

Replace:

```tsx
  const appliedWidths =
    centering && centeringApplied ? { ...centering.detected, ...centeringApplied } : centering?.detected ?? null;
```

with:

```tsx
  // A placeable side with nothing applied draws nothing read-only: its
  // starting lines are a guess, not a border anyone found or placed.
  const appliedWidths =
    centering && centeringApplied
      ? { ...centering.detected, ...centeringApplied }
      : centering?.mode === "nudge"
        ? centering.detected
        : null;
```

In the read-only `CenteringLines` block (the one rendered when `!adjusting`), change its condition from `{photoUrl && !adjusting && showMarkers && canAdjust && raster && !hasCenteringRegion && (` to:

```tsx
        {photoUrl && !adjusting && showMarkers && canAdjust && raster && !hasCenteringRegion && appliedWidths && (
```

change `widths={appliedWidths ?? adjust.widths}` to `widths={appliedWidths}`, and add directly after its `raster={raster}` line:

```tsx
            variant={placing ? "placed" : "detected"}
```

- [ ] **Step 3: AnnotatedPhoto — the toggle and the live lines**

Replace the toggle button:

```tsx
              <Button variant="outline" size="sm" onPress={() => setAdjusting((a) => !a)}>
                {adjusting ? t.centeringAdjust.toggleDone : t.centeringAdjust.toggle}
              </Button>
```

with:

```tsx
              <Button
                variant="outline"
                size="sm"
                onPress={() => {
                  setAdjusting((a) => !a);
                  setSelected(null);
                }}
              >
                {adjusting
                  ? t.centeringAdjust.toggleDone
                  : placing
                    ? t.centeringAdjust.placeToggle
                    : t.centeringAdjust.toggle}
              </Button>
```

Replace the live (adjusting) block:

```tsx
        {photoUrl && adjusting && canAdjust && raster && (
          <CenteringLines
            widths={adjust.widths}
            raster={raster}
            enabled={adjust.enabled}
            handleLabels={t.centeringAdjust.handleLabel}
            onDrag={adjust.setWidth}
          />
        )}
```

with:

```tsx
        {photoUrl && adjusting && canAdjust && raster && (
          <CenteringLines
            widths={adjust.widths}
            raster={raster}
            enabled={adjust.enabled}
            handleLabels={t.centeringAdjust.handleLabel}
            onDrag={adjust.setWidth}
            photoUrl={photoUrl}
            selected={selected}
            onSelect={setSelected}
            onNudge={adjust.nudgeBy}
            pxPerMm={adjust.pxPerMm}
            boundsMm={adjust.boundsMm}
          />
        )}
```

- [ ] **Step 4: AnnotatedPhoto — the panel under the photo**

Replace `{adjust.enabled ? t.centeringAdjust.instructions : t.centeringAdjust.disabled}` with:

```tsx
              {!adjust.enabled
                ? t.centeringAdjust.disabled
                : placing
                  ? t.centeringAdjust.placeInstructions
                  : t.centeringAdjust.instructions}
```

Directly after the closing `</dl>` of the ratios list, add the nudge bar:

```tsx
            {adjust.enabled && selected && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-muted">{t.centeringAdjust.handleLabel[selected]}</span>
                {directionsFor(selected).map((direction) => (
                  <Button
                    key={direction}
                    variant="outline"
                    size="sm"
                    aria-label={t.centeringAdjust.nudge[direction]}
                    onPress={() => adjust.nudgeBy(selected, arrowDeltaMm(selected, direction, 0.1))}
                  >
                    {ARROW_GLYPHS[direction]}
                  </Button>
                ))}
              </div>
            )}
```

In the controls, replace `{adjust.applying ? t.centeringAdjust.applying : t.centeringAdjust.apply}` with:

```tsx
                  {adjust.applying
                    ? t.centeringAdjust.applying
                    : placing
                      ? t.centeringAdjust.placeApply
                      : t.centeringAdjust.apply}
```

Replace `{t.centeringAdjust.reset}` (inside the Reset button) with `{placing ? t.centeringAdjust.placeReset : t.centeringAdjust.reset}`, and directly after that Reset button's closing `</Button>` add:

```tsx
                {placing && centeringApplied && (
                  <Button
                    variant="outline"
                    size="sm"
                    isDisabled={adjust.clearing || adjust.applying}
                    onPress={adjust.clear}
                  >
                    {t.centeringAdjust.clear}
                  </Button>
                )}
```

- [ ] **Step 5: SubmissionOverview — the chip, the link, and the split**

Directly after the `resultsBySide` declaration add:

```tsx
  // The side a "Place the lines yourself" link opens: the first whose
  // centering declined for want of a printed border and can be placed.
  const placeableSide = SIDES.find(
    (side) => centeringHandles(resultsBySide.get(side) ?? [])?.mode === "place"
  );
```

Directly after `const limitationCodes: string[] = assessmentBlock?.limitations ?? [];` add:

```tsx
                const placedByHand = limitationCodes.includes("centering_client_placed");
```

After the chip block that renders `{t.submissionDetail.adjustedChip}` (the `<Chip>` inside `{adjusted && (`, not the struck-through span), add:

```tsx
                      {placedByHand && (
                        <Chip color="danger" variant="soft" size="sm">
                          {t.submissionDetail.placedChip}
                        </Chip>
                      )}
```

Directly before the comment `{/* The measurement behind the number, and the form a` add:

```tsx
                    {category === "centering" && onAdjusted && placeableSide && (
                      <a
                        href={`#place-centering-${placeableSide}`}
                        className="mt-1 inline-flex min-h-6 items-center text-xs font-medium"
                        style={{ color: "var(--neon-pink)" }}
                      >
                        {placedByHand ? t.submissionDetail.adjustLinesLink : t.submissionDetail.placeLinesLink}
                      </a>
                    )}
```

In the per-side split, replace:

```tsx
                          const detected = centeringHandles(resultsBySide.get(side) ?? []);
                          if (!detected) return null;
                          const widths = {
                            ...detected.detected,
                            ...(submission.centering_adjustments?.[side] ?? {}),
                          };
```

with:

```tsx
                          const handles = centeringHandles(resultsBySide.get(side) ?? []);
                          if (!handles) return null;
                          const adjustment = submission.centering_adjustments?.[side];
                          // A placeable side with nothing placed has no border to
                          // split -- its starting lines are a guess.
                          if (handles.mode === "place" && !adjustment) return null;
                          const widths = { ...handles.detected, ...(adjustment ?? {}) };
```

- [ ] **Step 6: PublicReport — the chip**

In the scorecard tile, directly after:

```tsx
                      {result.flags.lower_confidence && (
                        <Chip color="warning" variant="soft" size="sm">
                          {t.submissionDetail.lowerConfidence}
                        </Chip>
                      )}
```

add:

```tsx
                      {limitationCodes.includes("centering_client_placed") && (
                        <Chip color="danger" variant="soft" size="sm">
                          {t.publicReport.placedChip}
                        </Chip>
                      )}
```

Nothing else on this page changes. Its per-side split already lays `centering_adjustments` over the widths, which carries a placement's four widths, and a declined side has no region, so no frame is drawn for it — the same as an unflagged nudge today.

- [ ] **Step 7: Compile, lint and build**

Run: `cd frontend && npx tsc --noEmit && npx eslint components/AnnotatedPhoto.tsx components/SubmissionOverview.tsx components/PublicReport.tsx && npx next build`
Expected: all succeed.

- [ ] **Step 8: Commit**

```bash
git add frontend/components/AnnotatedPhoto.tsx frontend/components/SubmissionOverview.tsx frontend/components/PublicReport.tsx
git commit -m "Offer centering placement on the results page and label it everywhere" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 10: Verify it in the browser, then the docs and the full suites

**Files:**
- Modify: `AGENTS.md`, `frontend/lib/i18n/en.ts` and `es.ts` (`methodology.adjustBody`)
- Modify: `.claude/launch.json` (the `backend-preview` path), and a scratch copy of the preview script
- No test files.

- [ ] **Step 1: The full backend suite, the drift check and the frontend build, first**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q > <scratch>/pytest-full.log 2>&1; echo exit=$?`
Expected: `exit=0`. Read the log's summary line. Any failure is investigated, not re-run until green.

Run: `.venv/Scripts/python.exe scripts/fixture_drift.py > <scratch>/drift.log 2>&1; echo exit=$?`
Expected: no synthetic drift (nothing measured changed). No methodology-figure regeneration is needed, since no analysis threshold moved.

Run: `cd ../frontend && npx tsc --noEmit && npx next build`
Expected: success.

Finish these before starting the preview: the preview writes to `zgrader_test`, and pytest deletes rows out from under anything else using it.

- [ ] **Step 2: A backend preview that can only reach the test database**

`.claude/launch.json`'s `backend-preview` points at a script in an old session's scratchpad. Copy it into this session's scratchpad (`cp "<old path>" "<scratch>/backend-preview.sh"`), read it — it must refuse any database whose name does not end in `_test` and set scratch scans/reports directories — and point `runtimeArgs` at the copy. Check `frontend/next.config.*` for where `/api` is proxied in development, and confirm it is `localhost:8000`.

- [ ] **Step 3: Seed one declined-centering submission and a login for it**

With the same environment the preview script builds (test database URL, the scratch scans/reports directories), run from `backend/`:

```bash
PYTHONPATH=. .venv/Scripts/python.exe - <<'PY'
import cv2, tempfile, os
from zgrader.db import SessionLocal
from zgrader.auth.security import hash_password
from zgrader.models import User
from zgrader.dev_trigger import run_dev_trigger
from tests.fixtures.generate_samples import build_fixture

email = "placement-preview@example.com"
with SessionLocal() as db:
    if db.query(User).filter(User.email == email).first() is None:
        db.add(User(email=email, hashed_password=hash_password("preview-pass-123"), is_verified=True))
        db.commit()
front = os.path.join(tempfile.mkdtemp(), "full_art.png")
cv2.imwrite(front, build_fixture("full_art_centered"))
print(run_dev_trigger(front_path=front, back_path=None, game="Pokemon", card_name="Placement preview", user_email=email))
PY
```

Before running it, print the database **name** only (never the URL) the environment resolves to, and stop unless it ends in `_test`.

- [ ] **Step 4: Walk it in the browser pane**

Start `backend-preview` and `frontend` with `preview_start`, sign in as `placement-preview@example.com`, open the seeded submission, and check each of these, taking a screenshot of the ones marked 📷:

1. Centering reads "Not measurable" with a **Place the lines yourself** link; the photo toolbar shows **Place centering lines**. 📷
2. The link scrolls to the photo and opens the adjuster.
3. Dragging a handle shows the loupe beside the pointer with the line through its centre; it flips below near the top edge. 📷
4. Tapping a line turns it pink and shows the ▲▼ / ◀▶ bar; each tap moves the split by a small step. Arrow keys on a focused handle do the same, Shift+arrow ten times as far, and `aria-valuenow` changes (check with `read_page`).
5. A line cannot be dragged past 8mm from the edge.
6. **Apply and score** gives a score, the **placed by you** chip, the placed-by-hand note, and dashed pink lines once the adjuster closes. 📷
7. **Clear my lines** returns to "Not measurable", with no lines drawn.
8. At 375px wide (`resize_window` preset `mobile`): the loupe stays on screen and the handles remain usable. 📷 Reset to `desktop` afterwards.
9. Switch to ES: every new string is Spanish.
10. `read_console_messages` shows no errors.

Stop both servers when done.

- [ ] **Step 5: Update the methodology copy**

In `frontend/lib/i18n/en.ts`, in `methodology.adjustBody`, replace the sentence beginning "Movement is capped a few millimetres either side of where the border was detected" (through "clears the adjustment completely.") with:

```text
Where the border was found, movement is capped a few millimetres either side of it, so a line can be fixed but not invented, and putting every line back where it started clears the adjustment completely. Where no printed border could be found at all, you can place the lines yourself instead: that figure is scored, but it is labelled everywhere as placed by hand rather than measured, and it carries less confidence than anything the software read for itself.
```

In `es.ts`, `methodology.adjustBody`, replace the corresponding sentence (the one about the few-millimetre cap and clearing the adjustment) with:

```text
Donde se encontró el borde, el movimiento se limita a unos milímetros a cada lado, de modo que una línea puede corregirse pero no inventarse, y devolver todas las líneas a donde empezaron borra el ajuste por completo. Donde no se pudo encontrar ningún borde impreso, puede colocar usted las líneas: esa cifra se puntúa, pero se indica en todas partes como colocada a mano y no medida, y lleva menos confianza que cualquier cosa que el programa haya leído por sí mismo.
```

- [ ] **Step 6: Update AGENTS.md**

At the end of the invariant that begins "**A client adjustment changes the numbers; anything drawn from those numbers has to be redrawn.**", after its paragraph ending "ask whether it remaps.", add:

```markdown
**A declined centering can now become a score, by hand.** Where centering declined with
`centering_no_frame` on a trusted card outline (`centering.placement_eligible`), the customer can
place the four lines themselves. It is stored in `centering_adjustments` like a nudge, and the
per-side row keeps saying what was measured; `recompute.placed_side` scores it through the usual
functions under `centering_client_placed` at confidence 0.4, and rebuilds the combined assessment,
keeping the pipeline's own as `original_assessment` so clearing restores it exactly. A
`geometry_unverified` side can never be placed, because its raster may be a desk. This is the first
path that *un-declines* a category, and it reached the same surfaces declining did: recompute, the
redraw, the PDF, the share page. Adjusting of either kind is allowed only in `draft_ready`, because the
share page renders from the database and would otherwise change after publication with nobody
reviewing it.

Planning it also found that recompute never applied "the score follows the assessment": a
front-declined card with a scored back took the back's number on any recompute. Fixed in the same
change; `test_recompute_never_resurrects_a_score_the_front_declined` pins it.
```

- [ ] **Step 7: Commit**

```bash
git add AGENTS.md frontend/lib/i18n/en.ts frontend/lib/i18n/es.ts .claude/launch.json
git commit -m "Describe centering placement on the methodology page and in AGENTS.md" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 8: Report**

Say what ran and what did not: the full-suite and drift results with their exit codes, the browser checks with the screenshots, and anything that failed or was skipped. Then use superpowers:finishing-a-development-branch.
