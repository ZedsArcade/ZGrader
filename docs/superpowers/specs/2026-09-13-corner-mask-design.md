# Corner mask — design

**Date:** 2026-09-13
**Status:** draft for review — no code until this is approved and turned into a plan
**Covers:** the corners category's material-loss mask: a crop-offset bug in `preprocessing.rectify` that
displaces it on every cropped analysis, and the global gate that decides whether it can be trusted

---

## 1. What the real photographs showed

`scripts/fixture_drift.py` reports no synthetic drift, and 46 real photographs in `real_scans/`. Scored by
**same-card spread** — the card cannot change between shots, so every difference is measurement error —
across the seven cards photographed three or more times:

| Category | Mean spread | Worst card | Mechanism | Documented before? |
|---|---|---|---|---|
| Corners | **2.87** | 13: **5.94** | this spec | no |
| Centering | 1.74 | 6: 6.02 | bistable border-transition selection | yes |
| Edges | 1.46 | 3: 4.09 | outer strip read as whitened | no — queued, §9 |
| Surface | 1.34 | 12: 2.72 | glare shots score lowest | partly — queued, §9 |

Corners is the worst category, and its error goes both ways depending on which path a photo lands on.

### 1.1 The global contour is wrong on a quarter of the photographs where the fit succeeds

The mask comes from `detect_boundary`: one Otsu threshold on the HSV value channel over the whole search
region, largest contour, filled. The corner lines come from RANSAC over that contour's points, which rejects
outliers; the mask does not. On the 36 photographs that fit:

- **27 healthy:** 0.09–0.45% of the raster missing, almost all of it in the corner windows (factory rounding
  plus wear), none in the interior.
- **9 broken:** 1.42–16.07% missing, 57–99% of it *inside* the card, one side band 17–39% missing. Holo
  glare, or a pale silver border against a pale backdrop, is thresholded as background. Overlays confirm the
  fitted lines sit tight on the card in every case; only the mask is wrong.

What corners then does:

- **Above 1% missing, it drops to whitening only**, with the tip sampled against no mask. The rounded corner
  is backdrop by definition, so lightness "rise" reads −40 to −150 (the desk is darker), clips to zero, and
  the corner scores 9.3–10. That is the upward-biased shape AGENTS.md describes for geometry: a desk has no
  corner wear.
- **Below 1%, a local bite is scored as damage.** On `13_FrontSideAngle` the contour bites 7.72mm² out of an
  intact, cleanly rounded corner. The whole-raster fraction is 0.21%, so the global gate passes it, and the
  corner scores 0.0. Card 13 reads **3.47** there and 9.3–9.4 in its whitening-only shots.

### 1.2 Every cropped analysis gets a displaced mask

`rectify` draws the mask in ROI coordinates and composes the homography with the crop offset
(`preprocessing.py`, the `shift` matrix before `canonical_mask`). `matrix` maps **source** coordinates to the
canonical raster, and source = ROI + offset, so the composition must be `matrix @ T(+offset)`. The code builds
`T(−offset)`, which displaces the mask by twice the ROI origin.

Proven on the real set with a crop traced around the card (the uncropped run's fitted apexes; `rectify`
adds its own 10% margin):

- On all 32 photos whose ROI origin is non-zero, the shipped cropped mask equals a rebuild at −offset
  **exactly**, and 7.3–100% of the raster reads as missing.
- A rebuild at **+offset** reproduces the uncropped mask at **IoU 0.989–1.000**.
- The two photos unaffected are the ones whose ROI origin clipped to (0, 0).

Production always passes a crop. The watcher analyses only sides with `crop_points` set (`watcher.py`), the
customer's crop step writes them (`submissions.py`), and operator-ingested scans get the detected box written
as their crop. **So corners has very likely been scoring whitening-only on nearly every production report
since the mask shipped.** This has not been checked against production data (§8).

No test could see it. The `roi_quad` tests in `test_geometry.py` assert apexes, image shape and scale, never
the mask. And every synthetic fixture sits on an 8% margin while the ROI adds 10%, so the ROI origin clips to
(0, 0) and the offset is zero. It is the same shape as the entries under Invariants: the synthetic case is
the one where the bug cannot happen.

The drift harness has the same blind spot one level up: it runs real photographs **uncropped**, which is not
the path that ships.

## 2. Decisions made during brainstorming

| Question | Decision |
|---|---|
| Which problem first? | Corner mask. Centering, edges and surface stay queued (§9). |
| One unreadable corner: what does the category do? | **Declines.** Corners are scored worst-anchored, so a score from three corners cannot know it skipped the worst one. |
| The ~1mm² excess on clean-looking corners (nominal radius or blur)? | **Separate spec.** Recorded here as characterised-but-unfixed (§7). |
| Approach | **C′: gate the existing mask per corner.** Local colour segmentation (A) was probed and rejected (§3). |
| The sign bug | **Task 1 of this plan**, same PR as the gate. Shipping the fix alone exposes the invented-loss corners the gate removes. |

## 3. Rejected: corner-local colour segmentation (approach A)

Probed on the real set before committing, and worth recording so nobody reaches for it again without new
evidence.

The idea: warp a padded raster so each corner can see its own backdrop, build Lab colour models of card
(0.25–1.0mm inside both fitted lines) and background (0.25–1.5mm outside), classify the window, and count
as missing only non-card pixels connected to the outside of the lines.

**What worked.** It removes the invented losses when forced to read (13_FrontSideAngle bottom-left
7.72 → 0.43mm²; 2_AngleView 7.12 → 0.34; 6_FrontShot 5.09 → 0.00; 12_FrontView 7.87 → 0.00), and it matches
the global mask exactly on the synthetics (clipped corner 1.59 = 1.59).

**What failed: no readability statistic separates good corners from bad.** Labels came from shot-to-shot
consistency. Against 6 clear failures (a thumb, rainbow glare, backdrop matching the border):

| Statistic | AUC | Why it fails |
|---|---|---|
| Fisher d′ | 0.85 | crisp corners sit at 2.1–2.5, one failure at 2.63 |
| overlap error | 0.82 | good corners 0.2–0.5 wherever print sits near the edge |
| one-class background distance | 0.68 | a speckled mat has huge variance |
| visibility of the loss | 0.83 | useful — kept in C′ |

The cause is physical. Cards print badges and text boxes within a millimetre of the cut, so the card model is
bimodal and its dark print looks like a dark mat. The eye reads those corners by shape continuity, not colour
membership. Under the decline policy the per-corner errors compound (a 65% per-corner pass rate is about 18%
per photo): the best gate that rejected all six failures read **7–14 of 35 photos** and recovered **0 of 9**
broken-mask ones.

**Also rejected:** tracing the corner arc by gradient (B). "Strongest gradient" is what `border.py` was
written to escape, and on card 13 the printed "G" box 2mm from the cut would win the rays.

## 4. Principles this design establishes

These become AGENTS.md invariants when the work lands.

1. **Anything warped through a crop offset is tested with a non-zero ROI origin.** Synthetic fixtures clip
   the ROI to (0, 0), where an offset error is invisible.
2. **A corner's mask is trusted only where it agrees with that corner's own fitted lines.** The whole-raster
   missing fraction is not the gate: it passes a local bite and fails a card whose hole is nowhere near a
   corner.
3. **There is no scored whitening-only path.** An unreadable corner, or no mask at all, declines the
   category. Whitening sampled with no mask measures the backdrop in the rounded corner.
4. **The drift harness measures the cropped path as well as the uncropped one**, because the cropped path is
   the one that ships.

## 5. Design

### 5.1 The sign (`preprocessing.rectify`)

Compose with `+offset`, and rewrite the comment beside it to say which coordinate system each side is in.
Nothing else in `rectify` changes. Apexes already add the offset correctly.

### 5.2 A per-corner boundary check (`corners.py`)

`_corner_readable(mask_crop, px_per_mm, excess_mm2) -> str | None` returns a reason code, or None when the
corner can be read. It works on the oriented crop that `_material_loss` already uses (apex at [0, 0]), over
the straight section beyond `_STRAIGHT_EDGE_START_MM` on both edges:

| Check | Fails when | Reason |
|---|---|---|
| Edge inset | the median depth of first material exceeds `CORNER_MAX_EDGE_INSET_MM` (0.3) | `inset` — the mask sits well inside the fitted line along the straight edge, so it is describing something other than the card's cut |
| Straight-section deviation | more than `CORNER_MAX_STRAIGHT_DEVIATION_FRACTION` (0.10) of straight-section lines start more than `CORNER_STRAIGHT_DEVIATION_MM` (0.3) deeper than their median | `straight` — a bite along the edge, which a median alone cannot see if it covers under half the section |
| Visibility | only when `excess_mm2 > 0`: more than `CORNER_MAX_VISIBILITY_VIOLATION` (0.05) of missing pixels cannot see the outside along their row or their column | `visibility` — real corner loss is reachable from the cut; misclassification speckle is not |

A line with no material at all counts as deviating. It is the most extreme case, not one to drop, which is
where this differs from `_edge_inset_px`.

Every constant is tagged `REASONED` with its provenance. The photo-level outcome is identical across
straight-section thresholds 0.05–0.20 and visibility thresholds 0.05–0.10, so these sit on a plateau rather
than a knife edge. They are still calibrated on 46 photographs of about ten cards, and the docstrings say so.

### 5.3 `measure_corners`

- The resolution gate stays first, unchanged.
- **No mask, or a mask of the wrong shape → unmeasurable.** A new code, `CORNERS_BOUNDARY_UNREADABLE`
  (`corners_boundary_unreadable`). In practice this is the geometry-fallback case, which
  `GEOMETRY_UNVERIFIED` already disqualifies.
- `MAX_MASK_MISSING_FRACTION` and its gate are removed. `mask_missing_fraction` stays in `measurements` as
  a diagnostic.
- Each corner's check runs after `_material_loss`, since visibility depends on excess. Its result is stored
  per corner as `boundary_check` (reason or null), and `measurements.unreadable_corners` lists the failures.
- **Any corner unreadable → the category is unmeasurable**, with `CORNERS_BOUNDARY_UNREADABLE`, `raw_score`
  None, and a flag naming the corners. The per-corner diagnostics are still computed and kept.
- Otherwise scoring is unchanged: `scoring.corner_score` and `corners_category_score`, with whitening
  sampled through the mask exactly as today.
- `CORNERS_WHITENING_ONLY` is **no longer emitted, but stays in `ALL_LIMITATION_CODES` with its copy**,
  because stored results carry it and existing reports render it. `CONFIDENCE_CORNERS_WHITENING_ONLY`,
  `CONFIDENCE_CORNERS_PALE_BORDER` (the no-material variant) and `CORNERS_WHITENING_ONLY_FLAG` go, since
  nothing can reach them. Grep the tests for all three first (`test_assessment.py` references the corners
  codes); any test pinning them is rewritten, not deleted.

Nothing downstream needs to change for a declined category: `regions.build_regions` and
`pipeline._annotate_category` already return early on `raw_score is None`. AGENTS.md's warning still
applies, though: corners already declines on resolution, but it will now decline far more often. Grep for
`raw_score` consumers during implementation, and add a test that a declined corners category reaches the
combined row and the report without error.

### 5.4 Copy (EN/ES)

The code gets copy in `reports/strings.py` and both frontend dictionaries (`tsc` enforces the Spanish). It
leads with **retaking the photo, not fixing the crop**, and that is evidence-based: a crop does not repair
these contours (cropped with the sign fixed agrees with uncropped on 34 of 35 photos). Draft for the report:

> The card's outline could not be traced reliably at one or more corners in this photo — usually glare on
> the corner, a finger over it, or a background close in colour to the card's border — so corners were not
> scored rather than scored against the wrong outline. A photo on a plain surface that contrasts with the
> border, without glare on the corners, would let them be measured.

The frontend string is the shorter house form. The existing corners flag reason text is replaced along the
same lines.

### 5.5 A synthetic fixture that exercises the gate

`make_card_scan` gains `backing_color` below its divider, defaulting to black, so no existing fixture moves.
It flows to the canvas and to `_round_corners`' backing. A new fixture, `capture_pale_backdrop`, puts a
pale-bordered card on a light backdrop with glare over one corner, **tuned until the shipped gate produces
more than 1mm² of invented loss at an intact corner**. That is the regression test the drift baseline
otherwise cannot provide.

If no synthetic reproduces it, the plan records why and relies on the hand-built mask tests below. Either
way the fixture must not be the only guard.

### 5.6 The harness measures what ships

`fixture_metrics.measure_image` gains an optional `roi_quad`. `fixture_drift.py`'s real-photo block prints a
second line per photo for the cropped path (crop = the uncropped run's apexes, or its coarse quad on a
fallback), so a difference between the two paths is visible at a glance. Synthetics stay uncropped and
baselined: their ROI origin clips to zero, so a cropped synthetic pass would prove nothing.

## 6. Testing

TDD throughout; each test is written to fail against the current code first.

**Sign (`test_geometry.py`)**
- A fixture padded onto a large canvas (ROI origin in the hundreds of pixels), rectified with and without a
  crop: the canonical masks agree (IoU ≥ 0.99). Written to fail against −offset. With the padding removed
  it passes against both signs, which is exactly why the padding is the test.
- On that cropped path `measure_corners` measures material rather than declining.

**Boundary check (`test_corners.py`), on hand-built oriented mask crops**
- A cleanly rounded corner reads as readable.
- A bite along the straight section reads as `straight`.
- A mask inset by 0.5mm along both edges reads as `inset`.
- Speckle that cannot see the outside, with excess, reads as `visibility`; the same speckle with no excess
  reads as readable.
- `damage_corner_clipped` still reads about 1.59mm² and is scored, not declined. **Real damage must never be
  gated away**, and this is the test that says so.
- One unreadable corner makes the category unmeasurable with `CORNERS_BOUNDARY_UNREADABLE`, names the
  corner, and emits no regions.

**Rewritten, because the path they tested is gone**
- `test_without_a_mask_the_category_says_it_measured_only_whitening` → *without a mask the category
  declines*.
- `test_backing_is_excluded_from_the_tip_colour_sample` → compare `_whitening` with and without a mask
  crop directly, since `measure_corners(mask=None)` no longer scores.
- `test_a_pale_border_costs_less_confidence_than_it_used_to` → assert the pale-border limitation and
  `CONFIDENCE_CORNERS_PALE_BORDER_WITH_MATERIAL`; the no-mask comparison no longer exists.

**Drift and published figures**
- `scripts/fixture_drift.py`: the 23 existing fixtures must not drift (the probe showed ≤ 0.01, from
  rounding, on two foil fixtures; implementation must route through the same path and show none). The new
  fixture is added with `--update`, and that baseline diff is the reviewable statement.
- `scripts/generate_methodology_figures.py` is re-run, as AGENTS.md requires after any change under
  `analysis/`.

**The real-photo block, judged on spread and readings together** (probe figures, to be reproduced by the
implementation):

| Path | Corners read | Mean same-card spread |
|---|---|---|
| Shipped, uncropped | 35/35 | 2.87 |
| Shipped, cropped (what ships) | 34 scorable, 33 of them whitening-only | n/a: whitening against the desk |
| C′, uncropped | 22/35 | 0.94 |
| C′, cropped, sign fixed | 23/35 | 0.97 |

Every invented-loss corner identified in brainstorming must decline. Every photo that declines must name a
corner and a reason. The 13 declines in the probe:

| Photo | Corner: reason |
|---|---|
| 10_Golbat_Back | bottom-left: inset |
| 12_FrontView | bottom-left: inset |
| 13_FrontAngle | bottom-left: inset |
| 13_FrontGlare | bottom-left: straight; bottom-right: visibility |
| 13_FrontSideAngle | bottom-left: straight |
| 13_FrontView | bottom-left: inset |
| 2_AngleView | bottom-right: visibility |
| 3_FrontView | bottom-left: inset |
| 4_FrontSlightLight | top-right: visibility |
| 4_SkewedShot | bottom-left: straight |
| 6_FrontShot | bottom-left: inset |
| 6_FrontShotHighGlare | top-left: inset |
| 7_FrontView | top-right: visibility |

Two of these are **borderline and knowingly accepted**: 4_FrontSlightLight top-right and 7_FrontView
top-right carry only 0.25 and 0.12mm² of excess, and the overlays show no visible damage. Relaxing the
visibility rule for them needs a new constant, and six failures are too thin a base to fit one. They are
recorded in §7 rather than tuned away.

## 7. AGENTS.md changes

- **Invariants:** the four principles in §4; the sign bug and why neither synthetics nor the uncropped harness
  could see it, next to the existing crop and geometry entries; corners' new decline path under "When a
  category gains the ability to decline".
- **Characterised but unfixed:**
  - Approach A's negative result, with the AUCs, the bimodal-card-model cause and the compounding
    arithmetic.
  - **Healthy-mask excess is noisy and biased.** Card 7's clean-looking corners read 1–2mm² of excess that
    moves between shots, and clean corners across the set sit around 1mm² (Kabutop 0.95–1.04 on all four).
    That fits a real die-cut radius nearer 2.5–3mm than the assumed 1.5, or blur at 22–40 px/mm. It is
    comparable to the 4mm² scoring range, which is the "noise comparable to its range" rule. Separate spec.
  - The two borderline visibility declines.
- **How the pipeline fits together:** `corners` now owns a boundary check.

## 8. Production consequences

- **Scores move, and mostly down.** New analyses go from whitening-only (typically 9–10) to measured
  material loss (typically 6–9 on this set), and about a third of photographs will decline corners where
  they previously always had a number. Part of the drop is the ~1mm² healthy-corner bias above, which makes
  the radius spec more urgent once this ships.
- **Existing reports are not regenerated.** That follows the AGENTS.md rule: a re-run can restate a result
  the customer was already shown. A re-analysis of an existing submission will produce the new numbers.
- **Unverified claim, and how to check it read-only:** the fraction of stored corners results with
  `measurements.material_measured = false`, compared before and after the date the mask shipped, says
  whether production really ran whitening-only. That query is for the operator to run. Nothing in this
  work touches the production database.

## 9. Queued, not in this spec

| Item | Why it waits |
|---|---|
| Nominal corner radius and blur | Needs its own measurement, ideally calipers on a real card (§7). |
| Edges: outer strip read as whitened | Same photos as the broken masks. Edges never consult a mask; the §5.6 harness change makes it measurable. |
| Centering bottom edge | Characterised in AGENTS.md; cross-edge plausibility and a text-band mask are the untested leads. |
| Surface under glare | Glare shots score lowest on surface. |
| Geometry fallback rate | 10 of 46 photos uncropped. Only worth measuring on the cropped path now that §5.6 prints it. |
| Per-corner decline granularity | Rejected for now (§2); revisit only with graded examples. |

## 10. Risks

- **A third of photographs decline corners.** That is customer friction, and the copy has to earn it by
  being actionable. Six of the 13 declines come from one physical card (12/13, a silver-bordered Japanese
  Dragonite), so the rate on a broader set is unknown. Measure it again when new photographs arrive.
- **A small evidence base.** The gate's failures were characterised on 6 clear examples. The plateau makes
  it robust to the exact thresholds, but not to cases the set does not contain.
- **The fixture may not reproduce the failure** (§5.5). If it does not, the hand-built mask tests are the
  guard, and AGENTS.md says so, so the drift baseline is not mistaken for coverage.
