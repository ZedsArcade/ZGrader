# Crop-Guided Edge Fit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the customer's crop disagrees with the fitted card edge, search for that edge near the crop line instead of discarding the correction — and decline honestly when no edge is found there.

**Architecture:** `preprocessing.rectify` keeps fitting the card the way it does today. Afterwards, when a crop was supplied, each fitted side is compared with the customer's crop line; a side that disagrees by more than `CROP_REFIT_TRIGGER_MM` is re-searched within `CROP_REFIT_BAND_MM` of that line for the outermost strong brightness step, re-fitted with the existing RANSAC + sub-pixel machinery, and the apexes re-intersected. A side whose re-search finds nothing falls back to the crop line and carries `GEOMETRY_UNVERIFIED` plus a new `GEOMETRY_CROP_DISAGREEMENT`, so every boundary-dependent category declines through the path that already exists.

**Tech Stack:** OpenCV + NumPy analysis pipeline (`backend/zgrader/analysis/`), FastAPI, pytest; Next.js frontend only for the two limitation strings.

**Spec:** `docs/superpowers/specs/2026-09-16-crop-guided-edge-fit-design.md`

## Global Constraints

- Branch: `crop-guided-edge-fit`, cut from `centering-placement-and-crop-fit-design` (which carries this spec; PR #72 is open from it).
- `<scratch>` means `C:/Users/Cedric/AppData/Local/Temp/claude/C--Claude-Projects-ZGrader/f58df2f3-f7d2-4d53-9415-ff5e033ce73d/scratchpad`. Never write logs into the repo.
- Backend tests: from `backend/`, `.venv/Scripts/python.exe -m pytest <args> > <scratch>/<name>.log 2>&1; echo exit=$?`, then read the log. **Never pipe pytest through `tail`/`head`.** The full suite takes ~35 minutes (baseline on this branch: 819 passed, 11 pre-existing warnings); run named files during tasks and the full suite only where a task says so.
- Tests use only the database named by `ZGRADER_TEST_DATABASE_URL` (ends in `_test`). `127.0.0.1:5432` is an ssh tunnel to **production** Postgres; never set `ZGRADER_DATABASE_URL`. One pytest process at a time.
- **Every change under `analysis/` must be checked for per-fixture drift** (`scripts/fixture_drift.py`, `tests/test_fixture_drift.py`). The only intended baseline change in this plan is the new fixture added in Task 2. Any other moved number is a finding, not a rebaseline.
- Real photographs live in `backend/tests/fixtures/real_scans/` and are **never committed** (the repo is public). `shadowed_photo.jpg`, `shadowed_photo_traced.png` and `shadowed_photo.crop.json` are already there locally.
- New constants start at `CROP_REFIT_TRIGGER_MM = 2.0` and `CROP_REFIT_BAND_MM = 3.0`, tagged ARBITRARY, and are **set from the Task 6 measurements before merge**.
- New limitation code `geometry_crop_disagreement`, with EN/ES copy in `reports/strings.py` and `frontend/lib/i18n/{en,es}.ts`.
- Frontend checks (Task 5 only): `cd frontend && npx tsc --noEmit && npx next build`.
- Commit messages end with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. `git add` only the files a task lists; never commit `.superpowers/`, `real_scans/`, or `.claude/`.

## Files

| File | Responsibility | Tasks |
|---|---|---|
| `backend/scripts/fixture_drift.py` | traced-crop path, `--sloppy`, skipping `*_traced.*` | 1 |
| `backend/tests/fixtures/real_scans/README.md` | how to trace a crop and save the sidecar | 1 |
| `backend/tests/fixtures/generate_samples.py` | `capture_shadowed_bottom` fixture | 2 |
| `backend/tests/fixtures/drift_baseline.json` | the new fixture's entry | 2 |
| `backend/zgrader/analysis/geometry.py` | `refit_geometry_near_crop`, its constants | 3 |
| `backend/zgrader/analysis/preprocessing.py` | wiring in `rectify`, the fallback | 4 |
| `backend/zgrader/analysis/assessment.py` | `GEOMETRY_CROP_DISAGREEMENT` | 4 |
| `backend/zgrader/reports/strings.py`, `frontend/lib/i18n/{en,es}.ts` | limitation copy | 5 |
| `backend/tests/test_geometry.py`, `test_crop_refit.py`, `test_api_check_crop.py` | tests | 3–5 |
| `AGENTS.md`, `/methodology` figures | docs | 6 |

---

### Task 1: The harness measures a traced crop, and a sloppy one

**Files:**
- Modify: `backend/scripts/fixture_drift.py`
- Modify: `backend/tests/fixtures/real_scans/README.md`

**Interfaces:**
- Produces:
  - `fixture_drift.traced_crop(path: Path) -> np.ndarray | None` — the four points from `<stem>.crop.json`, or None.
  - `fixture_drift.sloppy_crop(quad: np.ndarray, px_per_mm: float, seed: int) -> np.ndarray` — each side pushed in or out by a seeded 1–2mm.
  - `measure_real_scans(sloppy: bool = False)` gains a `"traced"` entry per photo that has a sidecar, and a `"sloppy"` entry when `--sloppy` is passed.
  - `python scripts/fixture_drift.py --sloppy` prints how many photos carry each new label and the largest px/mm shift against the unperturbed cropped run. (Apex displacement needs the geometry rather than the score metrics; Task 6 measures that directly.)

This task changes no production code, so the drift baseline must not move.

- [ ] **Step 1: Skip traced overlays and read the sidecar**

In `backend/scripts/fixture_drift.py`, below `_DEFAULT_CARD_MM`, add:

```python
#: A "<name>_traced.png" is a copy of its photo with a crop drawn on it by hand
#: -- an input to `traced_crop`, not another photograph to measure.
_TRACED_SUFFIX = "_traced"
```

Add, after `crop_like_a_customer`:

```python
def traced_crop(path: Path) -> np.ndarray | None:
    """The crop a person traced around this card, from `<stem>.crop.json`.

    The harness's own `crop_like_a_customer` is the *fit's* own apexes, so it
    can never contain a crop that corrects the fit -- which is the only case
    the crop-guided refit exists for. A traced crop is the missing input, and
    it stays out of git with the photographs it belongs to.
    """
    sidecar = path.with_suffix(".crop.json")
    if not sidecar.is_file():
        return None
    points = json.loads(sidecar.read_text(encoding="utf-8"))["points"]
    return np.array(points, dtype=np.float64).reshape(4, 2)


def sloppy_crop(quad: np.ndarray, px_per_mm: float, seed: int) -> np.ndarray:
    """`quad` with each side pushed in or out by 1-2mm, deterministically.

    A crop traced by finger on a phone is never on the edge to the millimetre,
    and the refit must not pull a good fit off its edge when the crop is merely
    imprecise. Seeded per photograph so a rerun reports the same number.
    """
    ordered = np.asarray(quad, dtype=np.float64).reshape(4, 2)
    rng = np.random.default_rng(seed)
    centre = ordered.mean(axis=0)
    moved = ordered.copy()
    # Corner i belongs to two sides; each side's offset moves both of its ends
    # along the outward direction from the quad's centre, which keeps the shape
    # a quadrilateral rather than shearing it.
    for i in range(4):
        outward = ordered[i] - centre
        norm = float(np.linalg.norm(outward))
        if norm < 1e-6:
            continue
        magnitude = rng.uniform(1.0, 2.0) * px_per_mm * rng.choice([-1.0, 1.0])
        moved[i] = ordered[i] + (outward / norm) * magnitude
    return moved
```

Add `from pathlib import Path` — already imported — and confirm `json` and `numpy` are imported at the top (they are).

- [ ] **Step 2: Measure the traced and sloppy paths**

Replace the body of `measure_real_scans` with:

```python
def measure_real_scans(sloppy: bool = False) -> dict[str, dict[str, dict[str, float]]]:
    """Measure any real photographs that have been dropped in: without a crop,
    with the harness's own crop, with a hand-traced crop where one exists, and
    -- under --sloppy -- with that crop deliberately misplaced by 1-2mm.

    Returns empty when the directory is absent or empty, which is the normal
    state for a fresh clone -- this must never be the reason the harness fails.
    """
    if not REAL_SCANS_DIR.is_dir():
        return {}
    results = {}
    for path in sorted(REAL_SCANS_DIR.iterdir()):
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
            continue
        if path.stem.endswith(_TRACED_SUFFIX):
            continue
        image = cv2.imread(str(path))
        if image is None:
            print(f"  ! could not read {path.name}", file=sys.stderr)
            continue
        try:
            crop = crop_like_a_customer(image)
            measurements = {
                "uncropped": measure_image(image, *_DEFAULT_CARD_MM),
                "cropped": measure_image(image, *_DEFAULT_CARD_MM, roi_quad=crop),
            }
            traced = traced_crop(path)
            if traced is not None:
                measurements["traced"] = measure_image(
                    image, *_DEFAULT_CARD_MM, roi_quad=traced
                )
            if sloppy:
                px_per_mm = measurements["cropped"].get("px_per_mm") or 1.0
                measurements["sloppy"] = measure_image(
                    image,
                    *_DEFAULT_CARD_MM,
                    roi_quad=sloppy_crop(crop, px_per_mm, seed=abs(hash(path.stem)) % (2**32)),
                )
            results[path.stem] = measurements
        except Exception as exc:  # noqa: BLE001 -- one bad photo must not stop the run
            print(f"  ! {path.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
    return results
```

- [ ] **Step 3: Print the new rows**

In `main`, replace `real = measure_real_scans()` with `real = measure_real_scans(sloppy=args.sloppy)`, and add the flag beside the others:

```python
    parser.add_argument(
        "--sloppy",
        action="store_true",
        help="also measure each real photo with its crop misplaced by 1-2mm per side",
    )
```

The existing per-label print loop already walks whatever labels are present, so "traced" and "sloppy" print themselves. After the `corners scored` lines, add:

```python
        for label in ("traced", "sloppy"):
            present = [p for p in real.values() if label in p]
            if not present:
                continue
            # px/mm is the raster's own scale, so a shift in it means the fitted
            # card changed size -- a cheap summary of "did this crop move the
            # geometry". The millimetre displacement of each apex is measured
            # directly in the plan's final task; these metrics do not carry it.
            shift = [
                abs(p[label].get("px_per_mm", 0.0) - p["cropped"].get("px_per_mm", 0.0))
                for p in present
            ]
            print(f"  {label}: {len(present)} photo(s), max px/mm shift {max(shift):.2f}")
```

- [ ] **Step 4: Run it**

Run: `cd backend && .venv/Scripts/python.exe scripts/fixture_drift.py > <scratch>/drift-task1.log 2>&1; echo exit=$?`
Expected: `exit=0`, "no drift across 24 fixtures", a real-photo block that includes a `traced` row for `shadowed_photo` and **no** `shadowed_photo_traced` row.

Run: `.venv/Scripts/python.exe scripts/fixture_drift.py --sloppy > <scratch>/drift-task1-sloppy.log 2>&1; echo exit=$?`
Expected: `exit=0`, every photo gains a `sloppy` row, and the summary lines print.

Record in your report the traced row's four scores and px/mm for `shadowed_photo`, and the same for its `cropped` row — Task 6 compares against them.

- [ ] **Step 5: Document the sidecar**

Append to `backend/tests/fixtures/real_scans/README.md`:

```markdown
## Tracing a crop for a photograph

The harness's own "customer crop" is the pipeline's own fitted apexes, so it can never contain a
crop that *corrects* the fit — and that is the only case the crop-guided refit exists for. To
supply a real one, draw the crop you would drag in the app around the card (any image editor, a
bright line a few pixels wide), save it beside the photo as `<name>_traced.png`, and record its four
corners in `<name>.crop.json`:

```json
{ "points": [[x, y], [x, y], [x, y], [x, y]], "traced_by": "...", "note": "..." }
```

Points are top-left, top-right, bottom-right, bottom-left in the photograph's own pixels, along the
**centre** of the drawn stroke. `fixture_drift.py` then measures a `traced` path for that photo, and
skips the `_traced` image itself. Both files stay out of git, like the photographs.
```

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/fixture_drift.py backend/tests/fixtures/real_scans/README.md
git commit -m "Measure a traced crop and a deliberately sloppy one in the drift harness" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: A synthetic card whose shadow hides its bottom edge

**Files:**
- Modify: `backend/tests/fixtures/generate_samples.py`
- Modify: `backend/tests/fixtures/drift_baseline.json` (via `--update`)
- Test: `backend/tests/test_crop_refit.py` (create)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: fixture name `capture_shadowed_bottom`, built by `make_card_scan(..., shadow_bottom_band=True)`; `tests/test_crop_refit.py` with the helper `true_card_quad(name)`.

The real photograph cannot be committed, so this fixture is what pins the behaviour in CI. It must fail the *old* pipeline in the same way the photograph does: the detected outline stops short of the card's bottom edge.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_crop_refit.py`:

```python
"""A crop that disagrees with the fit, and what the pipeline does about it.

On a real photograph (`real_scans/shadowed_photo.jpg`) a shadow across the
lower half of the card puts that part of it on the background side of the
detector's threshold, so the outline stops about 5mm short of the cut. The
customer's crop said where the edge was and the pipeline threw it away: with a
crop traced on the true edges, the fitted apexes came back identical to the
pixel.

The photograph is not committable (the repo is public), so this fixture is the
committed form of the same failure.
"""

import cv2
import numpy as np

from tests.fixtures.generate_samples import build_fixture, card_size_mm
from zgrader.analysis import preprocessing

POKEMON_MM = card_size_mm("pokemon_front")


def true_card_quad(name: str) -> np.ndarray:
    """The card's real corners in a fixture, from the fixture's own geometry
    rather than from a detection that may be the thing under test.

    `make_card_scan` centres the card on an 8% margin, so the corners are a
    fixed fraction of the canvas.
    """
    image = build_fixture(name)
    h, w = image.shape[:2]
    margin_x, margin_y = w * 0.08, h * 0.08
    return np.array(
        [
            [margin_x, margin_y],
            [w - margin_x, margin_y],
            [w - margin_x, h - margin_y],
            [margin_x, h - margin_y],
        ],
        dtype=np.float64,
    )


def test_the_shadowed_fixture_reproduces_the_photographs_failure():
    """Without help, the outline stops short of the card's bottom edge -- the
    same shape of failure the real photograph shows."""
    image = build_fixture("capture_shadowed_bottom")
    truth = true_card_quad("capture_shadowed_bottom")

    box, _info = preprocessing.detect_boundary(image, expected_aspect=63.0 / 88.0)

    detected_bottom = float(np.max(np.array(box, dtype=np.float64)[:, 1]))
    true_bottom = float(truth[2][1])
    px_per_mm = (truth[2][1] - truth[0][1]) / 88.0
    short_by_mm = (true_bottom - detected_bottom) / px_per_mm
    assert short_by_mm > 3.0, f"the shadow only hides {short_by_mm:.1f}mm of the card"
    assert short_by_mm < 12.0, "the fixture hides so much card that it is a different failure"


def test_the_shadowed_fixture_still_looks_like_a_card_to_the_fit():
    """The fit must succeed on the wrong outline -- a fixture that merely
    declines would exercise the fallback, not the silent mis-fit."""
    image = build_fixture("capture_shadowed_bottom")

    rectified = preprocessing.rectify(image, *POKEMON_MM)

    assert rectified.geometry["method"] == "ransac"
    assert "geometry_unverified" not in rectified.limitations
```

- [ ] **Step 2: Run it to watch it fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_crop_refit.py -v > <scratch>/task2-red.log 2>&1; echo exit=$?`
Expected: FAIL with `KeyError: Unknown fixture: capture_shadowed_bottom`.

- [ ] **Step 3: Add the shadow band to the fixture builder**

In `backend/tests/fixtures/generate_samples.py`, beside the `_CORNER_SHADOW_RADIUS_MM` block, add:

```python
#: A shadow lying across the lower part of the card, for
#: `capture_shadowed_bottom`. The floor is what puts the shadowed card below
#: the threshold that separates card from backing, so the detected outline
#: stops inside the card -- the committed form of the failure
#: `real_scans/shadowed_photo.jpg` shows, where a shadow cost about 5mm of the
#: bottom edge and the fit reported no problem at all.
_BOTTOM_SHADOW_FLOOR = 0.40
#: Where the shadow starts, as a fraction of the card's height. Below the
#: artwork, so the card still reads as a card to the aspect check.
_BOTTOM_SHADOW_START = 0.55
```

Add the keyword to `make_card_scan`'s signature, directly after `shadow_bottom_left_corner: bool = False,`:

```python
    shadow_bottom_band: bool = False,
```

In the body, directly after the `if shadow_bottom_left_corner:` block, add:

```python
    if shadow_bottom_band:
        # A soft ramp from full brightness at `_BOTTOM_SHADOW_START` down to
        # `_BOTTOM_SHADOW_FLOOR` at the bottom of the frame, applied to the
        # whole canvas so the card and the backing below it darken together --
        # which is what a shadow falling across a desk actually does, and why
        # one threshold cannot separate them any more.
        height = scan.shape[0]
        rows = np.arange(height, dtype=np.float32) / max(1, height - 1)
        ramp = np.clip((rows - _BOTTOM_SHADOW_START) / max(1e-6, 1.0 - _BOTTOM_SHADOW_START), 0.0, 1.0)
        factor = 1.0 - ramp * (1.0 - _BOTTOM_SHADOW_FLOOR)
        scan = np.clip(scan.astype(np.float32) * factor[:, None, None], 0, 255).astype(np.uint8)
```

(Use whatever the local variable for the assembled scan is called at that point in the function — read the surrounding code and match it; the corner-shadow block above works on the same array.)

Register the fixture in `FIXTURES`, directly after the `capture_shadowed_corner` entry:

```python
    (
        # A shadow across the lower card: detection's threshold cuts the card
        # off inside its own edge and the fit reports no problem, which is what
        # makes it worth a fixture -- see tests/test_crop_refit.py.
        "capture_shadowed_bottom",
        _POKEMON,
        dict(shadow_bottom_band=True),
    ),
```

- [ ] **Step 4: Run the test again**

Run: `.venv/Scripts/python.exe -m pytest tests/test_crop_refit.py -v > <scratch>/task2-green.log 2>&1; echo exit=$?`
Expected: both tests PASS. If `short_by_mm` is outside 3–12mm, adjust `_BOTTOM_SHADOW_FLOOR` (lower = more card lost) and re-run; record the final value and the measured shortfall in your report.

- [ ] **Step 5: Record the new fixture in the baseline**

Run: `.venv/Scripts/python.exe scripts/fixture_drift.py > <scratch>/task2-drift-before.log 2>&1; echo exit=$?`
Expected: `exit=1`, and the only fixture reported is `capture_shadowed_bottom` as `<entire fixture>` (new). If any *other* fixture moved, stop and report — adding a fixture must not change an existing one.

Run: `.venv/Scripts/python.exe scripts/fixture_drift.py --update > <scratch>/task2-update.log 2>&1; echo exit=$?`
Then: `git diff --stat backend/tests/fixtures/drift_baseline.json` and confirm the diff only **adds** an entry.

Run: `.venv/Scripts/python.exe -m pytest tests/test_fixture_drift.py -v > <scratch>/task2-drift-test.log 2>&1; echo exit=$?`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/fixtures/generate_samples.py backend/tests/fixtures/drift_baseline.json backend/tests/test_crop_refit.py
git commit -m "Add a shadowed-bottom fixture that loses its own edge to the threshold" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Search for a side near the customer's crop line

**Files:**
- Modify: `backend/zgrader/analysis/geometry.py`
- Test: `backend/tests/test_crop_refit.py` (append)

**Interfaces:**
- Consumes: `true_card_quad` and the `capture_shadowed_bottom` fixture (Task 2).
- Produces:
  - `geometry.CROP_REFIT_TRIGGER_MM = 2.0`, `geometry.CROP_REFIT_BAND_MM = 3.0`
  - `geometry.CropRefit` — `geometry: CardGeometry`, `moved: dict[str, dict[str, float]]`, `unresolved: tuple[str, ...]`
  - `geometry.refit_geometry_near_crop(image, fitted, crop_quad, px_per_mm, *, trigger_mm=CROP_REFIT_TRIGGER_MM, band_mm=CROP_REFIT_BAND_MM) -> CropRefit`

Pure geometry: this task wires nothing into `rectify` (Task 4 does), so nothing measured changes and the drift baseline must not move.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_crop_refit.py`:

```python
from zgrader.analysis import geometry


def _fitted(image, quad=None):
    """The pipeline's own fit for an image, plus the px/mm its raster is built
    at -- the two inputs the refit takes."""
    box, info = preprocessing.detect_boundary(image, expected_aspect=63.0 / 88.0)
    fit = geometry.fit_card_geometry(image, info["contour"], box)
    assert fit is not None, "this fixture is meant to fit, just in the wrong place"
    px_per_mm = preprocessing._canonical_size(fit.apexes, *POKEMON_MM)[2]
    return fit, px_per_mm


def _bottom_offset_mm(fit, truth, px_per_mm) -> float:
    """How far the fitted bottom line sits from the card's true bottom edge."""
    midpoint = (truth[2] + truth[3]) / 2
    return float(abs(fit.sides["bottom"].signed_distance(midpoint[None])[0])) / px_per_mm


def test_a_side_the_crop_agrees_with_is_left_alone():
    """The common case: an untouched crop is the detected box, so every side is
    already where the crop says. Nothing may move -- this is the guard that a
    crop half a millimetre inside the card still cannot trim damage away."""
    image = build_fixture("pokemon_front")
    fit, px_per_mm = _fitted(image)
    crop = np.array(fit.apexes, dtype=np.float64)

    refit = geometry.refit_geometry_near_crop(image, fit, crop, px_per_mm)

    assert refit.moved == {}
    assert refit.unresolved == ()
    assert np.allclose(refit.geometry.apexes, fit.apexes)


def test_a_crop_just_inside_the_card_does_not_move_the_fit():
    """Half a millimetre in is well under the trigger: the crop is a hint, and
    a hint that tight must not pull the measured edge inward."""
    image = build_fixture("pokemon_front")
    fit, px_per_mm = _fitted(image)
    centre = fit.apexes.mean(axis=0)
    crop = centre + (fit.apexes - centre) * (1.0 - (0.5 * px_per_mm) / np.linalg.norm(fit.apexes[0] - centre))

    refit = geometry.refit_geometry_near_crop(image, fit, crop, px_per_mm)

    assert refit.moved == {}
    assert np.allclose(refit.geometry.apexes, fit.apexes)


def test_a_crop_on_the_true_edge_recovers_a_side_the_shadow_hid():
    """The whole point. The fit stops inside the card; the crop says where the
    edge is; the re-search finds it there rather than taking the crop's word."""
    image = build_fixture("capture_shadowed_bottom")
    truth = true_card_quad("capture_shadowed_bottom")
    fit, px_per_mm = _fitted(image)
    assert _bottom_offset_mm(fit, truth, px_per_mm) > 3.0, "fixture no longer hides the edge"

    refit = geometry.refit_geometry_near_crop(image, fit, truth, px_per_mm)

    assert "bottom" in refit.moved
    assert refit.unresolved == ()
    assert _bottom_offset_mm(refit.geometry, truth, px_per_mm) < 0.5
    assert refit.moved["bottom"]["disagreement_mm"] > 3.0
    assert refit.moved["bottom"]["moved_mm"] > 3.0


def test_sides_the_crop_agrees_with_stay_put_when_another_is_refit():
    image = build_fixture("capture_shadowed_bottom")
    truth = true_card_quad("capture_shadowed_bottom")
    fit, px_per_mm = _fitted(image)

    refit = geometry.refit_geometry_near_crop(image, fit, truth, px_per_mm)

    for name in ("left", "right", "top"):
        assert name not in refit.moved
        assert refit.geometry.sides[name].offset == fit.sides[name].offset


def test_a_side_with_no_edge_near_the_crop_is_unresolved():
    """A crop line over featureless background has nothing to find. Saying so
    is the honest answer; inventing a line from the crop is not."""
    image = build_fixture("pokemon_front")
    fit, px_per_mm = _fitted(image)
    crop = np.array(fit.apexes, dtype=np.float64)
    # Push the bottom line far out into the flat backing, past any edge.
    crop[2][1] += 6.0 * px_per_mm
    crop[3][1] += 6.0 * px_per_mm

    refit = geometry.refit_geometry_near_crop(image, fit, crop, px_per_mm)

    assert refit.unresolved == ("bottom",)
    assert "bottom" not in refit.moved


def test_the_refit_is_deterministic():
    image = build_fixture("capture_shadowed_bottom")
    truth = true_card_quad("capture_shadowed_bottom")
    fit, px_per_mm = _fitted(image)

    first = geometry.refit_geometry_near_crop(image, fit, truth, px_per_mm)
    second = geometry.refit_geometry_near_crop(image, fit, truth, px_per_mm)

    assert np.array_equal(first.geometry.apexes, second.geometry.apexes)
```

- [ ] **Step 2: Run them to watch them fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_crop_refit.py -v > <scratch>/task3-red.log 2>&1; echo exit=$?`
Expected: the two Task 2 tests still pass; every new test FAILS with `AttributeError: module 'zgrader.analysis.geometry' has no attribute 'refit_geometry_near_crop'`.

- [ ] **Step 3: Add the constants and the result type**

At the end of `backend/zgrader/analysis/geometry.py`, add:

```python
# --- Crop-guided refit -------------------------------------------------------
# The customer's crop is a region of interest, not the card's geometry -- a
# crop half a millimetre inside the card must not trim the damage out of the
# image, which is why `rectify` fits the edges itself. But when the two
# disagree by *millimetres*, the crop is evidence the fit landed on the wrong
# step: on `real_scans/shadowed_photo.jpg` a shadow put the lower card on the
# background side of one threshold and the outline stopped about 5mm inside
# the cut, with a crop traced on the true edges changing the apexes by zero
# pixels. So a side that disagrees is searched for again near where the
# customer put it -- in the image, never taken from the crop.

#: How far a fitted side may sit from the crop line before that side is
#: searched again, in millimetres. ARBITRARY until measured: above the slop of
#: a crop traced by finger on a phone, below the shortfall observed on the real
#: photograph.
CROP_REFIT_TRIGGER_MM = 2.0

#: How far either side of the crop line that search looks, in millimetres.
#: ARBITRARY: wide enough for a crop a couple of millimetres off the edge,
#: narrow enough that a band around a crop *on* the edge cannot reach a printed
#: border line a few millimetres inside the cut.
CROP_REFIT_BAND_MM = 3.0

#: Which two ordered crop corners bound each side (top-left, top-right,
#: bottom-right, bottom-left), matching `_split_sides`.
_CROP_SIDE_CORNERS = {"top": (0, 1), "right": (1, 2), "bottom": (3, 2), "left": (0, 3)}


@dataclasses.dataclass(frozen=True)
class CropRefit:
    """The geometry after the crop was allowed to argue with it."""

    geometry: CardGeometry
    #: Per side that was re-searched: how far it disagreed with the crop and
    #: how far the line actually moved, both in millimetres.
    moved: dict[str, dict[str, float]]
    #: Sides that disagreed and whose re-search found no edge to move to. The
    #: caller treats these as "the fit cannot be trusted here" -- there is no
    #: half-trusted geometry.
    unresolved: tuple[str, ...]
```

- [ ] **Step 4: Add the band search**

Directly after the dataclass:

```python
def _fit_side_near_line(
    value: np.ndarray,
    start: np.ndarray,
    end: np.ndarray,
    centre: np.ndarray,
    band_px: float,
) -> SideFit | None:
    """Re-find one card edge within `band_px` of the segment start->end.

    Takes the **outermost** qualifying gradient peak along each normal, not the
    strongest. Moving outward from the card, the last strong step is the
    card-to-background transition; a printed border or a text box inside the
    card can be stronger than a shadowed edge, and taking the strongest is how
    `border.py`'s rays lose to a printed box.
    """
    normal = _unit_normal(start, end)
    if normal is None:
        return None
    offset = float(normal @ start)
    # Point the normal into the card, so a tap index runs outside -> inside.
    if (centre @ normal - offset) < 0:
        normal, offset = -normal, -offset

    ts = np.linspace(CORNER_MARGIN_FRACTION, 1.0 - CORNER_MARGIN_FRACTION, SUBPIXEL_SAMPLES)
    bases = start + ts[:, None] * (end - start)
    taps = np.arange(-band_px, band_px + SUBPIXEL_STEP_PX, SUBPIXEL_STEP_PX)
    xs = bases[:, 0][:, None] + taps[None, :] * normal[0]
    ys = bases[:, 1][:, None] + taps[None, :] * normal[1]
    gradient = np.abs(np.gradient(_sample_bilinear(value, xs, ys), axis=1))

    # A qualifying peak is a local maximum above the response floor, with a
    # neighbour on each side so the parabola has something to fit.
    qualifies = np.zeros_like(gradient, dtype=bool)
    qualifies[:, 1:-1] = (
        (gradient[:, 1:-1] >= gradient[:, :-2])
        & (gradient[:, 1:-1] >= gradient[:, 2:])
        & (gradient[:, 1:-1] >= MIN_GRADIENT_RESPONSE)
    )
    usable = qualifies.any(axis=1)
    if usable.sum() < MIN_REFINED_FRACTION * SUBPIXEL_SAMPLES:
        return None

    peak = np.argmax(qualifies, axis=1)  # first True is the outermost tap
    safe_peak = np.clip(peak, 1, gradient.shape[1] - 2)
    idx = np.arange(len(peak))
    sub = _parabola_vertex(
        gradient[idx, safe_peak - 1], gradient[idx, safe_peak], gradient[idx, safe_peak + 1]
    )
    along_normal = taps[safe_peak] + sub * SUBPIXEL_STEP_PX
    points = (bases + along_normal[:, None] * normal[None, :])[usable]

    fit_normal, fit_offset, mask = fit_line_ransac(points)
    if mask.sum() < MIN_REFINED_FRACTION * len(points):
        return None
    fit_normal, fit_offset = _fit_total_least_squares(points[mask])
    if (centre @ fit_normal - fit_offset) < 0:
        fit_normal, fit_offset = -fit_normal, -fit_offset
    residuals = points[mask] @ fit_normal - fit_offset
    return SideFit(
        normal=fit_normal,
        offset=fit_offset,
        inlier_count=int(mask.sum()),
        total_points=len(points),
        refined=True,
        roughness_px=float(np.std(residuals)),
        max_excursion_px=float(np.max(np.abs(residuals))),
        bow_px=_bow(residuals),
    )
```

- [ ] **Step 5: Add the entry point**

Directly after it:

```python
def refit_geometry_near_crop(
    image: np.ndarray,
    fitted: CardGeometry,
    crop_quad: np.ndarray,
    px_per_mm: float,
    *,
    trigger_mm: float = CROP_REFIT_TRIGGER_MM,
    band_mm: float = CROP_REFIT_BAND_MM,
) -> CropRefit:
    """Let the customer's crop argue with the fit, one side at a time.

    `crop_quad` must be in the same coordinates as `image` and `fitted` -- the
    caller subtracts any region-of-interest offset first. A side the crop
    agrees with to within `trigger_mm` is returned untouched, so an untouched
    crop (which is the detected box) and a crop traced slightly inside the card
    both leave the measured geometry exactly as it was.
    """
    ordered = _order_quad(crop_quad)
    centre = ordered.mean(axis=0)
    value = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 2]

    sides = dict(fitted.sides)
    moved: dict[str, dict[str, float]] = {}
    unresolved: list[str] = []

    for name, (i, j) in _CROP_SIDE_CORNERS.items():
        start, end = ordered[i], ordered[j]
        ts = np.array([CORNER_MARGIN_FRACTION, 0.5, 1.0 - CORNER_MARGIN_FRACTION])
        samples = start + ts[:, None] * (end - start)
        disagreement_mm = float(np.max(np.abs(sides[name].signed_distance(samples)))) / px_per_mm
        if disagreement_mm <= trigger_mm:
            continue

        found = _fit_side_near_line(value, start, end, centre, band_mm * px_per_mm)
        if found is None:
            unresolved.append(name)
            continue

        midpoint = ((start + end) / 2)[None]
        before = float(sides[name].signed_distance(midpoint)[0])
        after = float(found.signed_distance(midpoint)[0])
        sides[name] = found
        moved[name] = {
            "disagreement_mm": round(disagreement_mm, 2),
            "moved_mm": round(abs(before - after) / px_per_mm, 2),
        }

    if not moved:
        return CropRefit(geometry=fitted, moved={}, unresolved=tuple(sorted(unresolved)))

    corners = {
        "top_left": ("top", "left"),
        "top_right": ("top", "right"),
        "bottom_right": ("bottom", "right"),
        "bottom_left": ("bottom", "left"),
    }
    apexes = []
    for _corner, (a, b) in corners.items():
        point = _intersect(sides[a], sides[b])
        if point is None:
            # Two adjacent sides that no longer meet is a fit gone wrong, not a
            # corner: report both as unresolved rather than inventing an apex.
            return CropRefit(
                geometry=fitted, moved=moved, unresolved=tuple(sorted(set(unresolved) | {a, b}))
            )
        apexes.append(point)

    refitted = CardGeometry(
        apexes=_order_quad(np.array(apexes, dtype=np.float64)),
        sides=sides,
        # Still "ransac": every side here came from a line fitted to the image.
        method=fitted.method,
    )
    return CropRefit(geometry=refitted, moved=moved, unresolved=tuple(sorted(unresolved)))
```

- [ ] **Step 6: Run the tests and the drift check**

Run: `.venv/Scripts/python.exe -m pytest tests/test_crop_refit.py tests/test_geometry.py -v > <scratch>/task3-green.log 2>&1; echo exit=$?`
Expected: all PASS, `exit=0`.

Run: `.venv/Scripts/python.exe -m pytest tests/test_fixture_drift.py -v > <scratch>/task3-drift.log 2>&1; echo exit=$?`
Expected: PASS — nothing is wired in yet, so no measurement can have moved.

- [ ] **Step 7: Commit**

```bash
git add backend/zgrader/analysis/geometry.py backend/tests/test_crop_refit.py
git commit -m "Search for a card edge near the customer's crop line when the fit disagrees" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Wire it into rectify, and decline when the search finds nothing

**Files:**
- Modify: `backend/zgrader/analysis/preprocessing.py` (`rectify`, the fitted branch)
- Modify: `backend/zgrader/analysis/assessment.py` (new code)
- Test: `backend/tests/test_crop_refit.py` (append)

**Interfaces:**
- Consumes: `geometry.refit_geometry_near_crop`, `geometry.CROP_REFIT_*` (Task 3).
- Produces:
  - `assessment.GEOMETRY_CROP_DISAGREEMENT = "geometry_crop_disagreement"`, registered in `ALL_LIMITATION_CODES`.
  - `rectify`'s geometry block gains `"refit_sides": {side: {"disagreement_mm": float, "moved_mm": float}}` when any side was re-searched.
  - When a side is unresolved, `rectify` falls back to the crop: `method` `"user_crop"`, limitations `GEOMETRY_UNVERIFIED` + `GEOMETRY_CROP_DISAGREEMENT`, and the geometry block records `"crop_disagreement_sides": [name, ...]`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_crop_refit.py`:

```python
from zgrader.analysis import assessment


def test_rectify_recovers_the_hidden_edge_when_the_crop_says_where_it_is():
    image = build_fixture("capture_shadowed_bottom")
    truth = true_card_quad("capture_shadowed_bottom")

    uncropped = preprocessing.rectify(image, *POKEMON_MM)
    guided = preprocessing.rectify(image, *POKEMON_MM, roi_quad=truth)

    px_per_mm = guided.px_per_mm
    bottom_before = float(np.mean(np.array(uncropped.geometry["apexes"])[2:4, 1]))
    bottom_after = float(np.mean(np.array(guided.geometry["apexes"])[2:4, 1]))
    true_bottom = float(truth[2][1])

    assert (true_bottom - bottom_before) / px_per_mm > 3.0, "fixture no longer hides the edge"
    assert abs(true_bottom - bottom_after) / px_per_mm < 0.5
    assert guided.geometry["method"] == "ransac"
    assert "bottom" in guided.geometry["refit_sides"]
    assert assessment.GEOMETRY_UNVERIFIED not in guided.limitations
    assert assessment.GEOMETRY_CROP_DISAGREEMENT not in guided.limitations


def test_an_untouched_crop_changes_nothing_at_all():
    """The path every production submission takes today: the crop is the
    detected box. The refit must be invisible there, byte for byte."""
    image = build_fixture("pokemon_front")
    uncropped = preprocessing.rectify(image, *POKEMON_MM)
    crop = np.array(uncropped.geometry["apexes"], dtype=np.float64)

    cropped = preprocessing.rectify(image, *POKEMON_MM, roi_quad=crop)

    assert cropped.geometry["apexes"] == uncropped.geometry["apexes"]
    assert "refit_sides" not in cropped.geometry
    assert list(cropped.limitations) == list(uncropped.limitations)


def test_a_crop_over_background_declines_rather_than_taking_the_crop_s_word():
    image = build_fixture("pokemon_front")
    uncropped = preprocessing.rectify(image, *POKEMON_MM)
    crop = np.array(uncropped.geometry["apexes"], dtype=np.float64)
    crop[2][1] += 6.0 * uncropped.px_per_mm
    crop[3][1] += 6.0 * uncropped.px_per_mm

    guided = preprocessing.rectify(image, *POKEMON_MM, roi_quad=crop)

    assert guided.geometry["method"] == "user_crop"
    assert assessment.GEOMETRY_UNVERIFIED in guided.limitations
    assert assessment.GEOMETRY_CROP_DISAGREEMENT in guided.limitations
    assert guided.geometry["crop_disagreement_sides"] == ["bottom"]


def test_the_refit_survives_a_crop_away_from_the_image_origin():
    """The fit runs in the region of interest's coordinates and the crop
    arrives in the image's, so the offset has to be taken off before they are
    compared. That offset has been applied with the wrong sign here before, and
    no fixture can show it without padding: an unpadded fixture's ROI origin
    clips to (0, 0), where both signs agree.
    """
    padded = cv2.copyMakeBorder(
        build_fixture("capture_shadowed_bottom"), 400, 0, 300, 0, cv2.BORDER_CONSTANT, value=(0, 0, 0)
    )
    truth = true_card_quad("capture_shadowed_bottom") + np.array([300.0, 400.0])

    guided = preprocessing.rectify(padded, *POKEMON_MM, roi_quad=truth)

    bottom = float(np.mean(np.array(guided.geometry["apexes"])[2:4, 1]))
    assert abs(float(truth[2][1]) - bottom) / guided.px_per_mm < 0.5
    assert "bottom" in guided.geometry["refit_sides"]
    missing = float(np.mean(guided.mask == 0))
    assert missing < 0.05, f"{missing:.1%} of the raster reads as missing card"
```

- [ ] **Step 2: Run them to watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_crop_refit.py -v > <scratch>/task4-red.log 2>&1; echo exit=$?`
Expected: the four new tests FAIL — `AttributeError` on `GEOMETRY_CROP_DISAGREEMENT`, then `KeyError: 'refit_sides'`.

- [ ] **Step 3: Register the limitation code**

In `backend/zgrader/analysis/assessment.py`, directly after the `GEOMETRY_ASPECT_MISMATCH` declaration:

```python
#: The customer's crop disagreed with a fitted edge and no edge could be found
#: near where they put it, so the crop is all there is for that side.
GEOMETRY_CROP_DISAGREEMENT = "geometry_crop_disagreement"
```

Add `GEOMETRY_CROP_DISAGREEMENT,` to `ALL_LIMITATION_CODES` directly after `GEOMETRY_ASPECT_MISMATCH,`. It is **not** added to `DISQUALIFYING_LIMITATIONS` or `EXTERNAL_LIMITATION_FACTORS`: it always travels with `GEOMETRY_UNVERIFIED`, which already disqualifies, and its job is to tell the customer *which* thing went wrong.

- [ ] **Step 4: Wire the refit into rectify**

In `backend/zgrader/analysis/preprocessing.py`, in `rectify`, replace the `if fitted is not None:` branch (from that line through the `geometry_block["apexes"] = [...]` assignment) with:

```python
    crop_disagreement: list[str] = []
    if fitted is not None and roi_quad is not None:
        # The crop is evidence about where each edge is, not the edge itself.
        # A side the crop agrees with is untouched; one it disagrees with is
        # searched for again near the crop line, in the image. Both the fit and
        # the crop have to be in the same coordinates first: the fit ran inside
        # the region of interest, the crop arrived in the source image's.
        px_per_mm_estimate = _canonical_size(fitted.apexes, width_mm, height_mm)[2]
        refit = geometry.refit_geometry_near_crop(
            search, fitted, roi_quad - offset, px_per_mm_estimate
        )
        crop_disagreement = list(refit.unresolved)
        if not crop_disagreement:
            fitted = refit.geometry
            refit_sides = refit.moved
        else:
            # A side that disagreed and could not be re-found leaves nothing
            # trustworthy to measure that edge from, so the whole fit is set
            # aside rather than kept with one invented side.
            fitted = None
            refit_sides = {}
    else:
        refit_sides = {}

    if fitted is not None:
        apexes = fitted.apexes + offset
        geometry_block = fitted.as_dict()
        # The fit ran inside the region of interest, so its apexes are in ROI
        # coordinates. The warp above already adds the offset; the recorded
        # copy has to as well, or the stored geometry describes a card
        # somewhere else in the photo whenever a crop was supplied.
        geometry_block["apexes"] = [
            [round(float(x), 2), round(float(y), 2)] for x, y in apexes
        ]
        if refit_sides:
            geometry_block["refit_sides"] = refit_sides
```

In the `elif roi_quad is not None:` branch that follows (the user-crop fallback), replace its body's limitation append with:

```python
        apexes = _order_points(roi_quad.astype("float32")).astype(np.float64)
        geometry_block = {"method": "user_crop", "apexes": apexes.round(2).tolist(), "sides": {}}
        limitations.append(assessment.GEOMETRY_UNVERIFIED)
        if crop_disagreement:
            # Not merely "no card found in the crop": the card was found, and
            # it disagreed with the crop on a side where nothing edge-shaped
            # sits near the customer's line. The copy says which side.
            geometry_block["crop_disagreement_sides"] = crop_disagreement
            limitations.append(assessment.GEOMETRY_CROP_DISAGREEMENT)
```

Confirm `geometry` is imported in that function (it is: `from zgrader.analysis import assessment, geometry`), and that `_canonical_size` is defined above `rectify` in the same module.

- [ ] **Step 5: Run the tests, the geometry suite and the drift check**

Run: `.venv/Scripts/python.exe -m pytest tests/test_crop_refit.py tests/test_geometry.py tests/test_geometry_disqualifies.py tests/test_corners.py -v > <scratch>/task4-green.log 2>&1; echo exit=$?`
Expected: all PASS, `exit=0`.

Run: `.venv/Scripts/python.exe scripts/fixture_drift.py > <scratch>/task4-drift.log 2>&1; echo exit=$?`
Expected: `exit=0`, "no drift across 25 fixtures". Every synthetic fixture is measured **uncropped** by the harness, and the cropped path uses the fit's own apexes, so nothing may move. If anything does, stop and report it — that is the refit firing where the crop agreed.

- [ ] **Step 6: Commit**

```bash
git add backend/zgrader/analysis/preprocessing.py backend/zgrader/analysis/assessment.py backend/tests/test_crop_refit.py
git commit -m "Let a disagreeing crop re-search its side, and decline when nothing is there" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Say which side disagreed, at the crop step, in both languages

**Files:**
- Modify: `backend/zgrader/reports/strings.py` (`LIMITATION_LABELS`, EN and ES)
- Modify: `frontend/lib/i18n/en.ts`, `frontend/lib/i18n/es.ts` (`submissionDetail.limitation`)
- Test: `backend/tests/test_api_check_crop.py` (append)

**Interfaces:**
- Consumes: `assessment.GEOMETRY_CROP_DISAGREEMENT` (Task 4).
- Produces: customer-facing copy for that code everywhere a limitation code is rendered.

`POST /submissions/{code}/scans/{side}/check-crop` already returns `limitations` and `CropAdjustStep` already renders each code's results-page copy, so no component changes: the code needs copy, and a test that it reaches the response.

- [ ] **Step 1: Write the failing test**

Read the existing tests in `backend/tests/test_api_check_crop.py` first and follow their setup exactly (account, submission, uploaded sample scan). Append a test in that style:

```python
def test_a_crop_whose_edge_is_not_there_names_the_side(db_session):
    """The customer dragged a side out over the backing. The check says so
    before they spend the submission, and names which side rather than the
    generic "could not fit the edges"."""
    token, code = _submission_with_front_scan("crop-disagreement@example.com")
    points = _detected_crop(code)
    # Push the bottom edge 6mm below the card, into featureless backing.
    px_per_mm = _px_per_mm(code)
    points[2][1] += 6.0 * px_per_mm
    points[3][1] += 6.0 * px_per_mm

    resp = client.post(
        f"/submissions/{code}/scans/front/check-crop",
        json={"points": points},
        headers=_auth(token),
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["boundary_found"] is False
    assert "geometry_crop_disagreement" in body["limitations"]
```

If the file has no helper for the detected crop or the scale, write the smallest ones that serve this test, named as above, using `GET /submissions/{code}/scans/front/suggest-crop` for the points and `preprocessing.rectify` on the stored scan for `px_per_mm`.

- [ ] **Step 2: Run it to watch it fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_api_check_crop.py -v > <scratch>/task5-red.log 2>&1; echo exit=$?`
Expected: the new test FAILS on the missing code in `limitations` (the endpoint answers, the code is absent) — unless Task 4 already delivers it, in which case it fails instead on the missing copy asserted in Step 4's test run. Record which.

- [ ] **Step 3: Add the report copy**

`backend/zgrader/reports/strings.py`, in `LIMITATION_LABELS["en"]`, directly after the `geometry_aspect_mismatch` entry:

```python
        "geometry_crop_disagreement": (
            "The crop supplied with this scan disagreed with the card edge found in the "
            "image, and no edge could be found where the crop said one was -- so that side "
            "rests on the crop itself rather than on anything measured."
        ),
```

and in `LIMITATION_LABELS["es"]`, in the same position:

```python
        "geometry_crop_disagreement": (
            "El recorte enviado con este escaneo no coincide con el filo de la carta "
            "encontrado en la imagen, y no se pudo encontrar ningún filo donde el recorte "
            "indicaba -- así que ese lado se apoya en el recorte y no en algo medido."
        ),
```

- [ ] **Step 4: Add the page copy**

`frontend/lib/i18n/en.ts`, in `submissionDetail.limitation`, after `centering_client_placed`:

```ts
      geometry_crop_disagreement:
        "Your crop and the card edge we found disagree, and there's no edge where the crop says one is — so that side rests on your crop rather than on a measurement. Drag that side onto the card's edge and check again.",
```

`frontend/lib/i18n/es.ts`, same position:

```ts
      geometry_crop_disagreement:
        "Su recorte y el filo de la carta que encontramos no coinciden, y no hay ningún filo donde el recorte indica: ese lado se apoya en su recorte y no en una medición. Arrastre ese lado hasta el filo de la carta y vuelva a comprobarlo.",
```

- [ ] **Step 5: Run the test and the frontend checks**

Run: `.venv/Scripts/python.exe -m pytest tests/test_api_check_crop.py tests/test_crop_refit.py -v > <scratch>/task5-green.log 2>&1; echo exit=$?`
Expected: all PASS, `exit=0`.

Run: `cd ../frontend && npx tsc --noEmit > <scratch>/task5-tsc.log 2>&1; echo exit=$?` then `npx next build > <scratch>/task5-build.log 2>&1; echo exit=$?`
Expected: both `exit=0`. (`tsc` is also the check that `es.ts` gained the same key.)

- [ ] **Step 6: Commit**

```bash
git add backend/zgrader/reports/strings.py frontend/lib/i18n/en.ts frontend/lib/i18n/es.ts backend/tests/test_api_check_crop.py
git commit -m "Name the disagreeing side at the crop step, in both languages" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Measure it on the real photograph, set the constants, then document

**Files:**
- Modify (only if the measurements say so): `backend/zgrader/analysis/geometry.py` (the two constants)
- Modify: `AGENTS.md`
- Modify: `frontend/public/methodology/*` (regenerated figures), if the generator writes any change

This is the task the spec exists for. **The numbers decide the constants, not the other way round.** Nothing here is tuned to make a test pass.

- [ ] **Step 1: Measure the real photograph's true bottom edge**

The acceptance criterion is "within 0.5mm of the true edge", so the true edge has to be measured rather than assumed. Write `<scratch>/profile_bottom.py` that, for `backend/tests/fixtures/real_scans/shadowed_photo.jpg`, samples the Lab L* channel down columns 500, 1000, 1500, 2000, 2400 between y=3400 and y=3950, smooths with a Gaussian (σ=3), and prints for each column the y of the **strongest falling step below y=3700**. Run it and record the values; their mean is the true bottom edge. (An earlier profile of this photograph put it at y≈3785–3805, which is the figure to compare against.)

- [ ] **Step 2: Run the harness on the real set**

Run from `backend/`:
- `.venv/Scripts/python.exe scripts/fixture_drift.py > <scratch>/task6-drift.log 2>&1; echo exit=$?`
- `.venv/Scripts/python.exe scripts/fixture_drift.py --sloppy > <scratch>/task6-sloppy.log 2>&1; echo exit=$?`

Then write `<scratch>/task6_sloppy_apexes.py`, which for **every** real photograph rectifies
three ways — with `fixture_drift.crop_like_a_customer`, with `fixture_drift.sloppy_crop` of that
crop (same seed the harness uses), and uncropped — and prints per photo: the largest per-apex
distance between the cropped and sloppy runs **in millimetres** (divide by that run's `px_per_mm`),
each run's `geometry["method"]`, and its limitations. That table is criterion 2's evidence; the
harness's px/mm summary is not.

Then write `<scratch>/task6_apexes.py` to print, for `shadowed_photo.jpg`: the apexes, `px_per_mm`, `aspect_deviation`, `limitations` and `refit_sides` for three paths — uncropped, the harness crop (`crop_like_a_customer`), and the traced crop from the sidecar — plus the corners category's `raw_score` and limitations for the traced path (via `zgrader.analysis.fixture_metrics.measure_image`). Run it and record everything.

- [ ] **Step 3: Judge against the acceptance criteria**

Write these five into your report, each with its number:

1. **The traced crop recovers the edge:** bottom apexes within **0.5mm** of Step 1's measured true edge, `aspect_deviation` down from 0.058 to ≤0.02, and no `geometry_unverified`.
2. **Sloppy crops do not move a good fit:** for every other real photograph, the largest apex displacement between the `cropped` and `sloppy` runs is **≤0.5mm**, and no photograph that fitted under `cropped` falls back under `sloppy`.
3. **The untouched paths are unchanged:** every real photograph's `uncropped` and `cropped` scores are identical to the pre-change values recorded in Task 1 Step 4.
4. **Synthetic drift:** none beyond `capture_shadowed_bottom`.
5. **Corners on the real photo:** its score and limitations before and after, stated plainly (the spec expects the bottom corners to decline rather than invent loss, because the material mask still comes from the shadow-truncated contour).

- [ ] **Step 4: Set the constants, or report that you cannot**

If any of 1–3 fails, try other values of `CROP_REFIT_TRIGGER_MM` and `CROP_REFIT_BAND_MM` — sweep trigger over 1.0/1.5/2.0/3.0 and band over 2.0/3.0/4.0/5.0, re-running Steps 2–3 for each pair, and record the table. Two rules:
- The band must stay under the region-of-interest margin the crop is expanded by (10% of the crop's size; at these image sizes about 6mm), or the search runs off the pixels it was given. Assert this in a test if you change the default.
- If **no pair** satisfies both 1 and 2, stop and report that as the finding, with the table. That is a real result about the signal, not a failure to tune — the spec says so. Do not weaken the acceptance criteria to fit.

Update the two constants' comments with the measured justification, replacing "ARBITRARY until measured" with what the sweep showed.

- [ ] **Step 5: Regenerate the methodology figures**

Run: `.venv/Scripts/python.exe scripts/generate_methodology_figures.py > <scratch>/task6-figures.log 2>&1; echo exit=$?`
Then `git status --short` and report which figures changed. Run `.venv/Scripts/python.exe -m pytest tests/test_methodology_figures.py -v > <scratch>/task6-figtest.log 2>&1; echo exit=$?` — expected PASS.

- [ ] **Step 6: The full suite and the frontend build**

Run: `.venv/Scripts/python.exe -m pytest -q > <scratch>/task6-full.log 2>&1; echo exit=$?` (about 35 minutes; run it in the foreground with a long timeout and read the summary line).
Expected: `exit=0`, count ≥ 819 plus the new tests, warnings unchanged at 11.

Run the frontend checks from `frontend/`: `npx tsc --noEmit` and `npx next build`, both `exit=0`.

- [ ] **Step 7: Write it into AGENTS.md**

Amend the invariant that begins "**Measurement geometry comes from fitted card edges, never from the customer's crop.**" by appending:

```markdown
That stands, with one addition the crop earned by being right. When a fitted side sits more than
`geometry.CROP_REFIT_TRIGGER_MM` from the customer's crop line, that side is searched for again
within `geometry.CROP_REFIT_BAND_MM` of the line -- in the image, taking the **outermost** strong
gradient peak, never the crop itself. The crop is evidence about where to look; the edge still comes
from pixels. A side whose re-search finds nothing falls back to the crop and carries
`GEOMETRY_UNVERIFIED` with `GEOMETRY_CROP_DISAGREEMENT` beside it, so every boundary-dependent
category declines through the path that already existed.

It was earned on `real_scans/shadowed_photo.jpg`: a shadow across the lower card put that part of it
on the background side of the threshold, the outline stopped about 5mm inside the cut, and a crop
traced on the true edges changed the fitted apexes by **zero pixels**. Two things follow that are
worth keeping. A shape threshold cannot catch it -- correctly fitted angled photographs read up to
0.073 aspect deviation and that photograph reads 0.058, inside the band -- so do not reach for one.
And the harness could not see it either: `fixture_drift.crop_like_a_customer` returns the *fit's own
apexes*, so its "customer crop" can never correct the fit. Real photographs may now carry a
hand-traced crop in `<name>.crop.json` (uncommitted, like the photographs), which the harness
measures as a third path, and `--sloppy` perturbs each crop by 1-2mm per side to prove the re-search
does not pull a good fit off its edge.

The material mask is still the filled `detect_boundary` contour, so on a re-fitted side the mask and
the geometry disagree and `corners._corner_readable` declines those corners. That is the honest
outcome and it is deliberate: rebuilding the mask from the re-fitted lines would erase real corner
damage on that side.
```

Fill the two constant values in from Task 4's outcome, and correct the "5mm" and "0.058" figures if Step 1–3 measured differently.

- [ ] **Step 8: Commit**

```bash
git add AGENTS.md backend/zgrader/analysis/geometry.py frontend/public/methodology
git commit -m "Record what the crop-guided refit measured, and set its constants" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 9: Report**

State: the measured true edge, each acceptance criterion with its number, the constants you set and why, the corners outcome on the real photograph, what the methodology regeneration changed, the full-suite count and exit code, and anything you could not measure.
