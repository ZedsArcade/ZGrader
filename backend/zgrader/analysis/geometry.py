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
