# Corner Mask Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the corners category's card mask back on the card for cropped analyses, and stop corners
scoring a corner whose mask disagrees with that corner's own fitted edges.

**Architecture:**
- Fix a sign error in `preprocessing.rectify`'s crop-offset composition.
- Teach the drift harness to measure the cropped path that ships.
- Replace the whole-raster "1% missing" gate in `corners.py` with a per-corner structural check. The mask
  must agree with the fitted lines along each corner's straight sections, and any loss must be reachable
  from the cut.
- One unreadable corner, or no mask at all, makes the category decline with a new limitation code. There
  is no scored whitening-only path any more.

**Tech Stack:** Python 3.12, OpenCV, NumPy, pytest (Postgres-backed suite), Jinja/WeasyPrint reports,
Next.js i18n dictionaries (TypeScript).

**Spec:** `docs/superpowers/specs/2026-09-13-corner-mask-design.md`. Read it first; this plan argues from
it, and §1 holds the real-photo evidence.

## Global Constraints

- **Branch:** work on `corner-mask-design` (already exists and holds the spec). Never commit to `main`.
- **Never commit** anything under `backend/tests/fixtures/real_scans/`, nor the untracked
  `backend/tests/fixtures/*.png`. The repo is public and those are the operator's photographs. Stage
  files by explicit path, never `git add -A` or `git add .`.
- **Before any pytest run**, check what owns port 5432:
  `powershell -Command "Get-NetTCPConnection -LocalPort 5432 -State Listen | % { (Get-Process -Id $_.OwningProcess).ProcessName }"`.
  If it names `ssh`, 5432 is the **production** server's Postgres. The suite may still run there, but only
  against a database whose name ends in `_test` (conftest enforces this), and only one suite at a time.
  Never point `ZGRADER_DATABASE_URL` at it.
- **Never pipe pytest into `tail`/`head`**; that replaces pytest's exit code. Redirect to a temp file and
  read it:
  `OUT=$(mktemp); .venv/Scripts/python.exe -m pytest <args> > "$OUT" 2>&1; echo "exit=$?"; tail -30 "$OUT"`.
  All backend commands run from `backend/`.
- **Any change under `backend/zgrader/analysis/`** must end with `scripts/fixture_drift.py` showing no
  unintended drift. Intended drift is recorded with `--update` and committed as the reviewable statement.
- **New limitation code:** exactly `corners_boundary_unreadable`
  (`assessment.CORNERS_BOUNDARY_UNREADABLE`). It needs copy in `backend/zgrader/reports/strings.py` (en and
  es) and `frontend/lib/i18n/en.ts` + `es.ts`.
- **`corners_whitening_only` is no longer emitted, but its code and copy stay**, because stored results
  carry it and existing reports render it.
- **Constants and their values** (from spec §5.2), all in `corners.py`:
  - `CORNER_MAX_EDGE_INSET_MM = 0.3`
  - `CORNER_STRAIGHT_DEVIATION_MM = 0.3`
  - `CORNER_MAX_STRAIGHT_DEVIATION_FRACTION = 0.10`
  - `CORNER_MAX_VISIBILITY_VIOLATION = 0.05`
  - Reason codes: `"inset"`, `"straight"`, `"visibility"`.
- **Real damage must never be gated away:** `damage_corner_clipped` stays scored at about 1.59mm² excess.
- Commit messages end with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

## File map

| File | Responsibility | Tasks |
|---|---|---|
| `backend/zgrader/analysis/preprocessing.py` | the crop-offset sign in `rectify` | 1 |
| `backend/tests/test_geometry.py` | padded-canvas test that the cropped mask stays on the card | 1 |
| `backend/zgrader/analysis/fixture_metrics.py` | `measure_image(..., roi_quad=None)` | 2 |
| `backend/scripts/fixture_drift.py` | real-photo block prints the uncropped and cropped paths, plus a corners count | 2 |
| `backend/tests/test_fixture_drift.py` | test the harness can measure the cropped path | 2 |
| `backend/zgrader/analysis/corners.py` | `_corner_readable`, constants, decline path, whitening-only removal | 3, 4 |
| `backend/zgrader/analysis/assessment.py` | new code, removed confidence constants | 4 |
| `backend/zgrader/reports/strings.py`, `frontend/lib/i18n/en.ts`, `frontend/lib/i18n/es.ts` | copy | 4 |
| `backend/tests/test_corners.py`, `test_assessment.py`, `test_capture.py`, `test_recompute.py`, `test_regions.py` | tests that used the whitening-only path | 3, 4, 5 |
| `backend/tests/fixtures/generate_samples.py`, `backend/tests/fixtures/drift_baseline.json` | `capture_shadowed_corner` fixture | 5 |
| `backend/tests/test_corners_decline_end_to_end.py` (new) | declined corners through the pipeline and the PDF | 5 |
| `AGENTS.md`, `frontend/public/methodology/*` | invariants, characterised entries, regenerated figures | 6 |

---

### Task 1: Put the cropped mask back on the card

**Files:**
- Modify: `backend/zgrader/analysis/preprocessing.py` (the `shift` matrix inside `rectify`, currently lines
  533–545)
- Test: `backend/tests/test_geometry.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `preprocessing.rectify(image, w_mm, h_mm, roi_quad=...)` whose `.mask` sits on the card for any
  ROI origin. Later tasks rely on this.

- [ ] **Step 1: Write the failing test.** Add `corners` to the import at the top of
  `backend/tests/test_geometry.py`, so it reads
  `from zgrader.analysis import assessment, corners, geometry, preprocessing`. Then add after
  `test_a_bad_crop_no_longer_decides_where_the_card_is`:

```python
def test_a_crop_away_from_the_image_origin_keeps_the_mask_on_the_card():
    """The card mask is drawn in the crop's coordinates and warped through the
    homography composed with the crop offset. That offset was applied with the
    wrong sign, which put every cropped mask twice the crop origin away from
    the card -- and production always passes a crop.

    No fixture could show it on its own. Every synthetic card sits on an 8%
    margin and rectify widens the crop by 10%, so the crop origin clips to
    (0, 0) and the offset is zero whichever way round it is applied. The
    padding here is what puts the origin in the hundreds of pixels; remove it
    and this test passes against the broken sign too.
    """
    image = cv2.copyMakeBorder(
        build_fixture("pokemon_back"), 400, 0, 300, 0, cv2.BORDER_CONSTANT, value=(0, 0, 0)
    )
    uncropped = preprocessing.rectify(image, *POKEMON_MM)
    crop = np.array(uncropped.geometry["apexes"], dtype=np.float64)
    cropped = preprocessing.rectify(image, *POKEMON_MM, roi_quad=crop)

    assert cropped.geometry["method"] == "ransac"
    missing = float(np.mean(cropped.mask == 0))
    assert missing < 0.01, f"{missing:.1%} of the cropped raster reads as missing card"
    assert missing == pytest.approx(float(np.mean(uncropped.mask == 0)), abs=0.002)

    result = corners.measure_corners(
        cropped.image, px_per_mm=cropped.px_per_mm, mask=cropped.mask
    )
    assert result["measurements"]["material_measured"] is True
```

- [ ] **Step 2: Run it and watch it fail.** First do the 5432 check from Global Constraints, then:
  `OUT=$(mktemp); .venv/Scripts/python.exe -m pytest tests/test_geometry.py::test_a_crop_away_from_the_image_origin_keeps_the_mask_on_the_card -q > "$OUT" 2>&1; echo "exit=$?"; tail -30 "$OUT"`.
  Expected: **FAIL** on the `missing < 0.01` assertion, with a large percentage missing.

- [ ] **Step 3: Fix the sign.** In `rectify`, replace the comment and `shift` above `canonical_mask =
  cv2.warpPerspective(...)`:

```python
    canonical_mask = None
    if material is not None:
        # `matrix` maps *source-image* coordinates onto the canonical raster,
        # and `material` was drawn in *ROI* coordinates, so a mask pixel at q
        # sits at q + offset in the source image. The composition is therefore
        # matrix @ T(+offset).
        #
        # It was T(-offset) for a long time, which put every cropped mask twice
        # the ROI origin away from the card. Production always passes a crop,
        # so corners fell back to whitening on nearly every report. No fixture
        # showed it, because the synthetic cards' ROI origin clips to (0, 0) --
        # see test_a_crop_away_from_the_image_origin_keeps_the_mask_on_the_card.
        shift = np.array(
            [[1.0, 0.0, offset[0]], [0.0, 1.0, offset[1]], [0.0, 0.0, 1.0]], dtype="float64"
        )
```

  Leave the `cv2.warpPerspective(material, (matrix @ shift)...)` call and its `INTER_NEAREST` comment
  unchanged.

- [ ] **Step 4: Run the geometry tests and the drift test.**
  `OUT=$(mktemp); .venv/Scripts/python.exe -m pytest tests/test_geometry.py tests/test_fixture_drift.py -q > "$OUT" 2>&1; echo "exit=$?"; tail -30 "$OUT"`.
  Expected: **PASS**, with no drift. Synthetic ROI origins are (0, 0), so no fixture moves.

- [ ] **Step 5: Commit.**

```bash
git add backend/zgrader/analysis/preprocessing.py backend/tests/test_geometry.py
git commit -m "Compose the crop offset with the right sign so a cropped mask stays on the card

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Make the drift harness measure the cropped path

**Files:**
- Modify: `backend/zgrader/analysis/fixture_metrics.py` (`measure_image` signature and its `rectify` call)
- Modify: `backend/scripts/fixture_drift.py` (`measure_real_scans`, the real-photo printing in `main`)
- Test: `backend/tests/test_fixture_drift.py`

**Interfaces:**
- Consumes: Task 1's corrected `rectify`.
- Produces:
  - `fixture_metrics.measure_image(image, width_mm, height_mm, roi_quad: np.ndarray | None = None) -> dict[str, float]`
  - `fixture_drift.crop_like_a_customer(image: np.ndarray) -> np.ndarray` (4×2 float64 apexes)
  - `fixture_drift.measure_real_scans() -> dict[str, dict[str, dict[str, float]]]`, keyed
    `{stem: {"uncropped": metrics, "cropped": metrics}}`

- [ ] **Step 1: Write the failing test.** Append to `backend/tests/test_fixture_drift.py`. Add `import cv2`
  to its imports, and change the `from fixture_drift import (...)` block to also import
  `crop_like_a_customer`. Add `from zgrader.analysis.fixture_metrics import measure_image` beside the
  existing `tests.fixtures` import.

```python
def test_the_harness_can_measure_the_cropped_path():
    """Production always passes a crop, and the harness used to measure real
    photographs only without one -- so a bug confined to the cropped path,
    like the crop-offset sign that displaced every cropped mask, was invisible
    to the one tool meant to catch analysis regressions. Padded so the crop
    origin is not (0, 0); see test_geometry for why that matters."""
    image = cv2.copyMakeBorder(
        build_fixture("pokemon_back"), 400, 0, 300, 0, cv2.BORDER_CONSTANT, value=(0, 0, 0)
    )
    crop = crop_like_a_customer(image)
    assert crop.shape == (4, 2)

    metrics = measure_image(image, 63.0, 88.0, roi_quad=crop)
    assert metrics["geometry.fitted"] == 1.0
    assert "corners.raw_score" in metrics
```

- [ ] **Step 2: Run it and watch it fail.**
  `OUT=$(mktemp); .venv/Scripts/python.exe -m pytest tests/test_fixture_drift.py::test_the_harness_can_measure_the_cropped_path -q > "$OUT" 2>&1; echo "exit=$?"; tail -30 "$OUT"`.
  Expected: **FAIL** with `ImportError: cannot import name 'crop_like_a_customer'`.

- [ ] **Step 3: Add `roi_quad` to `measure_image`.** In `backend/zgrader/analysis/fixture_metrics.py`,
  change the signature and the `rectify` call. The comment above the call is rewritten because it
  currently says "No roi_quad".

```python
def measure_image(
    image: np.ndarray,
    width_mm: float,
    height_mm: float,
    roi_quad: np.ndarray | None = None,
) -> dict[str, float]:
    """Every number the four analysers produce for one card, flattened.

    Flat rather than nested so a diff can name exactly what moved --
    "corners.per_corner.top_left.whitening_score" is a useful failure message;
    "corners changed" is not.

    `roi_quad` is a customer's crop. Synthetic fixtures are measured without
    one, because their crop origin clips to (0, 0) and a cropped pass would
    prove nothing; real photographs are measured both ways, because the
    cropped path is the one that ships.
    """
    # The same entry point the pipeline uses, so the harness measures what
    # ships.
    rectified = preprocessing.rectify(image, width_mm, height_mm, roi_quad=roi_quad)
```

  Leave the rest of the function unchanged.

- [ ] **Step 4: Measure both paths in `fixture_drift.py`.** Add
  `from zgrader.analysis import preprocessing  # noqa: E402` beside the existing `fixture_metrics` import
  and `import numpy as np` beside `import cv2`. Then replace `measure_real_scans` with:

```python
def crop_like_a_customer(image: np.ndarray) -> np.ndarray:
    """The four points a customer's crop would carry: the card's own corners
    from an uncropped run -- fitted apexes when the fit held, the coarse quad
    when it fell back. rectify records either as `apexes`."""
    rectified = preprocessing.rectify(image, *_DEFAULT_CARD_MM)
    return np.array(rectified.geometry["apexes"], dtype=np.float64)


def measure_real_scans() -> dict[str, dict[str, dict[str, float]]]:
    """Measure any real photographs that have been dropped in, both without a
    crop and with one -- production always passes a crop, and a bug confined to
    that path was once invisible here because only the uncropped path was
    measured.

    Returns empty when the directory is absent or empty, which is the normal
    state for a fresh clone without git-LFS content pulled -- this must never
    be the reason the harness fails.
    """
    if not REAL_SCANS_DIR.is_dir():
        return {}
    results = {}
    for path in sorted(REAL_SCANS_DIR.iterdir()):
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
            continue
        image = cv2.imread(str(path))
        if image is None:
            print(f"  ! could not read {path.name}", file=sys.stderr)
            continue
        try:
            results[path.stem] = {
                "uncropped": measure_image(image, *_DEFAULT_CARD_MM),
                "cropped": measure_image(
                    image, *_DEFAULT_CARD_MM, roi_quad=crop_like_a_customer(image)
                ),
            }
        except Exception as exc:  # noqa: BLE001 -- one bad photo must not stop the run
            print(f"  ! {path.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
    return results
```

- [ ] **Step 5: Print both paths and a corners count.** In `main`, replace the whole `if real:` block
  (keep its existing "--" comment inside `_score`):

```python
    real = measure_real_scans()
    if real:
        print(f"\nreal photographs measured (not baselined): {len(real)}")
        for name, paths in real.items():
            for label, metrics in paths.items():
                # "--" where a category declined to score. The first real card that
                # produced an unmeasurable centering crashed this line with a
                # KeyError, because it assumed every category always yields a
                # number -- which is exactly the assumption the nullable score was
                # introduced to remove, still living in the reporting.
                def _score(key: str) -> str:
                    value = metrics.get(key)
                    return f"{value:5.2f}" if value is not None else "   --"

                tag = name if label == "uncropped" else "  (cropped)"
                print(
                    f"  {tag:28} cen {_score('centering.raw_score')}"
                    f"  cor {_score('corners.raw_score')}"
                    f"  edg {_score('edges.raw_score')}"
                    f"  sur {_score('surface.raw_score')}"
                    f"  ({metrics['px_per_mm']:.1f} px/mm)"
                )
        for label in ("uncropped", "cropped"):
            scored = sum("corners.raw_score" in paths[label] for paths in real.values())
            print(f"  corners scored, {label}: {scored}/{len(real)}")
```

- [ ] **Step 6: Run the drift tests.**
  `OUT=$(mktemp); .venv/Scripts/python.exe -m pytest tests/test_fixture_drift.py -q > "$OUT" 2>&1; echo "exit=$?"; tail -30 "$OUT"`.
  Expected: **PASS**, with no drift.

- [ ] **Step 7: Check the script runs.**
  `OUT=$(mktemp); .venv/Scripts/python.exe scripts/fixture_drift.py > "$OUT" 2>&1; echo "exit=$?"; tail -60 "$OUT"`.
  Expected: exit 0 and "no drift across 23 fixtures". If `real_scans/` holds photographs, each prints two
  lines followed by two "corners scored" lines. Most cropped lines now show a corners score instead of
  the uncropped path's "--". That's Task 1 at work: with the old sign, cropped corners fell back to
  whitening.

- [ ] **Step 8: Commit.**

```bash
git add backend/zgrader/analysis/fixture_metrics.py backend/scripts/fixture_drift.py backend/tests/test_fixture_drift.py
git commit -m "Measure real photographs on the cropped path too, since that is the one that ships

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: A per-corner boundary check

Adds the check as a pure function. Nothing calls it until Task 4, so this task changes no behaviour and a
reviewer can judge the check on its own.

**Files:**
- Modify: `backend/zgrader/analysis/corners.py`: new constants and functions, placed after
  `_edge_inset_px` and before `_material_loss`
- Test: `backend/tests/test_corners.py`

**Interfaces:**
- Consumes: `corners._STRAIGHT_EDGE_START_MM` (existing, 3.0).
- Produces: `corners._corner_readable(mask_crop: np.ndarray, px_per_mm: float, excess_mm2: float | None) -> str | None`.
  It returns `None` when the corner is readable, otherwise `"inset"`, `"straight"` or `"visibility"`.
  `mask_crop` is oriented like every corner crop: apex at `[0, 0]`, non-zero means card.

- [ ] **Step 1: Write the failing tests.** Add `import numpy as np` to the imports of
  `backend/tests/test_corners.py`, then add this section before `# --- Aggregation ---`:

```python
# --- Whether a corner's mask can be believed --------------------------------
#
# Hand-built masks rather than fixtures: each one isolates exactly one way a
# mask can disagree with the card's fitted lines. 20 px/mm over a 5mm window.

_PPM = 20.0
_SIZE = 100


def _rounded_corner(radius_mm: float = 1.5) -> np.ndarray:
    """A clean factory corner, oriented like every corner crop (apex at [0, 0])."""
    mask = np.full((_SIZE, _SIZE), 255, np.uint8)
    r = int(round(radius_mm * _PPM))
    yy, xx = np.mgrid[0:r, 0:r]
    mask[:r, :r][np.hypot(r - yy, r - xx) > r] = 0
    return mask


def test_a_clean_rounded_corner_is_readable():
    assert corners._corner_readable(_rounded_corner(), _PPM, 0.0) is None
    # Loss that is visible from the cut is what real wear looks like.
    assert corners._corner_readable(_rounded_corner(), _PPM, 0.5) is None


def test_a_bite_along_the_straight_edge_is_not_believed():
    """The failure behind 13_FrontSideAngle: the contour cut into an intact,
    cleanly rounded corner along its edge, and 7.72mm2 of "loss" zeroed it. A
    median of the edge inset cannot see a bite covering under half the section,
    which is why the fraction of deviating lines is checked separately."""
    mask = _rounded_corner()
    mask[70:82, :12] = 0  # 30% of the straight section, 0.6mm deep
    assert corners._corner_readable(mask, _PPM, 1.0) == "straight"


def test_a_line_with_no_material_counts_as_deviating():
    """_edge_inset_px drops a line with no material, which is right for a
    calibration and wrong here: an empty line is the most extreme deviation
    there is, not one to ignore."""
    mask = _rounded_corner()
    mask[70:76, :] = 0  # 15% of the straight section, no material at all
    assert corners._corner_readable(mask, _PPM, 1.0) == "straight"


def test_a_mask_sitting_inside_the_fitted_lines_is_not_believed():
    mask = _rounded_corner()
    mask[:, :10] = 0
    mask[:10, :] = 0  # 0.5mm inside both lines
    assert corners._corner_readable(mask, _PPM, 1.0) == "inset"


def test_loss_that_cannot_see_the_cut_is_not_believed_when_it_is_scored():
    """Real corner loss is reachable from the cut along a row or a column;
    misclassified speckle inside the card is not. Checked only when there is
    excess to score -- speckle that costs nothing need not decline anything."""
    mask = _rounded_corner()
    mask[40:51, 40:51] = 0
    assert corners._corner_readable(mask, _PPM, 0.5) == "visibility"
    assert corners._corner_readable(mask, _PPM, 0.0) is None
```

- [ ] **Step 2: Run them and watch them fail.**
  `OUT=$(mktemp); .venv/Scripts/python.exe -m pytest tests/test_corners.py -q -k "readable or believed or deviating" > "$OUT" 2>&1; echo "exit=$?"; tail -30 "$OUT"`.
  Expected: **FAIL** with `AttributeError: module 'zgrader.analysis.corners' has no attribute '_corner_readable'`.

- [ ] **Step 3: Implement.** In `backend/zgrader/analysis/corners.py`, directly after `_edge_inset_px`, add:

```python
# --- Whether a corner's mask can be believed ---------------------------------
#
# The mask is a filled threshold contour; the lines the raster is built from
# are RANSAC fits over the same contour, which reject outliers where the mask
# cannot. So glare, or a pale border against a pale backdrop, can break the
# mask while leaving the lines exactly right -- measured on 9 of 36 real
# photographs whose fit held. Each corner is therefore checked against its own
# fitted lines, in its own window, before its material loss is believed.
#
# The whole-raster check this replaces (1% of the raster missing) was wrong in
# both directions: it passed a 7.72mm2 bite out of an intact corner, because
# 0.21% of a whole card is small, and it failed cards whose hole was nowhere
# near a corner.
#
# REASONED, all four, and measured rather than picked. Across the real
# photographs the photo-level outcome is identical for straight-section
# thresholds 0.05-0.20 and visibility thresholds 0.05-0.10 -- a plateau, not a
# knife edge. They are still calibrated on 46 photographs of about ten cards.
#
# What this cannot do: a compact, rounded artefact -- a 2-3mm shadow over an
# intact corner -- is exactly the shape of real wear and passes. It catches
# artefacts that run along the straight edge, which is what every failure in
# the real set did. "Gated" is not "correct".

#: How far inside the fitted line the mask's boundary may sit, as a median over
#: a corner's straight sections, before the mask is describing something other
#: than the card's cut.
CORNER_MAX_EDGE_INSET_MM = 0.3

#: A straight-section line whose material starts this much deeper than the
#: section's median is deviating...
CORNER_STRAIGHT_DEVIATION_MM = 0.3

#: ...and more than this fraction of deviating lines is a bite along the edge.
#: A median alone cannot see a bite that covers under half the section.
CORNER_MAX_STRAIGHT_DEVIATION_FRACTION = 0.10

#: Fraction of missing pixels allowed to be unreachable from the cut along
#: their row or their column. Real corner loss is reachable from the cut;
#: misclassification speckle is not.
CORNER_MAX_VISIBILITY_VIOLATION = 0.05

#: Below this many missing pixels there is no shape to judge.
_MIN_VISIBILITY_PIXELS = 20


def _first_material_depths(lines: np.ndarray) -> np.ndarray:
    """Per line, the index of the first card pixel.

    A line with no material at all reports the full line length -- the deepest
    deviation possible -- rather than being dropped as _edge_inset_px drops it.
    That is right for a calibration and wrong here.
    """
    present = lines.any(axis=1)
    return np.where(present, np.argmax(lines, axis=1), lines.shape[1])


def _corner_readable(
    mask_crop: np.ndarray, px_per_mm: float, excess_mm2: float | None
) -> str | None:
    """None when this corner's mask can be believed, otherwise why not.

    `mask_crop` is oriented like every corner crop: the ideal apex at [0, 0],
    non-zero where there is card. The straight sections are the parts of both
    edges beyond _STRAIGHT_EDGE_START_MM, where the card's boundary must lie on
    the fitted line.
    """
    size = mask_crop.shape[0]
    card = mask_crop != 0
    start = min(size - 1, int(round(_STRAIGHT_EDGE_START_MM * px_per_mm)))
    rows = _first_material_depths(card[start:, :])
    cols = _first_material_depths(card[:, start:].T)
    median_rows, median_cols = float(np.median(rows)), float(np.median(cols))

    if max(median_rows, median_cols) / px_per_mm > CORNER_MAX_EDGE_INSET_MM:
        return "inset"

    tolerance = CORNER_STRAIGHT_DEVIATION_MM * px_per_mm
    deviating = max(
        float(np.mean(rows > median_rows + tolerance)),
        float(np.mean(cols > median_cols + tolerance)),
    )
    if deviating > CORNER_MAX_STRAIGHT_DEVIATION_FRACTION:
        return "straight"

    if excess_mm2 is not None and excess_mm2 > 0:
        missing = ~card
        total = int(missing.sum())
        if total > _MIN_VISIBILITY_PIXELS:
            visible = np.cumprod(missing, axis=1).astype(bool) | np.cumprod(
                missing, axis=0
            ).astype(bool)
            if (missing & ~visible).sum() / total > CORNER_MAX_VISIBILITY_VIOLATION:
                return "visibility"
    return None
```

- [ ] **Step 4: Run the new tests.** Same command as Step 2. Expected: **PASS** (5 tests).

- [ ] **Step 5: Run the drift test.**
  `OUT=$(mktemp); .venv/Scripts/python.exe -m pytest tests/test_fixture_drift.py tests/test_corners.py -q > "$OUT" 2>&1; echo "exit=$?"; tail -30 "$OUT"`.
  Expected: **PASS**, with no drift, since nothing calls the function yet.

- [ ] **Step 6: Commit.**

```bash
git add backend/zgrader/analysis/corners.py backend/tests/test_corners.py
git commit -m "Add a per-corner check that the mask agrees with the corner's own fitted lines

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Decline an unreadable corner instead of scoring it

One behaviour change and everything that has to move with it: the decline path, the new code and its
copy, and the tests that relied on the whitening-only path. They break together, so they land together.

**Files:**
- Modify: `backend/zgrader/analysis/assessment.py` (codes near lines 44–47 and 69–84; confidence constants
  near lines 104–117)
- Modify: `backend/zgrader/analysis/corners.py`:
  - delete `CORNERS_WHITENING_ONLY_FLAG` (lines 74–82) and `MAX_MASK_MISSING_FRACTION` with its comment
    (lines 116–137)
  - add `_boundary_flag`
  - rewrite `measure_corners`
- Modify: `backend/zgrader/reports/strings.py` (en block near line 171, es block near line 237)
- Modify: `frontend/lib/i18n/en.ts` (near line 156), `frontend/lib/i18n/es.ts` (near line 147)
- Modify tests: `backend/tests/test_corners.py`, `test_assessment.py`, `test_capture.py`,
  `test_recompute.py`, `test_regions.py`

**Interfaces:**
- Consumes: `corners._corner_readable` (Task 3).
- Produces:
  - `assessment.CORNERS_BOUNDARY_UNREADABLE == "corners_boundary_unreadable"`, listed in
    `assessment.ALL_LIMITATION_CODES`.
  - `measure_corners` results gain:
    - `measurements["unreadable_corners"]: list[str]` (sorted corner names)
    - `measurements["per_corner"][name]["boundary_check"]: str | None`
  - On decline:
    - `raw_score is None`
    - `measurements["assessment"]["state"] == "unmeasurable"`, with `CORNERS_BOUNDARY_UNREADABLE` in its
      limitations
    - `flags["reason"]` names the unreadable corners with underscores replaced by spaces (e.g.
      "bottom left")

- [ ] **Step 1: Write the failing tests in `test_corners.py`.**
  1. Replace `test_without_a_mask_the_category_says_it_measured_only_whitening` entirely with:

```python
def test_without_a_mask_the_category_declines():
    """There is no scored whitening-only path any more. Whitening sampled with
    no mask measures whatever sits behind the rounded corner -- on a real
    photograph, the desk -- and real photographs read lightness "rises" of -40
    to -150 there, which clip to zero and score a clean corner. A reading with
    nothing behind it declines instead."""
    card = _rectified()
    result = corners.measure_corners(card.image, px_per_mm=card.px_per_mm, mask=None)

    assert result["raw_score"] is None
    block = result["measurements"]["assessment"]
    assert block["state"] == assessment.UNMEASURABLE
    assert assessment.CORNERS_BOUNDARY_UNREADABLE in block["limitations"]
    assert assessment.CORNERS_WHITENING_ONLY not in block["limitations"]
    assert result["flags"]["lower_confidence"] is True
```

  2. Replace the body of `test_backing_is_excluded_from_the_tip_colour_sample` (keep its docstring) with:

```python
    card = _rectified(clip_top_left_corner=True)
    size = corners._window_px(card.image, card.px_per_mm)
    crop = corners.corner_crops(card.image, size=size)["top_left"]
    mask_crop = corners.corner_crops(card.mask, size=size)["top_left"]

    with_mask = corners._whitening(crop, mask_crop, card.px_per_mm)["lightness_rise"]
    without = corners._whitening(crop, None, card.px_per_mm)["lightness_rise"]
    assert with_mask > without, (
        "excluding the backing should stop it dragging the tip's lightness down"
    )
```

  3. Replace `test_a_pale_border_costs_less_confidence_than_it_used_to` entirely with:

```python
def test_a_pale_border_lowers_confidence_but_material_is_still_measured():
    """A pale border disables the colour half of the corner reading, not the
    material half, so it costs confidence without costing the measurement."""
    pale = preprocessing.rectify(build_fixture("white_border_clean"), *card_size_mm("white_border_clean"))
    plain = preprocessing.rectify(build_fixture("centering_perfect"), *card_size_mm("centering_perfect"))
    pale_result = corners.measure_corners(pale.image, px_per_mm=pale.px_per_mm, mask=pale.mask)
    plain_result = corners.measure_corners(plain.image, px_per_mm=plain.px_per_mm, mask=plain.mask)

    pale_block = pale_result["measurements"]["assessment"]
    assert assessment.CORNERS_PALE_BORDER in pale_block["limitations"]
    assert pale_result["measurements"]["material_measured"] is True
    assert pale_block["confidence"] < plain_result["measurements"]["assessment"]["confidence"]
```

  4. Add to the "Whether a corner's mask can be believed" section (add
     `from zgrader.models import AnalysisCategory` and change the analysis import to
     `from zgrader.analysis import assessment, corners, preprocessing, regions, scoring`):

```python
def test_one_unreadable_corner_declines_the_whole_category():
    """Corners are scored worst-anchored, so a score from three corners cannot
    know it skipped the worst one. The bite here runs along the bottom edge of
    the bottom-left corner, clear of the factory rounding -- the shape of the
    contour failure seen on real photographs."""
    card = _rectified()
    ppm = card.px_per_mm
    mask = card.mask.copy()
    h = mask.shape[0]
    mask[h - int(round(0.8 * ppm)) :, int(round(3.2 * ppm)) : int(round(3.8 * ppm))] = 0

    result = corners.measure_corners(card.image, px_per_mm=ppm, mask=mask)

    assert result["raw_score"] is None
    assert result["measurements"]["unreadable_corners"] == ["bottom_left"]
    assert result["measurements"]["per_corner"]["bottom_left"]["boundary_check"] == "straight"
    assert (
        assessment.CORNERS_BOUNDARY_UNREADABLE
        in result["measurements"]["assessment"]["limitations"]
    )
    assert "bottom left" in result["flags"]["reason"]
    assert regions.build_regions(
        AnalysisCategory.corners, card.image.shape[:2], ppm, "en", result, None
    ) == []


def test_real_damage_is_measured_not_gated_away():
    """The check exists to refuse a mask that is wrong, never to refuse damage.
    A clipped corner is exactly the loss corners exists to report."""
    card = _rectified(clip_top_left_corner=True)
    result = corners.measure_corners(card.image, px_per_mm=card.px_per_mm, mask=card.mask)

    top_left = result["measurements"]["per_corner"]["top_left"]
    assert top_left["boundary_check"] is None
    assert top_left["excess_area_mm2"] == pytest.approx(1.59, abs=0.3)
    assert result["raw_score"] is not None
    assert result["measurements"]["unreadable_corners"] == []
```

- [ ] **Step 2: Rewrite the whitening-only callers in the other test files.**
  1. **`backend/tests/test_assessment.py`.** Replace `_analyse` with:

```python
def _analyse(name: str) -> dict:
    """Every category's assessment block for one catalogue fixture.

    Corners goes through rectify, as the pipeline does: it needs the card mask,
    and without one it declines rather than scoring on whitening alone.
    """
    image = build_fixture(name)
    card, _info = preprocessing.locate_and_deskew(image)
    px_per_mm = scale.px_per_mm(card.shape[:2], *card_size_mm(name))
    rectified = preprocessing.rectify(image, *card_size_mm(name))
    surface_result, _mask = surface.measure_surface(card, px_per_mm=px_per_mm)
    return {
        "centering": centering.measure_centering(card, px_per_mm)["measurements"]["assessment"],
        "corners": corners.measure_corners(
            rectified.image, px_per_mm=rectified.px_per_mm, mask=rectified.mask
        )["measurements"]["assessment"],
        "edges": edges.measure_edges(card)["measurements"]["assessment"],
        "surface": surface_result["measurements"]["assessment"],
    }
```

     Then replace `test_corners_always_admit_that_material_loss_is_not_measured` with:

```python
def test_corners_on_the_shipped_path_measure_material():
    """The caveat this replaced was true of a code path that no longer scores:
    corners without a mask now declines rather than reporting whitening alone."""
    block = _analyse("pokemon_back")["corners"]
    assert block["state"] == assessment.MEASURED
    assert assessment.CORNERS_WHITENING_ONLY not in block["limitations"]
```

  2. **`backend/tests/test_capture.py`.** Add a helper after `_card`:

```python
def _rectified_card(name: str):
    """Through rectify, as the pipeline does. Corners needs the card mask;
    without one it declines rather than scoring whitening alone."""
    return preprocessing.rectify(build_fixture(name), *card_size_mm(name))


def _measure_at(module, px_per_mm: float) -> dict:
    if module is corners:
        card = _rectified_card("pokemon_front")
        return corners.measure_corners(card.image, px_per_mm=px_per_mm, mask=card.mask)
    card, _ = _card("pokemon_front")
    return edges.measure_edges(card, px_per_mm=px_per_mm)
```

     Replace `test_an_absent_scale_makes_no_claim` with:

```python
def test_an_absent_scale_makes_no_capture_claim():
    """A caller that supplies no px_per_mm gets no guess about the capture.
    Corners can no longer score at all without a scale -- material loss is
    measured in mm^2 -- but it must still not claim anything about resolution."""
    card, _ = _card("pokemon_front")
    result = corners.measure_corners(card)
    limitations = result["measurements"]["assessment"]["limitations"]
    assert assessment.CAPTURE_MODEST_RESOLUTION not in limitations
    assert assessment.CAPTURE_TOO_LOW_RESOLUTION not in limitations
```

     In `test_a_modest_capture_still_scores_but_at_lower_confidence`, delete these three lines:

```python
    card, _ = _card("pokemon_front")
    measure = module.measure_corners if module is corners else module.measure_edges
```

     and

```python
    modest = measure(card, px_per_mm=24.0)
    comfortable = measure(card, px_per_mm=26.0)
```

     Put `modest = _measure_at(module, 24.0)` and `comfortable = _measure_at(module, 26.0)` in their place,
     keeping the long comment between them. In `test_the_penalty_compounds_with_an_existing_limitation`,
     replace its first three code lines with:

```python
    card = _rectified_card("white_border_clean")
    pale_only = corners.measure_corners(card.image, px_per_mm=COMFORTABLE, mask=card.mask)
    pale_and_small = corners.measure_corners(card.image, px_per_mm=MODEST, mask=card.mask)
```

     Leave `test_a_capture_too_small_to_measure_is_not_scored` alone. The resolution gate runs before the
     boundary decline, so its `limitations == [CAPTURE_TOO_LOW_RESOLUTION]` assertion still holds.
  3. **`backend/tests/test_recompute.py`.** In the `analyzed_side` fixture:
     - after `ppm = ...`, add `rectified = preprocessing.rectify(preprocessing.load_image(path), 63.0, 88.0)`
     - replace the corners entry with
       `AnalysisCategory.corners: (corners.measure_corners(rectified.image, px_per_mm=rectified.px_per_mm, mask=rectified.mask), None),`
     - replace the regions loop with:

```python
    # Corners was measured on the rectified raster, so its boxes are
    # normalised against that raster's shape rather than the deskewed one.
    shapes = {AnalysisCategory.corners: rectified.image.shape[:2]}
    for category, (result, extra) in built.items():
        result["measurements"]["regions"] = regions.build_regions(
            category, shapes.get(category, card.shape[:2]), ppm, "en", result, extra
        )
```

  4. **`backend/tests/test_regions.py`.** Add after `_deskewed`:

```python
def _measured_corners(**kwargs):
    """Corners through rectify, as the pipeline does -- it needs the card mask,
    and without one it declines and draws nothing."""
    rectified = preprocessing.rectify(make_card_scan(63.0, 88.0, **kwargs), 63.0, 88.0)
    result = corners.measure_corners(
        rectified.image, px_per_mm=rectified.px_per_mm, mask=rectified.mask
    )
    return rectified.image, result
```

     In `test_pristine_corners_are_all_ok_with_no_notes`, replace
     `card = _deskewed()` + `result = corners.measure_corners(card)` with
     `card, result = _measured_corners()`. In `test_whitened_corner_produces_flag_with_note` and
     `test_whitened_corner_note_is_localized_for_spanish`, replace the same two lines with
     `card, result = _measured_corners(whiten_top_left_corner=True)`.

- [ ] **Step 3: Run the touched tests and watch them fail.**
  `OUT=$(mktemp); .venv/Scripts/python.exe -m pytest tests/test_corners.py tests/test_assessment.py tests/test_capture.py tests/test_recompute.py tests/test_regions.py -q > "$OUT" 2>&1; echo "exit=$?"; tail -40 "$OUT"`.
  Expected: **FAIL**. `test_without_a_mask_the_category_declines`,
  `test_one_unreadable_corner_declines_the_whole_category` and
  `test_every_limitation_code_has_copy_in_both_languages` fail on the missing `CORNERS_BOUNDARY_UNREADABLE`
  / `unreadable_corners`.

- [ ] **Step 4: Add the code and retire the dead confidence constants in `assessment.py`.**
  1. After `CORNERS_PALE_BORDER = "corners_pale_border"`, add:

```python
#: A corner's mask disagrees with that corner's fitted lines -- glare, a finger,
#: a background close in colour to the border -- or there is no mask at all, so
#: corners declines rather than scoring against the wrong outline.
CORNERS_BOUNDARY_UNREADABLE = "corners_boundary_unreadable"
```

  2. Change the comment above `CORNERS_WHITENING_ONLY` to
     `#: No longer emitted. Stored results still carry it and reports still render it, so its copy stays.`
  3. Add `CORNERS_BOUNDARY_UNREADABLE,` to `ALL_LIMITATION_CODES` directly after `CORNERS_PALE_BORDER,`.
  4. Delete `CONFIDENCE_CORNERS_WHITENING_ONLY` and `CONFIDENCE_CORNERS_PALE_BORDER`, together with the
     comment lines directly above each. Keep `CONFIDENCE_CORNERS_PALE_BORDER_WITH_MATERIAL`.
  5. Confirm nothing else references them:
     `grep -rn "CONFIDENCE_CORNERS_WHITENING_ONLY\|CONFIDENCE_CORNERS_PALE_BORDER\b\|CORNERS_WHITENING_ONLY_FLAG\|MAX_MASK_MISSING_FRACTION" --include=*.py .`
     should print nothing once Step 5 is done.

- [ ] **Step 5: Rewrite `corners.py`'s decline path.**
  1. Delete `CORNERS_WHITENING_ONLY_FLAG` (the dict and its assignment).
  2. Delete `MAX_MASK_MISSING_FRACTION` and the long comment above it.
  3. Add this function after `_corner_readable`:

```python
def _boundary_flag(unreadable: list[str]) -> dict:
    where = (
        "at the "
        + ", ".join(name.replace("_", " ") for name in unreadable)
        + (" corners" if len(unreadable) > 1 else " corner")
        if unreadable
        else "at the corners"
    )
    return {
        "lower_confidence": True,
        "reason": (
            f"The card's outline could not be traced reliably {where} in this photo -- "
            "usually glare on the corner, a finger over it, or a background close in "
            "colour to the card's border -- so corners were not scored rather than "
            "scored against the wrong outline."
        ),
    }
```

  4. Replace `measure_corners` entirely with:

```python
def measure_corners(
    card_image: np.ndarray,
    corner_fraction: float | None = None,
    px_per_mm: float | None = None,
    mask: np.ndarray | None = None,
) -> dict:
    """Assess all four corners.

    `mask` is the canonical card mask from preprocessing.rectify -- the same
    raster as `card_image`, non-zero where there is card. Material loss is
    measured against it, and each corner is believed only where the mask agrees
    with that corner's own fitted lines (see _corner_readable). One unreadable
    corner declines the category: corners are scored worst-anchored, so a score
    from three corners cannot know it skipped the worst one.

    Without a mask or a scale there is nothing to measure against, and the
    category declines. It used to fall back to whitening alone, but with no mask
    the rounded corner is backdrop, and real photographs read lightness "rises"
    of -40 to -150 there -- clipped to zero, scored as a clean corner.
    """
    size = _window_px(card_image, px_per_mm)
    crops = corner_crops(card_image, size=size, corner_fraction=corner_fraction)
    mask_usable = mask is not None and mask.shape[:2] == card_image.shape[:2]
    # A diagnostic only. It gates nothing any more -- see _corner_readable.
    mask_missing = float(np.mean(mask == 0)) if mask_usable else 1.0

    mask_crops = (
        corner_crops(mask, size=size, corner_fraction=corner_fraction) if mask_usable else {}
    )
    can_measure_material = bool(mask_crops) and px_per_mm is not None and px_per_mm > 0

    per_corner: dict[str, dict] = {}
    for name, crop in crops.items():
        mask_crop = mask_crops.get(name)
        info = dict(_whitening(crop, mask_crop, px_per_mm))
        excess = None
        if can_measure_material:
            info.update(_material_loss(mask_crop, px_per_mm))
            excess = info["excess_area_mm2"]
        # Still computed when the category declines: these are the diagnostics
        # the drift harness tracks and a later retune gets compared against.
        info["combined_score"] = round(
            scoring.corner_score(excess, info["lightness_rise"], info["chroma_loss"]), 2
        )
        info["material_measured"] = can_measure_material
        info["boundary_check"] = (
            _corner_readable(mask_crop, px_per_mm, excess) if can_measure_material else None
        )
        per_corner[name] = info

    scores = [c["combined_score"] for c in per_corner.values()]
    worst_corner = min(per_corner, key=lambda k: per_corner[k]["combined_score"])
    unreadable = sorted(n for n, c in per_corner.items() if c["boundary_check"] is not None)

    # A pale border has almost no chroma to lose, so the whitening channel is
    # weak there. It is a caveat on one of two channels, because material loss
    # does not care what colour the border is.
    mean_reference_chroma = float(np.mean([c["reference_chroma"] for c in per_corner.values()]))
    pale = mean_reference_chroma < assessment.PALE_BORDER_CHROMA

    capture_code, too_low_resolution = capture.resolution_limitation(px_per_mm)

    measurements = {
        "per_corner": per_corner,
        "worst_corner": worst_corner,
        # Both the physical size (for a customer) and the pixel size (so the
        # annotator and the region boxes draw exactly the window that was
        # measured -- they each used to derive their own from a fraction, which
        # is how an overlay silently stops matching its measurement).
        "corner_window_mm": round(size / px_per_mm, 2) if px_per_mm else None,
        "corner_window_px": size,
        "mean_reference_chroma": round(mean_reference_chroma, 1),
        "material_measured": can_measure_material,
        "mask_missing_fraction": round(mask_missing, 5),
        "unreadable_corners": unreadable,
    }

    if too_low_resolution:
        measurements["assessment"] = assessment.unmeasurable((capture_code,)).as_dict()
        return {
            "category": CATEGORY,
            "raw_score": None,
            "measurements": measurements,
            "flags": {
                "lower_confidence": True,
                "reason": (
                    "The card occupies too few pixels in this photo for corner "
                    "wear to be visible at all, so corners were not scored. A "
                    "closer or higher-resolution photo would let this be "
                    "measured."
                ),
            },
        }

    if not can_measure_material or unreadable:
        codes = (assessment.CORNERS_BOUNDARY_UNREADABLE,) + (
            (capture_code,) if capture_code is not None else ()
        )
        measurements["assessment"] = assessment.unmeasurable(codes).as_dict()
        return {
            "category": CATEGORY,
            "raw_score": None,
            "measurements": measurements,
            "flags": _boundary_flag(unreadable),
        }

    raw_score = round(scoring.corners_category_score(scores), 2)
    limitations: list[str] = []
    confidence = assessment.CONFIDENCE_CORNERS
    if pale:
        limitations.append(assessment.CORNERS_PALE_BORDER)
        confidence = min(confidence, assessment.CONFIDENCE_CORNERS_PALE_BORDER_WITH_MATERIAL)
    if capture_code is not None:
        limitations.append(capture_code)
        confidence *= assessment.CONFIDENCE_MODEST_RESOLUTION_FACTOR

    measurements["assessment"] = assessment.measured(
        raw_score, confidence, tuple(limitations)
    ).as_dict()
    return {
        "category": CATEGORY,
        "raw_score": raw_score,
        "measurements": measurements,
        "flags": {},
    }
```

- [ ] **Step 6: Add the copy.**
  1. **`backend/zgrader/reports/strings.py`.** After the en `"corners_pale_border": (...)` entry, add:

```python
        "corners_boundary_unreadable": (
            "The card's outline could not be traced reliably at one or more corners in this "
            "photo -- usually glare on the corner, a finger over it, or a background close in "
            "colour to the card's border -- so corners were not scored rather than scored "
            "against the wrong outline. A photo on a plain surface that contrasts with the "
            "border, without glare on the corners, would let them be measured."
        ),
```

     After the es `"corners_pale_border": (...)` entry, add:

```python
        "corners_boundary_unreadable": (
            "No se pudo trazar con fiabilidad el contorno de la carta en una o más esquinas de "
            "esta foto (normalmente por un reflejo en la esquina, un dedo encima o un fondo de "
            "color parecido al borde de la carta), así que las esquinas no se puntuaron en lugar "
            "de puntuarse contra un contorno equivocado. Una foto sobre una superficie lisa que "
            "contraste con el borde, sin reflejos en las esquinas, permitiría medirlas."
        ),
```

  2. **`frontend/lib/i18n/en.ts`.** After the `corners_pale_border:` entry in `limitation`, add:

```ts
      // Leads with retaking the photo, not re-cropping: a crop does not repair
      // these outlines (measured -- cropped and uncropped agreed on 34 of 35).
      corners_boundary_unreadable:
        "The card's outline couldn't be traced reliably at a corner — glare, a finger, or a background too close in colour to the border — so corners weren't scored. A photo on a plain, contrasting surface without glare on the corners would let them be measured.",
```

     Add `// No longer emitted; stored results still carry it.` on the line above `corners_whitening_only:`.
  3. **`frontend/lib/i18n/es.ts`.** After the `corners_pale_border:` entry, add:

```ts
      corners_boundary_unreadable:
        "No se pudo trazar bien el contorno en alguna esquina (un reflejo, un dedo o un fondo de color parecido al borde), así que las esquinas no se puntuaron. Una foto sobre una superficie lisa que contraste, sin reflejos en las esquinas, permitiría medirlas.",
```

- [ ] **Step 7: Run the touched tests.** Same command as Step 3. Expected: **PASS**.

- [ ] **Step 8: Run the drift test and the wider analysis tests.**
  `OUT=$(mktemp); .venv/Scripts/python.exe -m pytest tests/test_fixture_drift.py tests/test_geometry.py tests/test_geometry_disqualifies.py tests/test_public_share.py tests/test_methodology_figures.py tests/test_watcher.py tests/test_edges.py tests/test_centering.py tests/test_surface.py -q > "$OUT" 2>&1; echo "exit=$?"; tail -40 "$OUT"`.
  Expected: **PASS**, with **no drift**. Every synthetic corner is readable (measured during planning), so
  the per-corner metrics, scores and confidences don't change.
  - If `test_no_metric_drift` fails on `corners.*`: stop. It means a synthetic corner is now declined or
    scored differently, which the plan says cannot happen. Report the fixture and metric; don't
    `--update`.
  - If `test_public_payload_key_allowlist` fails, the projection has started passing a nested block
    through. The new keys are not for strangers: exclude them in `schemas/public_report.py`.

- [ ] **Step 9: Frontend type check.** From `frontend/`, run `npx tsc --noEmit`. Expected: exit 0. A
  missing `es.ts` key is a type error here.

- [ ] **Step 10: Commit.**

```bash
git add backend/zgrader/analysis/assessment.py backend/zgrader/analysis/corners.py backend/zgrader/reports/strings.py frontend/lib/i18n/en.ts frontend/lib/i18n/es.ts backend/tests/test_corners.py backend/tests/test_assessment.py backend/tests/test_capture.py backend/tests/test_recompute.py backend/tests/test_regions.py
git commit -m "Decline corners when a corner's mask disagrees with its fitted lines

Replaces the whole-raster 1% gate, which passed a local bite out of an
intact corner and failed cards whose hole was nowhere near one, and removes
the whitening-only fallback, which sampled the backdrop in the rounded
corner and scored it as clean.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: A fixture the drift baseline can hold, and the pipeline end to end

**Files:**
- Modify: `backend/tests/fixtures/generate_samples.py`:
  - add constants after `_CORNER_RADIUS_MM`
  - add a `make_card_scan` keyword below the divider, applied just before `_round_corners`
  - add a `FIXTURES` entry
- Modify: `backend/tests/fixtures/drift_baseline.json` (via `--update`)
- Test: `backend/tests/test_corners.py`
- Create: `backend/tests/test_corners_decline_end_to_end.py`

**Interfaces:**
- Consumes: Task 4's decline path and code.
- Produces: fixture `capture_shadowed_corner`; `make_card_scan(..., shadow_bottom_left_corner: bool = False)`.

- [ ] **Step 1: Write the failing tests.** Append to `backend/tests/test_corners.py`:

```python
def test_a_shadowed_corner_is_declined_not_scored_as_damage():
    """The regression the drift baseline could not otherwise hold -- every
    other synthetic fixture fits its mask cleanly.

    A soft shadow darkens an intact bottom-left corner until its border falls
    below the threshold separating card from backing: the mechanism behind
    13_FrontSideAngle, where a border indistinguishable from the backdrop let
    the contour bite 7.72mm2 out of a corner that was not damaged. The old
    whole-raster gate passed this card and scored the bite as lost material.
    """
    name = "capture_shadowed_corner"
    card = preprocessing.rectify(build_fixture(name), *card_size_mm(name))
    assert float(np.mean(card.mask == 0)) < 0.01, "fixture no longer passes the old global gate"

    result = corners.measure_corners(card.image, px_per_mm=card.px_per_mm, mask=card.mask)
    bottom_left = result["measurements"]["per_corner"]["bottom_left"]

    assert bottom_left["excess_area_mm2"] > 1.0, "fixture no longer invents loss at the corner"
    assert bottom_left["boundary_check"] is not None
    assert result["raw_score"] is None
```

  Create `backend/tests/test_corners_decline_end_to_end.py`:

```python
"""A declined corners category must reach the combined row and the PDF.

Corners has declined before -- on a capture too small to show wear -- but
rarely. It now declines on about a third of real photographs, which makes it
the most frequent decline path in the pipeline, and AGENTS.md records that
every time a category gained the ability to decline, something downstream
assumed it could not. This goes through run_dev_trigger, the whole pipeline
including the report, rather than trusting each piece separately.
"""

from pathlib import Path

import cv2
from pypdf import PdfReader

from tests.fixtures.generate_samples import build_fixture
from zgrader.analysis import assessment
from zgrader.dev_trigger import run_dev_trigger
from zgrader.models import AnalysisCategory, AnalysisResult, AnalysisSide, Submission


def test_a_declined_corners_category_reaches_the_report(db_session, tmp_path):
    front = tmp_path / "shadowed_front.png"
    cv2.imwrite(str(front), build_fixture("capture_shadowed_corner"))

    result = run_dev_trigger(
        front_path=str(front),
        back_path=None,
        game="Pokemon",
        card_name="Shadowed Corner",
        user_email="shadowed@example.com",
        submission_code="SUB-SHADOW1",
    )

    assert result["status"] == "draft_ready"
    submission = db_session.query(Submission).filter_by(submission_code="SUB-SHADOW1").one()
    rows = {
        (row.side, row.category): row
        for row in db_session.query(AnalysisResult).filter_by(submission_id=submission.id)
    }
    front_corners = rows[(AnalysisSide.front, AnalysisCategory.corners)]
    combined_corners = rows[(AnalysisSide.combined, AnalysisCategory.corners)]

    assert front_corners.raw_score is None
    assert (
        assessment.CORNERS_BOUNDARY_UNREADABLE
        in front_corners.measurements["assessment"]["limitations"]
    )
    assert combined_corners.raw_score is None

    pdf_path = Path(result["report_pdf_path"])
    assert pdf_path.exists()
    text = " ".join(
        " ".join(page.extract_text().split()) for page in PdfReader(str(pdf_path)).pages
    )
    assert "Not measurable" in text
    assert "wrong outline" in text
```

  Check the model import before running: `AnalysisResult`, `AnalysisSide`, `AnalysisCategory` and
  `Submission` must all be importable from `zgrader.models`. `grep -n "AnalysisSide" backend/zgrader/models/__init__.py`
  should print a line. If `AnalysisSide` isn't re-exported, import it from `zgrader.models.analysis_result`.

- [ ] **Step 2: Run them and watch them fail.**
  `OUT=$(mktemp); .venv/Scripts/python.exe -m pytest tests/test_corners.py::test_a_shadowed_corner_is_declined_not_scored_as_damage tests/test_corners_decline_end_to_end.py -q > "$OUT" 2>&1; echo "exit=$?"; tail -30 "$OUT"`.
  Expected: **FAIL** with `KeyError: 'Unknown fixture: capture_shadowed_corner'`.

- [ ] **Step 3: Add the fixture.**
  1. In `backend/tests/fixtures/generate_samples.py`, after `_CORNER_RADIUS_MM = 1.5`, add:

```python
#: A soft shadow over one intact corner, for `capture_shadowed_corner`. Radius
#: and floor were settled against the shipped pipeline rather than picked: the
#: old whole-raster mask gate passes this card (0.36% missing) while its
#: contour invents about 10.8mm^2 of loss at the corner, and every neighbouring
#: setting (radius 4.0-5.0mm, floor 0.1-0.2) is declined by the per-corner
#: check too -- so the fixture sits inside that region, not on its edge.
_CORNER_SHADOW_RADIUS_MM = 4.5
_CORNER_SHADOW_FLOOR = 0.15
```

  2. In `make_card_scan`'s signature, add after `scale: float = 1.0,`:

```python
    shadow_bottom_left_corner: bool = False,
```

  3. Directly before the `# Place on a dark scanner-backing canvas with a comfortable margin.` comment,
     add:

```python
    if shadow_bottom_left_corner:
        # Darkens an intact corner until its border falls below the threshold
        # that separates card from backing -- a border indistinguishable from
        # the backdrop at one corner, which is how a real photograph's contour
        # came to bite an undamaged corner. Applied before the die-cut rounding
        # so the corner is shaped exactly as every other fixture's.
        px_per_mm = card_h / height_mm
        yy, xx = np.mgrid[0:card_h, 0:card_w]
        distance_mm = np.hypot(yy - (card_h - 1), xx) / px_per_mm
        falloff = 1.0 - (1.0 - _CORNER_SHADOW_FLOOR) * np.exp(
            -((distance_mm / _CORNER_SHADOW_RADIUS_MM) ** 2)
        )
        card = np.clip(card.astype(np.float64) * falloff[..., None], 0, 255).astype(np.uint8)
```

  4. In `FIXTURES`, add to the `# --- deliberately bad captures ---` group, after `capture_noisy`:

```python
    (
        # An intact corner the card mask cannot be believed at. Declined, never
        # scored as damage -- see test_a_shadowed_corner_is_declined_not_scored_as_damage.
        "capture_shadowed_corner",
        _POKEMON,
        dict(shadow_bottom_left_corner=True),
    ),
```

- [ ] **Step 4: Run the two tests.** Same command as Step 2. Expected: **PASS**. The end-to-end test
  renders a PDF, so it needs Pango. If it fails on a Pango/`OSError` import, see AGENTS.md "WeasyPrint on
  Windows" and fix the environment, not the test.

- [ ] **Step 5: Record the new fixture in the baseline.**
  `OUT=$(mktemp); .venv/Scripts/python.exe scripts/fixture_drift.py > "$OUT" 2>&1; echo "exit=$?"; tail -40 "$OUT"`.
  Expected: exit 1, reporting drift in exactly one fixture, `capture_shadowed_corner`, as
  `+ <entire fixture>`. If **any other fixture** appears, stop and report it. Otherwise:
  `.venv/Scripts/python.exe scripts/fixture_drift.py --update`, then
  `git diff --stat backend/tests/fixtures/drift_baseline.json`. The diff should add one fixture block and
  change nothing else. Check with `git diff backend/tests/fixtures/drift_baseline.json | grep "^-" | grep -v "^---"`,
  which should print nothing.

- [ ] **Step 6: Run the drift tests.**
  `OUT=$(mktemp); .venv/Scripts/python.exe -m pytest tests/test_fixture_drift.py -q > "$OUT" 2>&1; echo "exit=$?"; tail -20 "$OUT"`.
  Expected: **PASS**.

- [ ] **Step 7: Commit.**

```bash
git add backend/tests/fixtures/generate_samples.py backend/tests/fixtures/drift_baseline.json backend/tests/test_corners.py backend/tests/test_corners_decline_end_to_end.py
git commit -m "Add a shadowed-corner fixture and carry a declined corners category through the report

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Verify on real photographs, regenerate the figures, record the invariants

**Files:**
- Modify: `AGENTS.md`
- Modify (regenerated): `frontend/public/methodology/*.jpg`, if any change

- [ ] **Step 1: Check the real-photo block against the spec.** `real_scans/` is untracked. If it's empty,
  **ask the operator for the photographs**; don't skip this step.
  `OUT=$(mktemp); .venv/Scripts/python.exe scripts/fixture_drift.py > "$OUT" 2>&1; echo "exit=$?"; cat "$OUT"`.
  Compare with spec §6:
  - The "corners scored" lines: the probe measured 22 of 35 fitted photos uncropped and 23 cropped. The
    harness counts all 46 photos, including the 11 that decline on geometry or resolution, so expect
    roughly 22/46 uncropped and 23/46 cropped.
  - Every photo in spec §6's decline table shows `cor    --` on its uncropped line.
  - Same-card spread: compute it from the printed corner scores for cards 12, 13, 2, 3, 4, 6 and 7
    (fronts, three or more shots), for both the uncropped and the cropped lines. Expect a mean around
    0.9–1.0.

  A difference of one or two photos is expected and must be **reported with the names**, not smoothed
  over. A large difference means the implementation differs from the probe: stop and investigate.

- [ ] **Step 2: Regenerate the methodology figures.**
  `.venv/Scripts/python.exe scripts/generate_methodology_figures.py`, then
  `git status --short frontend/public/methodology`. The demo card's corners were measured readable during
  planning, so the figures should be unchanged or change only in the corner caption. Open any changed
  image and check it still shows a whitened corner. Then run
  `OUT=$(mktemp); .venv/Scripts/python.exe -m pytest tests/test_methodology_figures.py -q > "$OUT" 2>&1; echo "exit=$?"; tail -20 "$OUT"`.
  Expected: **PASS**.

- [ ] **Step 3: Update `AGENTS.md`.**
  1. Under **Invariants**, directly after the paragraph that begins
     `**When the fit falls back, every category declines rather than scoring.**` and its following
     paragraph (ending `... that crop is the dominant variable ...` / `... clip a card that is
     off-centre.`), insert:

```markdown
**A crop offset has to be tested with a crop that is not at the image origin.** `rectify` draws the card
mask in the region of interest's coordinates and warps it through the homography composed with the crop
offset. It composed `−offset` where `+offset` was right, so every cropped analysis got a mask displaced by
twice the ROI origin. Production always passes a crop — the watcher analyses only sides with
`crop_points`, and operator ingest writes the detected box as one — and on 32 of 34 real photographs the
displaced mask left 7–100% of the raster reading as missing, which dropped corners to whitening alone on
nearly every report. Nothing saw it, for two reasons that are each worth remembering: every synthetic
fixture sits on an 8% margin while the ROI adds 10%, so the ROI origin clips to (0, 0) and the offset is
zero whichever way round it is applied; and the drift harness measured real photographs **uncropped**,
which is not the path that ships. `test_geometry.py`'s padded-canvas test puts the origin in the hundreds
of pixels, and the real-photo block now prints the cropped path beside the uncropped one.

**A corner's mask is believed only where it agrees with that corner's own fitted lines.** The mask is a
filled threshold contour; the lines are RANSAC over the same contour, which rejects outliers where the
mask cannot. Glare, or a pale border against a pale backdrop, breaks the first and not the second — on 9
of 36 real photographs whose fit held. The whole-raster gate that used to judge it (1% missing) was wrong
both ways: it passed a 7.72mm² bite out of an intact corner, because 0.21% of a card is small, and failed
cards whose hole was nowhere near a corner. `corners._corner_readable` checks each corner's straight
sections against the fitted lines and that any scored loss is reachable from the cut, and one unreadable
corner declines the category with `corners_boundary_unreadable` — a worst-anchored score cannot know it
skipped the worst corner. **There is no scored whitening-only path.** Sampled with no mask, the rounded
corner is backdrop, and real photographs read lightness "rises" of −40 to −150 there, which clip to zero
and score a clean corner. And the gate has a known blind spot: it catches artefacts that run along the
straight edge, but **a compact, rounded artefact is the shape of real wear and passes** — a 2–3mm shadow
over an intact corner reads as 1.6–5.3mm² of damage. "Gated" does not mean "correct".
```

  2. In the paragraph beginning `**When a category gains the ability to decline, something downstream
     assumes it cannot.**`, append this sentence at its end:
     ` Corners now also declines on its boundary check — about a third of real photographs, the most
     frequent decline path yet — and \`tests/test_corners_decline_end_to_end.py\` carries one through the
     combined row and the PDF.`
  3. In the **How the analysis pipeline fits together** table, add this row directly above the
     `| \`scoring.py\` |` row:

```markdown
| `corners.py` | Material loss (mm² beyond the factory rounding) and whitening per corner, and whether each corner's mask can be believed at all (`_corner_readable`). One unreadable corner declines the category; there is no whitening-only fallback. |
```

  4. Under **Analysis issues that are characterised but unfixed**, append these bullets after the last
     existing bullet (the one beginning `**A failed geometry fit cannot be graded, only detected.**`):

```markdown
- **Corner-local colour segmentation does not work, and has been measured.** Warping a padded raster so
  each corner sees its own backdrop, building Lab models of card (just inside the fitted lines) and
  background (just outside), and counting as missing only non-card pixels connected to the outside does
  remove the invented losses — 7.72 → 0.43mm² on 13_FrontSideAngle — but nothing says when to believe it.
  Against six clear failures, Fisher d′ scored AUC 0.85, overlap error 0.82 and a one-class background
  distance 0.68. The cause is physical: cards print badges and text boxes within a millimetre of the cut,
  so the card model is bimodal and its dark print looks like a dark mat. Under decline-if-any-corner the
  per-corner error compounds (65% per corner is about 18% per photo), and the best gate read 7–14 of 35
  photographs. Tracing the corner arc by gradient was rejected for the reason `border.py` exists: a printed
  box 2mm from the cut wins the rays. Do not reach for either without a card model that tolerates print at
  the edge.
- **Healthy-mask corner excess is biased and noisy.** Clean-looking corners read about 1mm² of excess
  (Kabutop 0.95–1.04 on all four), and card 7's move by 1–2mm² between shots. That fits a real die-cut
  radius nearer 2.5–3mm than the assumed 1.5mm, or boundary blur at 22–40 px/mm, and it is comparable to
  the 4mm² scoring range — the "noise comparable to its range" rule. It caps clean cards near 7.5 on
  corners. Settling it needs calipers on a real card; it is its own piece of work.
- **Two corner declines are borderline and accepted.** 4_FrontSlightLight top-right and 7_FrontView
  top-right carry only 0.25 and 0.12mm² of excess with no visible damage; the visibility rule fires on
  small speckle there. Relaxing it needs a new constant, and six failures are too few to fit one.
```

- [ ] **Step 4: Run the full backend suite.** Do the 5432 check first. Only one suite may run against the
  database at a time.
  `OUT=$(mktemp); .venv/Scripts/python.exe -m pytest -q > "$OUT" 2>&1; echo "exit=$?"; tail -40 "$OUT"`.
  Expected: exit 0. If anything fails outside the files this plan touched, read its traceback in `$OUT`
  before assuming it's unrelated. A test keyed on `corners_whitening_only` being *emitted* would be exactly
  the kind of thing Task 4 should have caught.

- [ ] **Step 5: Frontend checks.** From `frontend/`, run `npx tsc --noEmit`, then `npx next build`.
  Expected: both exit 0.

- [ ] **Step 6: Commit.**

```bash
git add AGENTS.md
git add frontend/public/methodology
git commit -m "Record the corner mask invariants and the measured dead ends

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

  (`git add frontend/public/methodology` stages only the regenerated figures. If Step 2 changed nothing,
  the commit carries `AGENTS.md` alone.)

- [ ] **Step 7: Report.** Summarise for the operator:
  - the real-photo counts and spreads from Step 1, next to spec §6's, naming any photo that differs
  - which figures changed
  - the full-suite result

  Note that **production corner scores move down broadly** on new analyses (spec §8), and that the
  read-only production check in spec §8 hasn't been run.
