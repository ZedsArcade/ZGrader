"""Where the card's edges actually are, to a fraction of a pixel.

Everything downstream inherits this. Centering measures a border against the
cut edge; corners measure material missing from an apex; edges measure wear
along a line. If the line is off by two pixels, or is the wrong line entirely,
no amount of care in those detectors recovers it.

WHAT WAS THERE BEFORE
---------------------
`preprocessing.detect_boundary` thresholds, takes the largest contour, and
either accepts `approxPolyDP`'s four vertices or falls back to
`minAreaRect`. Both have the same two problems:

* **A corner is a contour vertex.** It is one pixel-quantised point, chosen by
  a simplification algorithm, and it sits wherever the card's material
  actually ends. On a chipped corner that is *inside* the ideal apex -- so the
  crop traces tight around the damage and the damage disappears from the
  image before anything measures it. The `minAreaRect` fallback exists
  specifically to blunt this (see that function's comment), but it does so by
  giving up on perspective entirely: a rectangle cannot represent keystone.

* **Nothing uses the edges.** Four corners are four points. The hundreds of
  boundary points between them -- which is where roughness, nicks and bow live
  -- are discarded.

WHAT THIS DOES INSTEAD
----------------------
Fit a line to each side and intersect adjacent lines to get the apexes.

1. **Split the contour into four sides**, dropping a margin at each end. The
   margin is the whole point: a fitted line knows nothing about the corners,
   so intersecting two of them recovers where the apex *would be* if the
   corner were perfect. A chipped corner then reads as material missing from
   inside a known apex, which is the measurement phase 5 needs and the thing
   the old code could not express.

2. **RANSAC per side**, so a chipped corner, a thumb, or a shadow at one end
   moves nothing. A least-squares fit would let a single 20px excursion tilt
   the whole line; RANSAC fits the consensus and reports the excursion as a
   residual, which is both more robust and more informative.

3. **Sub-pixel refinement.** The contour comes from a binary threshold, so
   every point is quantised to a whole pixel. Each sample is re-found by
   walking the intensity gradient along the line's normal and fitting a
   parabola through the three samples around its peak -- the standard
   sub-pixel edge estimator, and it costs one pass over a few thousand
   bilinear samples. At 24 px/mm a whole pixel is 42 microns, so this is not
   ceremony: pixel quantisation alone is a meaningful fraction of the corner
   and edge features being measured.

4. **Keep the residuals.** The distance of each refined point from its fitted
   line is edge roughness at the sub-pixel scale, and its largest excursion is
   a nick. Retained here and unscored; edges consumes them in a later phase.

Deterministic by construction -- the RNG is seeded per call. A harness that
reports different numbers on a second run of the same image teaches everyone
to ignore it.
"""

import dataclasses

import cv2
import numpy as np

# --- Side splitting ---------------------------------------------------------

#: Fraction of each side's length dropped at both ends before fitting.
#: REASONED. It has to clear real corner rounding -- a factory corner radius is
#: about 1.5mm, and damage extends further -- without starving the fit. At 63mm
#: across, 0.12 drops ~7.5mm per end, comfortably past both, and still leaves
#: three quarters of every side to fit through.
CORNER_MARGIN_FRACTION = 0.12

#: A side needs enough points for the consensus to mean anything. Below this
#: the fit is declined rather than made from noise.
MIN_POINTS_PER_SIDE = 12

# --- RANSAC -----------------------------------------------------------------

#: Inlier distance, in pixels. ARBITRARY but bounded by what it has to
#: tolerate: a real cut edge wanders by a pixel or two under thresholding
#: noise, so anything tighter rejects the edge itself. Anything much looser
#: starts admitting a chipped corner as consensus.
RANSAC_INLIER_PX = 2.5
RANSAC_ITERATIONS = 120
RANSAC_SEED = 20260803

# --- Sub-pixel refinement ---------------------------------------------------

#: How far along the normal to search for the true edge, in pixels. The coarse
#: fit is already within a pixel or two; this only has to cover thresholding
#: bias, not find the edge from scratch.
SUBPIXEL_SEARCH_PX = 6.0
SUBPIXEL_STEP_PX = 0.5
#: Samples per side taken for refinement. Enough to characterise roughness
#: along a 63-88mm edge without making this the pipeline's slow step.
SUBPIXEL_SAMPLES = 96
#: Gradient magnitude below which a sample is not an edge at all -- a blown-out
#: or backing-coloured stretch where the card boundary is genuinely invisible.
#: Such samples are dropped rather than allowed to pull the line toward noise.
MIN_GRADIENT_RESPONSE = 4.0

#: Below this fraction of samples surviving refinement, the side is reported
#: as unrefined and the coarse RANSAC fit stands. Not an error -- a partially
#: invisible edge is still a usable line, it just carries no roughness figure.
MIN_REFINED_FRACTION = 0.5


@dataclasses.dataclass(frozen=True)
class SideFit:
    """One fitted card edge.

    `normal` is a unit vector and `offset` satisfies `normal . p == offset` for
    points p on the line, so a point's signed distance is just
    `normal . p - offset`. Chosen over a slope/intercept form because it has no
    special case for a vertical edge, and two of the four sides are vertical.
    """

    normal: np.ndarray
    offset: float
    inlier_count: int
    total_points: int
    refined: bool
    #: Sub-pixel residual statistics, in pixels. Empty when `refined` is False.
    roughness_px: float
    max_excursion_px: float
    bow_px: float

    def signed_distance(self, points: np.ndarray) -> np.ndarray:
        return points @ self.normal - self.offset


@dataclasses.dataclass(frozen=True)
class CardGeometry:
    """The card's four apexes and how well they are known."""

    #: Top-left, top-right, bottom-right, bottom-left, in source-image pixels.
    apexes: np.ndarray
    sides: dict[str, SideFit]
    #: "ransac" when the apexes come from fitted lines, "fallback" when the
    #: fit was declined and a caller-supplied quad stands in its place.
    method: str

    def as_dict(self) -> dict:
        return {
            "method": self.method,
            "apexes": [[round(float(x), 2), round(float(y), 2)] for x, y in self.apexes],
            "sides": {
                name: {
                    "inlier_fraction": round(fit.inlier_count / max(1, fit.total_points), 3),
                    "refined": fit.refined,
                    "roughness_px": round(fit.roughness_px, 3),
                    "max_excursion_px": round(fit.max_excursion_px, 3),
                    "bow_px": round(fit.bow_px, 3),
                }
                for name, fit in self.sides.items()
            },
        }


def _unit_normal(p0: np.ndarray, p1: np.ndarray) -> np.ndarray | None:
    direction = p1 - p0
    length = float(np.hypot(*direction))
    if length < 1e-6:
        return None
    return np.array([-direction[1] / length, direction[0] / length])


def _fit_total_least_squares(points: np.ndarray) -> tuple[np.ndarray, float]:
    """Line of best fit minimising perpendicular distance.

    Ordinary least squares minimises *vertical* distance, which is undefined in
    the limit for a vertical edge and badly conditioned near it -- and two of
    the four sides of a card are vertical. The smallest-eigenvalue eigenvector
    of the centred scatter matrix is the normal, with no such axis preference.
    """
    centroid = points.mean(axis=0)
    centred = points - centroid
    _u, _s, vt = np.linalg.svd(centred, full_matrices=False)
    normal = vt[-1]
    normal = normal / np.linalg.norm(normal)
    return normal, float(normal @ centroid)


def fit_line_ransac(
    points: np.ndarray,
    inlier_px: float = RANSAC_INLIER_PX,
    iterations: int = RANSAC_ITERATIONS,
    seed: int = RANSAC_SEED,
) -> tuple[np.ndarray, float, np.ndarray]:
    """Returns (normal, offset, inlier_mask).

    The refit on inliers at the end matters as much as the consensus search:
    RANSAC's best hypothesis is a line through two sampled points, which is a
    poor estimate even when it has found the right inliers.
    """
    rng = np.random.default_rng(seed)
    n = len(points)
    best_mask = np.zeros(n, dtype=bool)

    for _ in range(iterations):
        i, j = rng.choice(n, size=2, replace=False)
        normal = _unit_normal(points[i], points[j])
        if normal is None:
            continue
        offset = float(normal @ points[i])
        mask = np.abs(points @ normal - offset) <= inlier_px
        if mask.sum() > best_mask.sum():
            best_mask = mask

    if best_mask.sum() < 2:
        normal, offset = _fit_total_least_squares(points)
        return normal, offset, np.ones(n, dtype=bool)

    normal, offset = _fit_total_least_squares(points[best_mask])
    # One re-selection pass: the refit moved the line, so the inlier set that
    # produced it is no longer quite the inlier set it implies.
    mask = np.abs(points @ normal - offset) <= inlier_px
    if mask.sum() >= 2:
        normal, offset = _fit_total_least_squares(points[mask])
        best_mask = mask
    return normal, offset, best_mask


def _sample_bilinear(image: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Bilinear sample of a single-channel image at float coordinates.

    Written out rather than reaching for cv2.remap because the sample points
    here are a scattered set, not a grid, and building a grid to throw most of
    it away costs more than the arithmetic.
    """
    h, w = image.shape[:2]
    xs = np.clip(xs, 0, w - 1.001)
    ys = np.clip(ys, 0, h - 1.001)
    x0 = np.floor(xs).astype(int)
    y0 = np.floor(ys).astype(int)
    x1, y1 = x0 + 1, y0 + 1
    fx, fy = xs - x0, ys - y0
    img = image.astype(np.float32)
    top = img[y0, x0] * (1 - fx) + img[y0, x1] * fx
    bottom = img[y1, x0] * (1 - fx) + img[y1, x1] * fx
    return top * (1 - fy) + bottom * fy


def _parabola_vertex(y_prev: np.ndarray, y_mid: np.ndarray, y_next: np.ndarray) -> np.ndarray:
    """Sub-sample offset of a parabola's peak through three equally spaced
    samples, in units of the sample spacing, clamped to +/-1.

    The clamp is not cosmetic: when the three samples are nearly equal the
    denominator approaches zero and the unclamped vertex flies off, which would
    place an "edge" further from the search centre than the search itself went.
    """
    denominator = y_prev - 2.0 * y_mid + y_next
    safe = np.where(np.abs(denominator) < 1e-6, 1e-6, denominator)
    return np.clip(0.5 * (y_prev - y_next) / safe, -1.0, 1.0)


def _refine_side(
    value: np.ndarray,
    normal: np.ndarray,
    offset: float,
    start: np.ndarray,
    end: np.ndarray,
    inward: np.ndarray,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Re-find the edge to sub-pixel precision along a fitted side.

    Returns (refined_points, residuals) or None if too little of the edge was
    visible to trust. `inward` points into the card, and only fixes the sign
    convention -- the gradient peak is found on magnitude, so an edge that is
    dark-on-light and one that is light-on-dark behave identically.
    """
    ts = np.linspace(0.0, 1.0, SUBPIXEL_SAMPLES)
    bases = start + ts[:, None] * (end - start)

    taps = np.arange(-SUBPIXEL_SEARCH_PX, SUBPIXEL_SEARCH_PX + SUBPIXEL_STEP_PX, SUBPIXEL_STEP_PX)
    # profile[i, k] = intensity at sample i, tap k along the normal.
    xs = bases[:, 0][:, None] + taps[None, :] * inward[0]
    ys = bases[:, 1][:, None] + taps[None, :] * inward[1]
    profile = _sample_bilinear(value, xs, ys)

    gradient = np.abs(np.gradient(profile, axis=1))
    peak = np.argmax(gradient, axis=1)
    strength = gradient[np.arange(len(peak)), peak]

    # A peak at either end of the search means the true edge is outside it, so
    # the "peak" is just the profile still rising -- not a located edge.
    interior = (peak > 0) & (peak < gradient.shape[1] - 1)
    usable = interior & (strength >= MIN_GRADIENT_RESPONSE)
    if usable.sum() < MIN_REFINED_FRACTION * SUBPIXEL_SAMPLES:
        return None

    idx = np.arange(len(peak))
    # Clamped before indexing, not after: a peak sitting on either end of the
    # search has no neighbour on one side. Those samples are discarded by
    # `usable` a line later, but the parabola is evaluated for all of them, so
    # without this the array lookup itself raises.
    safe_peak = np.clip(peak, 1, gradient.shape[1] - 2)
    sub = _parabola_vertex(
        gradient[idx, safe_peak - 1], gradient[idx, safe_peak], gradient[idx, safe_peak + 1]
    )
    along_normal = taps[safe_peak] + sub * SUBPIXEL_STEP_PX
    refined = bases + along_normal[:, None] * inward[None, :]
    refined = refined[usable]

    residuals = refined @ normal - offset
    return refined, residuals


def _bow(residuals: np.ndarray) -> float:
    """Peak deviation of the *smooth* component of an edge, in pixels.

    A bowed card and a rough one both have large residuals; what separates them
    is that a bow is a low-order trend along the edge and roughness is not.
    Fitting a quadratic and taking its own peak-to-line deviation isolates the
    trend, so a warped card does not read as a hundred small nicks.
    """
    if len(residuals) < 3:
        return 0.0
    ts = np.linspace(-1.0, 1.0, len(residuals))
    a, b, c = np.polyfit(ts, residuals, 2)
    smooth = a * ts**2 + b * ts + c
    # Deviation from the straight line through the fitted curve's endpoints --
    # a tilt is the line fit's business, not bow's.
    chord = np.linspace(smooth[0], smooth[-1], len(smooth))
    return float(np.max(np.abs(smooth - chord)))


def _split_sides(contour: np.ndarray, quad: np.ndarray) -> dict[str, np.ndarray]:
    """Assign each contour point to the quad side it lies nearest, dropping a
    margin at both ends of every side.

    Assignment is by projection onto each side's own direction rather than by
    nearest-vertex, so a point near a corner goes to the side it is actually
    collinear with instead of being split arbitrarily between the two.
    """
    ordered = _order_quad(quad)
    pairs = {
        "top": (ordered[0], ordered[1]),
        "right": (ordered[1], ordered[2]),
        "bottom": (ordered[3], ordered[2]),
        "left": (ordered[0], ordered[3]),
    }

    distances = {}
    positions = {}
    for name, (a, b) in pairs.items():
        direction = b - a
        length_sq = float(direction @ direction)
        if length_sq < 1e-9:
            distances[name] = np.full(len(contour), np.inf)
            positions[name] = np.zeros(len(contour))
            continue
        t = ((contour - a) @ direction) / length_sq
        projected = a + np.clip(t, 0.0, 1.0)[:, None] * direction
        distances[name] = np.linalg.norm(contour - projected, axis=1)
        positions[name] = t

    names = list(pairs)
    stacked = np.stack([distances[n] for n in names], axis=1)
    nearest = np.argmin(stacked, axis=1)

    sides = {}
    for i, name in enumerate(names):
        t = positions[name]
        keep = (
            (nearest == i)
            & (t >= CORNER_MARGIN_FRACTION)
            & (t <= 1.0 - CORNER_MARGIN_FRACTION)
        )
        sides[name] = contour[keep]
    return sides


def _order_quad(points: np.ndarray) -> np.ndarray:
    """Top-left, top-right, bottom-right, bottom-left.

    Duplicates preprocessing._order_points deliberately rather than importing
    it: preprocessing imports nothing from here, and reversing that would make
    the two modules mutually dependent for four lines of arithmetic.
    """
    pts = np.asarray(points, dtype=np.float64).reshape(4, 2)
    ordered = np.zeros((4, 2), dtype=np.float64)
    s = pts.sum(axis=1)
    ordered[0] = pts[np.argmin(s)]
    ordered[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1).ravel()
    ordered[1] = pts[np.argmin(diff)]
    ordered[3] = pts[np.argmax(diff)]
    return ordered


def _intersect(a: SideFit, b: SideFit) -> np.ndarray | None:
    matrix = np.stack([a.normal, b.normal])
    determinant = float(np.linalg.det(matrix))
    # Near-parallel sides have no meaningful intersection. Two adjacent card
    # edges are nominally perpendicular, so this only fires when a fit has
    # gone badly wrong -- and inventing an apex from it would put a corner
    # thousands of pixels off the image.
    if abs(determinant) < 1e-3:
        return None
    return np.linalg.solve(matrix, np.array([a.offset, b.offset]))


def fit_card_geometry(
    image: np.ndarray, contour: np.ndarray, quad: np.ndarray
) -> CardGeometry | None:
    """Fit the four card edges and intersect them for the ideal apexes.

    `contour` is the detected boundary (Nx2) and `quad` its coarse four-point
    approximation, used only to decide which points belong to which side.
    Returns None when the fit cannot be trusted, which the caller must treat as
    "use the coarse quad and say so" rather than as an error.
    """
    contour = np.asarray(contour, dtype=np.float64).reshape(-1, 2)
    if len(contour) < 4 * MIN_POINTS_PER_SIDE:
        return None

    grouped = _split_sides(contour, quad)
    if any(len(pts) < MIN_POINTS_PER_SIDE for pts in grouped.values()):
        return None

    ordered = _order_quad(quad)
    centre = ordered.mean(axis=0)
    value = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 2]

    sides: dict[str, SideFit] = {}
    for name, points in grouped.items():
        normal, offset, mask = fit_line_ransac(points)
        # Point the normal into the card, so the refinement search walks a
        # consistent direction and a residual's sign means the same thing on
        # every side.
        if (centre @ normal - offset) < 0:
            normal, offset = -normal, -offset

        inliers = points[mask]
        along = np.array([-normal[1], normal[0]])
        projections = inliers @ along
        start = inliers[np.argmin(projections)]
        end = inliers[np.argmax(projections)]
        # Put start/end back onto the fitted line, so refinement samples run
        # along the line rather than between two contour points that happen to
        # sit a pixel off it.
        start = start - (start @ normal - offset) * normal
        end = end - (end @ normal - offset) * normal

        refinement = _refine_side(value, normal, offset, start, end, normal)
        if refinement is None:
            sides[name] = SideFit(
                normal=normal,
                offset=offset,
                inlier_count=int(mask.sum()),
                total_points=len(points),
                refined=False,
                roughness_px=0.0,
                max_excursion_px=0.0,
                bow_px=0.0,
            )
            continue

        refined_points, _residuals = refinement
        normal, offset = _fit_total_least_squares(refined_points)
        if (centre @ normal - offset) < 0:
            normal, offset = -normal, -offset
        final_residuals = refined_points @ normal - offset

        sides[name] = SideFit(
            normal=normal,
            offset=offset,
            inlier_count=int(mask.sum()),
            total_points=len(points),
            refined=True,
            roughness_px=float(np.std(final_residuals)),
            max_excursion_px=float(np.max(np.abs(final_residuals))),
            bow_px=_bow(final_residuals),
        )

    corners = {
        "top_left": ("top", "left"),
        "top_right": ("top", "right"),
        "bottom_right": ("bottom", "right"),
        "bottom_left": ("bottom", "left"),
    }
    apexes = []
    for _name, (a, b) in corners.items():
        point = _intersect(sides[a], sides[b])
        if point is None:
            return None
        apexes.append(point)

    apexes = np.array(apexes, dtype=np.float64)
    # A fit can be individually sane per side and still produce a nonsense
    # quad -- two sides assigned the same stretch of contour, say. Requiring
    # the apexes to stay near the coarse quad catches that without constraining
    # the sub-pixel correction the whole exercise is for.
    span = float(np.max(np.linalg.norm(ordered - centre, axis=1)))
    if np.max(np.linalg.norm(_order_quad(apexes) - ordered, axis=1)) > 0.25 * span:
        return None

    return CardGeometry(apexes=_order_quad(apexes), sides=sides, method="ransac")


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
#: searched again, in millimetres. REASONED, and measured to be the least
#: load-bearing of these four. Swept over 1.0 / 1.5 / 2.0 / 3.0 against 37 real
#: photographs each re-searched with a crop 2.5mm and 3.0mm proud of its own
#: fitted sides, plus `shadowed_photo.jpg` on its traced crop and the
#: `capture_shadowed_bottom` fixture: 1.0, 1.5 and 2.0 produce *identical*
#: numbers on all three, because whether a side is searched at all barely
#: changes what the search then finds. 3.0 differs only by switching the
#: 2.5mm-proud case off entirely, which is a fact about that test crop rather
#: than about any edge. So 2.0 stands: comfortably above the slop of a crop
#: traced by finger on a phone, and far below the disagreements this exists to
#: catch -- 5.29mm on the fixture and 7.31mm on the photograph.
CROP_REFIT_TRIGGER_MM = 2.0

#: How far either side of the crop line that search looks, in millimetres.
#: DERIVED. The band has to be *wider* than the crop slop it is meant to see
#: past: the card's edge sits that slop inward of the crop line, and a truth
#: sitting on the band's own limit is half-clipped by the local-maximum test.
#: Measured on 37 real photographs, each re-searched with a crop 2.5mm and
#: 3.0mm proud of its own fitted sides -- which makes the true edge's position
#: known exactly, so every side is a labelled example. At band 3.0 the
#: 3.0mm-proud case puts the edge exactly on the limit and 21 of 148 sides lose
#: it altogether, against 1 of 148 at band 4.0 and 5.0. End to end at
#: `CROP_REFIT_PEAK_FRACTION`, band 3.0 leaves 4 of 70 runs moving a side
#: outward by more than 0.5mm and band 5.0 leaves 4 (up to 6.97mm), against 2
#: at 3.5, 4.0 and 4.5 -- and those two are the same photograph, correcting an
#: edge the uncropped fit had wrong. 4.0 is the middle of that plateau.
#:
#: The upper bound is structural rather than empirical: the band must stay
#: under the region-of-interest margin `rectify` expands the crop by
#: (`preprocessing.ROI_MARGIN_FRACTION`, 10% of the crop, about 6.3mm across a
#: 63mm card), or the search runs off the pixels it was given.
CROP_REFIT_BAND_MM = 4.0

#: A peak qualifies only if it stands at this fraction of the strongest
#: gradient along its own normal. DERIVED, and the thing that stops a textured
#: backdrop winning. `MIN_GRADIENT_RESPONSE` alone is an absolute floor set for
#: a +/-6px refinement window, and a desk, a cutting mat or a sleeve clears it
#: all along a 4mm band -- so "the outermost peak above the floor" stopped
#: being the card's edge and became the outer limit of the search itself.
#:
#: Swept end to end, at band 4.0, against all three things this has to be true
#: of at once -- 70 proud-crop runs on real photographs, the real photograph
#: the feature exists for, and the synthetic fixture:
#:
#:     fraction  runs moving a side out >0.5mm   shadowed_photo recovered?
#:     floor only (0.0)   72 of 72, up to 7.43mm   yes
#:     0.35               13, up to 6.95mm         yes
#:     0.45                4, up to 6.95mm         yes
#:     0.55                2, up to 2.83mm         yes
#:     0.65                2, up to 2.81mm         yes
#:     0.75                3, up to 2.41mm         yes
#:     0.80                3, up to 2.12mm         NO -- side never resolves
#:     0.90                3, up to 2.11mm         NO
#:
#: and in every row the two remaining >0.5mm runs are one photograph
#: (`Kabutop_Back`) whose uncropped top edge is fitted 2.1mm inside the cut, so
#: the re-search is correcting it, not inflating it -- confirmed by eye against
#: the image.
#:
#: The plateau is 0.55-0.75 and 0.65 is its centre, which is where this sits:
#: below it a strong feature a few millimetres outside the card wins, above it
#: the shadowed photograph's own cut -- a weak step, which is the whole reason
#: that photograph is hard -- stops qualifying next to the stronger shadow
#: boundary inside the card, and the side it exists to recover goes
#: unresolved. A relative test rather than a larger absolute one because what
#: separates a cut from backdrop texture is contrast against the rest of that
#: profile, and no absolute number travels between a flatbed and a phone.
#: Taking simply the strongest peak was measured too (99.1% of labelled sides
#: within 0.5mm) and rejected on the same evidence: it is `fraction = 1.0`, past
#: the cliff, and it throws away the outermost-peak arbitration that exists so
#: a printed border cannot beat the cut.
CROP_REFIT_PEAK_FRACTION = 0.65

#: A peak this close to either end of the search is not a located edge.
#: REASONED, and the same reasoning `_refine_side` already applies to its own
#: ends: a profile still rising at the limit of the window means the true edge
#: is outside it. Two taps (1px at the 0.5px step) is the smallest span that
#: leaves the parabola a neighbour on each side. Honest about its weight: with
#: `CROP_REFIT_PEAK_FRACTION` in place this changes nothing measurable -- 0, 2
#: and 4 taps give byte-identical results on all three criteria -- because the
#: failures it was proposed for do not sit at the limit once a peak has to
#: stand against its own profile. It is kept as the cheap statement of a true
#: thing, not as the gate doing the work.
CROP_REFIT_OUTER_GUARD_TAPS = 2

#: Which two ordered crop corners bound each side (top-left, top-right,
#: bottom-right, bottom-left), matching `_split_sides`.
_CROP_SIDE_CORNERS = {"top": (0, 1), "right": (1, 2), "bottom": (3, 2), "left": (0, 3)}

#: Why a re-search came back without a line. The two are not the same thing and
#: the caller must not treat them alike -- see `_fit_side_near_line`.
_NO_EDGE = "no_edge"
_NO_CONSENSUS = "no_consensus"


@dataclasses.dataclass(frozen=True)
class CropRefit:
    """The geometry after the crop was allowed to argue with it."""

    geometry: CardGeometry
    #: Per side that was re-searched: how far it disagreed with the crop and
    #: how far the line actually moved, both in millimetres.
    moved: dict[str, dict[str, float]]
    #: Sides that disagreed and whose re-search found *nothing edge-shaped* to
    #: move to. The caller treats these as "the fit cannot be trusted here" --
    #: there is no half-trusted geometry. A side whose re-search found edges
    #: but could not place a line is deliberately not here: see the
    #: `_NO_CONSENSUS` branch in `refit_geometry_near_crop`.
    unresolved: tuple[str, ...]


def _fit_side_near_line(
    value: np.ndarray,
    start: np.ndarray,
    end: np.ndarray,
    centre: np.ndarray,
    band_px: float,
) -> tuple[SideFit | None, str]:
    """Re-find one card edge within `band_px` of the segment start->end.

    Returns `(fit, reason)`. The two ways of coming back empty are different
    facts about the image and the caller must not treat them alike:

    * `_NO_EDGE` -- fewer than half the normals carry any gradient worth the
      name. There is nothing edge-shaped anywhere near the crop line; the crop
      is pointing at background.
    * `_NO_CONSENSUS` -- peaks are there but they do not lie on a line. The
      re-search has found no edge it can place, so it has nothing better to
      offer than the fit that is already there.

    Takes the **outermost** qualifying gradient peak along each normal, not the
    strongest. Moving outward from the card, the last strong step is the
    card-to-background transition; a printed border or a text box inside the
    card can be stronger than a shadowed edge, and taking the strongest is how
    `border.py`'s rays lose to a printed box.

    "Qualifying" is what was hardened, and it is the difference between a rule
    about this edge and a rule about the search. `MIN_GRADIENT_RESPONSE` is an
    absolute floor set for the sub-pixel refinement's own +/-6px window; a
    desk, a cutting mat or a sleeve clears it all along the band, so on a
    textured backdrop the outermost peak above the floor was simply the
    outermost *tap* -- the outer limit of the search, reported as a card edge
    with no limitation raised. Measured on 37 real photographs re-searched with
    a crop 2.5-3.0mm proud of their own fitted sides, that rule put the line
    within 0.5mm of the known edge on 3-4% of 296 sides and was wrong by up to
    6.95mm, growing whole cards by 17% in px/mm while `limitations` stayed
    empty. A peak now also has to stand at `CROP_REFIT_PEAK_FRACTION` of the
    strongest step along its own normal -- a relative test, because what
    separates a cut from backdrop texture is contrast against the rest of that
    profile, not an absolute number. End to end that takes the same 70 runs
    from all of them moving a side outward by more than 0.5mm (up to 7.43mm) to
    two, both of them one photograph whose uncropped fit was the thing that was
    wrong. The synthetic fixtures cannot express any of this: their backing is
    a flat fill whose gradient is exactly zero, so the floor rejected
    everything and the side merely unresolved.
    """
    normal = _unit_normal(start, end)
    if normal is None:
        return None, _NO_EDGE
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

    # Nothing edge-shaped near the crop line at all: the strongest step along
    # each normal does not clear the absolute floor. This is the flat-backing
    # case, and it is the one the caller must decline on.
    strongest = gradient.max(axis=1)
    if (strongest >= MIN_GRADIENT_RESPONSE).sum() < MIN_REFINED_FRACTION * SUBPIXEL_SAMPLES:
        return None, _NO_EDGE

    # A qualifying peak is a local maximum that clears both the absolute floor
    # and this normal's own relative one, with a neighbour on each side so the
    # parabola has something to fit.
    qualifies = np.zeros_like(gradient, dtype=bool)
    qualifies[:, 1:-1] = (
        (gradient[:, 1:-1] >= gradient[:, :-2])
        & (gradient[:, 1:-1] >= gradient[:, 2:])
        & (gradient[:, 1:-1] >= MIN_GRADIENT_RESPONSE)
        & (gradient[:, 1:-1] >= CROP_REFIT_PEAK_FRACTION * strongest[:, None])
    )
    peak = np.argmax(qualifies, axis=1)  # first True is the outermost tap
    # A peak against either limit of the band means the true edge is outside
    # the search, not that it was found at the edge of it.
    guard = CROP_REFIT_OUTER_GUARD_TAPS
    usable = (
        qualifies.any(axis=1) & (peak > guard) & (peak < gradient.shape[1] - 1 - guard)
    )
    if usable.sum() < MIN_REFINED_FRACTION * SUBPIXEL_SAMPLES:
        return None, _NO_CONSENSUS

    safe_peak = np.clip(peak, 1, gradient.shape[1] - 2)
    idx = np.arange(len(peak))
    sub = _parabola_vertex(
        gradient[idx, safe_peak - 1], gradient[idx, safe_peak], gradient[idx, safe_peak + 1]
    )
    along_normal = taps[safe_peak] + sub * SUBPIXEL_STEP_PX
    points = (bases + along_normal[:, None] * normal[None, :])[usable]

    fit_normal, fit_offset, mask = fit_line_ransac(points)
    if mask.sum() < MIN_REFINED_FRACTION * len(points):
        return None, _NO_CONSENSUS
    fit_normal, fit_offset = _fit_total_least_squares(points[mask])
    if (centre @ fit_normal - fit_offset) < 0:
        fit_normal, fit_offset = -fit_normal, -fit_offset
    residuals = points[mask] @ fit_normal - fit_offset
    return (
        SideFit(
            normal=fit_normal,
            offset=fit_offset,
            inlier_count=int(mask.sum()),
            total_points=len(points),
            refined=True,
            roughness_px=float(np.std(residuals)),
            max_excursion_px=float(np.max(np.abs(residuals))),
            bow_px=_bow(residuals),
        ),
        "found",
    )


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

    The re-search only ever fires **outward**. Each `SideFit.normal` points
    into the card (see `fit_card_geometry`), so `signed_distance` is positive
    on the card's own side of the fitted line and negative beyond it, toward
    the background. A crop point with a *negative* signed distance is claiming
    more card than the fit found -- the shadow-hides-the-edge case this exists
    for -- and is evidence the fit landed on the wrong step. A crop point with
    a *positive* signed distance is claiming less card than the fit found: a
    tighter crop than the fit's own edge, which is not evidence against an
    edge the fit already measured from the image. AGENTS.md's invariant is
    that a crop inside the card must never trim the measured edge inward, so
    that side is left exactly as fitted -- no re-search, and it is not
    `unresolved` either, since nothing about it was in question.
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
        signed = sides[name].signed_distance(samples)
        worst_idx = int(np.argmax(np.abs(signed)))
        worst = float(signed[worst_idx])
        disagreement_mm = abs(worst) / px_per_mm
        # worst > 0 means the crop's largest disagreement lies on the card's
        # own side of the fitted line -- inward -- which is never grounds to
        # re-search (see the docstring). Only worst < 0, the crop reaching
        # past the fitted line toward the background, is searched.
        if disagreement_mm <= trigger_mm or worst > 0:
            continue

        found, reason = _fit_side_near_line(value, start, end, centre, band_mm * px_per_mm)
        if found is None:
            if reason == _NO_EDGE:
                # The crop is pointing at background: nothing along that line
                # is edge-shaped at all. Either the crop or the fit is wrong
                # and this search cannot say which, so the caller declines.
                unresolved.append(name)
            # _NO_CONSENSUS is the other answer and it is not the same one.
            # There *are* steps near the crop line, they just do not lie on a
            # line the search can place -- glare along one side, a busy
            # backdrop, a low-contrast cut. The re-search has produced nothing
            # better than the side already fitted from the image with
            # sub-pixel refinement, so that side stands, untouched and
            # unremarked. Declining here instead was measured: with a crop
            # 2.5-3.0mm proud of the card -- ordinary slop from a crop traced
            # by finger -- it threw away 22 of 37 real photographs that fitted
            # perfectly well, because on a fifth of sides fewer than half the
            # normals in a 4mm band agree on where the edge is. A crop that
            # merely fails to corroborate the fit is not evidence against it;
            # AGENTS.md's invariant is that the geometry comes from the fitted
            # edges, and this is what that means when the re-search is
            # inconclusive.
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
            # corner: discard the whole refit rather than half of it, and
            # report every side that was searched -- successfully or not --
            # as unresolved, since none of their search results are being
            # used.
            return CropRefit(
                geometry=fitted,
                moved={},
                unresolved=tuple(sorted(set(unresolved) | set(moved.keys()))),
            )
        apexes.append(point)

    # A fit can be individually sane per side and still produce a nonsense
    # quad (the same reasoning `fit_card_geometry` guards with) -- here
    # doubly so, since only one or two sides may have moved while the others
    # anchor the intersection. Guard the re-intersected apexes against the
    # *pre-refit* fit, not the crop: a crop is what triggered the search, not
    # what the result is allowed to agree with.
    pre_refit_apexes = _order_quad(fitted.apexes)
    pre_refit_centre = pre_refit_apexes.mean(axis=0)
    span = float(np.max(np.linalg.norm(pre_refit_apexes - pre_refit_centre, axis=1)))
    new_apexes = _order_quad(np.array(apexes, dtype=np.float64))
    if np.max(np.linalg.norm(new_apexes - pre_refit_apexes, axis=1)) > 0.25 * span:
        return CropRefit(
            geometry=fitted,
            moved={},
            unresolved=tuple(sorted(set(unresolved) | set(moved.keys()))),
        )

    refitted = CardGeometry(
        apexes=new_apexes,
        sides=sides,
        # Still "ransac": every side here came from a line fitted to the image.
        method=fitted.method,
    )
    return CropRefit(geometry=refitted, moved=moved, unresolved=tuple(sorted(unresolved)))
