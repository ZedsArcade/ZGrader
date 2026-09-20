# Crop-guided edge fit — design

**Date:** 2026-09-16
**Status:** draft for review — no code until this is approved and turned into a plan
**Covers:** a customer's corrected crop being discarded by the edge fit, so a shadow that fools detection
fools the analysis too; and a safety net for when the fit and the crop still disagree

Depends on nothing in `2026-09-16-centering-placement-design.md`; built after it, on its own branch.

---

## 1. What happened

The report: the automatic crop cut off the bottom of the card, where the photo is in shadow. The customer
dragged the bottom of the crop down to the real edge, tightened each corner, and confirmed — and the
analysis ran on the original, cut-off outline.

### 1.1 The crop is saved; the fit overrides it

`confirm-crop` stores the points and runs the pipeline, which passes them to `preprocessing.rectify` as
`roi_quad`. Since the "fitted card edges, never the customer's crop" invariant, the crop is only a region to
search: `rectify` expands it by `ROI_MARGIN_FRACTION` (10%), runs `detect_boundary` inside it (one Otsu
threshold on the HSV value channel), and fits RANSAC lines to the resulting contour. `_refine_side` then
searches only ±`SUBPIXEL_SEARCH_PX` (6px, about 0.15mm) around each fitted line. A shadow puts the lower
card on the background side of the threshold, and widening the crop only adds more shadow to the search.

### 1.2 Reproduced on the customer's photograph

`real_scans/shadowed_photo.jpg` (3000×4000, 39.1 px/mm):

| Run | Method | Bottom apexes (y) | Aspect deviation | Limitations |
|---|---|---|---|---|
| No crop | ransac | 3596, 3551 | 0.058 | none |
| Detected crop | ransac | 3595, 3552 | 0.058 | none |
| **Crop with the bottom pulled to the real edge** (~y 3810–3830) | ransac | **3596, 3551** | 0.058 | none |

The corrected crop changes the fitted apexes by **zero pixels**. The fit is about **6mm short** of the real
bottom edge, and nothing flags it: the result would score confidently on a card with its bottom trimmed off.

Vertical L* profiles across the bottom (Gaussian σ=3, 20px-wide columns) show two falling steps: one at
y≈3530–3590, where the shadow and a printed strip begin (what the threshold found), and the true card edge
at **y≈3785–3805**, where L* drops from ~50 to ~3 against the black mat. The true step is at least as strong
as the false one; it is simply outside everything the fit looks at.

A synthetic probe on four other real photographs, darkening the lower half with a gradient, reproduced the
same thing on three: a crop traced exactly on the true card gave the same truncated outline as the detected
crop (15–24% of the height missing). The fourth fell back to `user_crop` with `geometry_unverified`. The
synthetic shadow is harsher than the real one, so those figures show the mechanism, not a rate.

### 1.3 Why a shape threshold cannot be the safety net

`MAX_ASPECT_DEVIATION` is 0.12 and `geometry_aspect_mismatch` is deliberately not disqualifying. Tightening
it was the obvious net and it does not separate. Measured across all 47 photographs in `real_scans/` with
the detected crop, correctly fitted photographs read up to **0.073** from perspective alone
(`12_FrontAngle` 0.073, `12_FrontSideAngle` 0.065, `13_FrontAngle` 0.060, `Kabutop_Back` 0.055), and
`shadowed_photo` reads **0.058**, inside that band. Do not reach for a shape threshold again without new
evidence.

What does separate them is the customer's own crop: the fitted bottom sits about 6mm inside the crop line,
where a traced crop is normally within a millimetre or two of the edge.

### 1.4 Why nothing caught it

- `check-crop` reports only disqualifying limitations, and a fit that succeeds on the wrong edge has none.
- `fixture_drift.py`'s real-photo "cropped" path builds its crop with `crop_like_a_customer`, which returns
  the **uncropped fit's own apexes**. The simulated customer crop is the fit, so it can never contain a crop
  that corrects the fit — the one case this bug lives in. The same shape as the crop-offset sign bug: the
  harness measured a path in which the bug could not occur.

## 2. Decisions made during brainstorming

| Question | Decision |
|---|---|
| How should the fix use the crop? | **Search for each edge near the customer's crop line**, from the image. The crop becomes evidence of *where to look*, never the geometry itself, except as a declared fallback. |
| Safety net | **Fit and crop disagreeing by more than a few mm on a side**, surfaced at the crop step and disqualifying if submitted anyway. The shape threshold is ruled out (§1.3). |
| Ship order | After the centering placement work, on its own branch. |

## 3. Design

### 3.1 Where it runs

In `preprocessing.rectify`, after `geometry.fit_card_geometry` succeeds and only when `roi_quad` was given.
New code lives in `geometry.py` beside the existing fit, so `rectify` stays the entry point it is today and
`check-crop`, which calls the same `load_deskewed_card`, inherits the behaviour by construction.

The fit runs in region-of-interest coordinates; the crop quad is translated into the same coordinates
(`roi_quad − offset`) before any comparison. This is the offset whose sign was once wrong in this function,
so it is tested with a crop that is **not** at the image origin (§5).

### 3.2 Per side: compare, then re-search

For each side, the crop's corresponding edge (between the crop quad's two corners on that side) is compared
with the fitted line: the signed perpendicular distance from the fitted line to the crop edge's midpoint and
to its two points at the corner margin (`CORNER_MARGIN_FRACTION`, 12%), converted to millimetres with the
fitted geometry's px/mm. The side's disagreement is the largest of the three.

- **Disagreement ≤ `CROP_REFIT_TRIGGER_MM`:** the fitted side stands, untouched. This is the common case:
  an untouched suggested crop and an operator-ingest crop are the detected box, which sits on the fit; a
  customer's crop half a millimetre inside the card is also under the trigger, so **the rule that a crop
  cannot trim damage out of the image is preserved exactly.**
- **Disagreement > trigger, and outward** — the crop claims *more* card than the fit found (the shadow
  case this spec exists for): the side is re-searched near the crop edge. The re-search fires only in this
  direction. A crop that disagrees *inward* — claiming *less* card than the fit found — is never
  re-searched and the fitted side stands untouched, even past the trigger: the crop is a hint about where
  to look, not a measurement, and AGENTS.md's invariant is that a crop inside the card must never trim the
  measured edge inward. (A round-1 implementation searched both directions and re-fit every side of a card
  onto printed border structure when the crop was traced 4mm inside it, shrinking a 63×88mm card to
  roughly 63×77mm — this restriction is what closes that.) Re-search itself:
  1. `SUBPIXEL_SAMPLES` sample positions along the crop edge, excluding the corner margins, as `_refine_side`
     does along a fitted side;
  2. at each, the HSV value profile along the crop edge's normal, over ±`CROP_REFIT_BAND_MM`;
  3. the **outermost** gradient peak (furthest from the card centre) with magnitude ≥
     `MIN_GRADIENT_RESPONSE`. Outermost, not strongest: moving outward, the last strong step is the
     card-to-background transition, while printed features inside the card can be stronger than a
     shadowed edge;
  4. `fit_line_ransac` over those points with the existing inlier tolerance, requiring at least
     `MIN_REFINED_FRACTION` of the samples as inliers;
  5. the existing `_refine_side` sub-pixel pass around that line, and `SideFit` fields computed as today.

  If step 4 succeeds, the new line replaces the fitted side and the apexes are re-intersected. The geometry
  block records `refit_sides: {"bottom": {"disagreement_mm": 6.2, "moved_mm": 5.9}}` so the result says
  what happened.

- **Re-search fails** (too few usable peaks, or no straight line through them): the side falls back to the
  crop edge, and the result carries `geometry_unverified` plus a new code
  `assessment.GEOMETRY_CROP_DISAGREEMENT = "geometry_crop_disagreement"`, with the side named in the
  geometry block. `geometry_unverified` is already in `DISQUALIFYING_LIMITATIONS`, so every
  boundary-dependent category declines through the existing path (§3.4). The new code exists for the copy,
  not the gate.

### 3.3 The constants

| Constant | Starting value | Tag | Why this shape |
|---|---|---|---|
| `CROP_REFIT_TRIGGER_MM` | 2.0 | ARBITRARY until measured | Above the slop of a crop traced by finger on a phone (a raw-photo pixel is ~8 raw px per screen px at phone width), below the 6mm shortfall observed. |
| `CROP_REFIT_BAND_MM` | 3.0 | ARBITRARY until measured | Wide enough to cover a crop 2–3mm off the true edge; narrow enough that the band around a crop on the edge does not reach a printed border line 3–4mm inside the cut. |

Both are set from the §4 measurements before merge, not from these starting values. A test asserts that the
band never exceeds the 10% region-of-interest margin (about 6mm at these sizes), or a re-search could run
off the pixels it was given.

### 3.4 What this does not change: the material mask

The corners mask is the filled `detect_boundary` contour. On a refit side it is still the shadow-truncated
contour, so the refit geometry and the mask disagree along that side. `corners._corner_readable` exists for
exactly that disagreement and will decline the affected corners with `corners_boundary_unreadable`: an
honest decline rather than 6mm² of invented material loss. That is accepted for this spec. Rebuilding the
mask from refit lines would erase real corner damage on that side, which is worse. The §4 measurement
records what corners does on `shadowed_photo`, so the cost is known rather than assumed.

### 3.5 At the crop step

`check-crop` runs `load_deskewed_card`, so it sees the refit and the fallback without changes of its own.
Its response already returns `limitations`, and `CropAdjustStep` already renders a limitation's
results-page copy. The new code gets EN/ES copy naming the side ("The bottom edge we found doesn't line up
with your crop. Drag that side onto the card's edge, or submit anyway and centering, corners and edges won't
be scored"), in `en.ts`/`es.ts` and `LIMITATION_LABELS`.

## 4. Measuring it — the harness first

Built before the change, so the change is judged by it.

- **Traced crops.** A real photograph may carry a sidecar, `<photo>.crop.json` —
  `{"points": [[x, y] × 4], "traced_by": "...", "note": "..."}` — holding a crop traced by hand around the
  card as a customer would. Sidecars are not committed, like the photographs; `real_scans/README.md` says
  how to make one. `fixture_drift.py`'s real-photo block gains a third path, **traced**, beside uncropped
  and cropped, printing apexes, px/mm, aspect deviation, `refit_sides` and each category's score.
- **Sloppy crops.** A `--sloppy` mode perturbs the harness crop of every real photograph by a seeded,
  per-side offset of ±1–2mm, in and out, and reports the largest apex displacement against the unperturbed
  run. This is the real regression test. The existing cropped path cannot fail, since its crop *is* the fit.

Acceptance, all measured and quoted in the PR:

1. `shadowed_photo` with a traced crop: bottom apexes within **0.5mm** of the profiled true edge
   (y≈3785–3805), aspect deviation down from 0.058 to the ≤0.02 of clean frontal photographs, and no
   `geometry_unverified`.
2. Every other real photograph under `--sloppy`: largest apex displacement **≤ 0.5mm**, and no photograph
   that fitted before falls back.
3. Uncropped and cropped paths: no change on any real photograph (the trigger never fires when the crop is
   the fit).
4. `fixture_drift.py`: the only baseline change is the new fixture (§5).
5. Corners on `shadowed_photo`, before and after, recorded (§3.4).

If criteria 1 and 2 cannot both be met with any trigger and band pair, that is a finding and gets reported,
not tuned around. It would mean the edge-shaped signal is not enough on its own, as happened with the border
transition entry in AGENTS.md.

## 5. Tests

- A new synthetic fixture, `capture_shadowed_bottom`: a card whose lower half carries a seeded gradient
  shadow strong enough that the Otsu contour stops short, on an offset canvas so the ROI origin is not
  (0, 0). It joins the drift baseline, which records what the change does to it.
- `test_geometry.py`:
  - a crop traced on the true edges of `capture_shadowed_bottom` refits the bottom to within 0.5mm;
  - a crop within the trigger of the fit leaves the geometry byte-identical to the uncropped fit;
  - a crop 0.5mm *inside* the card on every side leaves the geometry unchanged (the invariant);
  - a crop edge over featureless background with no edge in the band falls back, with
    `geometry_unverified` and `geometry_crop_disagreement`;
  - all of the above on a padded canvas, per the crop-offset rule in AGENTS.md.
- `test_api_check_crop.py`: the disagreement code reaches the response; a corrected crop on
  `capture_shadowed_bottom` passes the check.
- `test_geometry_disqualifies.py`: the fallback declines every boundary-dependent category.

## 6. Documentation

- AGENTS.md: amend "Measurement geometry comes from fitted card edges, never from the customer's crop":
  the crop is now also evidence of where to search, and the trigger is what keeps a slightly-inside crop from
  trimming damage. Add the shape-threshold result (§1.3) and the harness blind spot (§1.4) where the
  measured dead ends are kept.
- Run `backend/scripts/generate_methodology_figures.py`, and update `/methodology` if it describes how the
  crop is used (EN/ES).

## 7. Not in scope

- Making the global threshold robust to shadow (per-region thresholds, illumination flattening). It would
  help uncropped and untouched-crop photos too, but it changes the fit for every photograph and needs its
  own measurement round. This spec only acts when the customer has said where the edge is.
- Guidance in the capture copy about shadows; worth doing, and separate.
- Finding a card's edge *inside* a sleeve or toploader by tightening the crop past it. The re-search fires
  only where the crop claims more card than the fit found (outward), never where it claims less (inward),
  because a crop inside the card must never pull the measured edge inward; a crop tightened inside the
  fit's own edge leaves that side exactly as the fit measured it, so this case stays as it is today.
