"""Locate the physical card in a flatbed scan and deskew/crop to its exact
boundary, so downstream analysis (centering/corners/edges/surface) operates
on a straightened, edge-to-edge image of just the card.
"""

from pathlib import Path

import cv2
import numpy as np

# See detect_boundary's docstring for why this specific ratio distinguishes
# genuine keystone perspective from local corner damage/noise.
_QUAD_AREA_RATIO_THRESHOLD = 0.95


def load_image(path: str | Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read image: {path}")
    return image


def _largest_contour(binary: np.ndarray) -> np.ndarray | None:
    # CHAIN_APPROX_NONE, not SIMPLE. SIMPLE compresses a straight run to its
    # two endpoints, which is exactly the wrong thing here: a cleanly cut card
    # is mostly straight runs, so its boundary arrived as a handful of points
    # and geometry.py had nothing to fit a line through. The corner and area
    # figures derived below are identical either way; this only keeps the
    # points in between, which is where edge roughness lives.
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    return max(contours, key=cv2.contourArea)


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def warp_to_points(image: np.ndarray, box: np.ndarray) -> np.ndarray:
    """Perspective-warp `image` so the quadrilateral `box` (4 points, any
    order) becomes an axis-aligned rectangle. The homography corrects in-plane
    rotation and true keystone/perspective distortion together, so a separate
    "deskew"/"tilt" step is unnecessary once real corner points are known.

    **Not the analysis path.** The output size comes from the quad's own edge
    lengths, so px/mm varies per scan and the card's true 63:88 aspect is never
    imposed -- `rectify` exists because both of those matter. This remains for
    the crop-preview and boundary-suggestion flows, which want to show a user
    exactly the quad they supplied.
    """
    rect = _order_points(box)
    (tl, tr, br, bl) = rect
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = max(int(width_a), int(width_b))
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = max(int(height_a), int(height_b))
    if max_width < 2 or max_height < 2:
        raise ValueError("Detected card region is too small to be a real card")
    dst = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, matrix, (max_width, max_height))


#: A candidate reaching this close to every image border, as a fraction of the
#: image's own dimensions, is the photograph rather than anything in it.
_FRAME_SPAN_FRACTION = 0.98


def _spans_whole_frame(contour: np.ndarray, image_w: int, image_h: int) -> bool:
    """Whether a candidate is really just the whole photograph.

    The aspect test cannot catch this one, and the reason is unlucky
    arithmetic: a 3000x4000 phone frame has an aspect of 0.750 against a card's
    0.716, which is under 5% out. The frame is card-shaped.

    What separates them is margin. A card photographed with any background
    visible around it does not reach the edge of the frame on all four sides;
    the frame does, by definition. One real shot detected a region of
    2999x3999 in a 3000x4000 image and every measurement downstream was taken
    against the photograph's own border.
    """
    x, y, w, h = cv2.boundingRect(contour.astype(np.int32))
    return (
        w >= image_w * _FRAME_SPAN_FRACTION
        and h >= image_h * _FRAME_SPAN_FRACTION
    )


#: Morphological closing kernel for the rescue pass, as a fraction of the
#: image's shorter side. Big enough to bridge a glare split, small enough not
#: to weld the card to its surroundings -- see the rescue branch below.
_RESCUE_CLOSE_FRACTION = 0.005

#: Area floor for the rescue pass. The ordinary 15% assumes the card fills a
#: good part of the frame; a deliberately distant shot does not.
_RESCUE_MIN_AREA_FRACTION = 0.05


def _aspect_error(contour: np.ndarray, expected_aspect: float) -> float:
    """How far a candidate region's shape is from a card's, as a fraction.

    Orientation-agnostic: a card photographed sideways is still a card, so the
    reciprocal is tried too and the better of the two wins.
    """
    (_cx, _cy), (rw, rh), _angle = cv2.minAreaRect(contour)
    if rw <= 0 or rh <= 0:
        return float("inf")
    observed = rw / rh
    return min(
        abs(observed / expected_aspect - 1.0),
        abs((1.0 / observed) / expected_aspect - 1.0),
    )


def detect_boundary(
    image: np.ndarray,
    min_area_fraction: float = 0.15,
    max_area_fraction: float = 0.95,
    expected_aspect: float | None = None,
) -> tuple[np.ndarray, dict]:
    """Find the card's outer boundary and return its 4 corner points (any
    order) plus info about the detected contour, for annotation/debugging
    and as the starting suggestion for the manual crop-adjust UI.

    Tries both light-on-dark and dark-on-light thresholding since scanner
    backing (scanner lid open/closed, black backing sheet, etc.) varies. A
    contour spanning nearly the whole canvas is rejected -- that's the
    background winning under the wrong polarity, not the card (a real card
    scan always has some backing margin visible around it).

    Thresholds on the HSV Value channel (max of B/G/R) rather than
    luminance-weighted grayscale: a card's own border/interior regions can
    have very different luma (e.g. a blue-heavy border is "dark" under the
    standard luma formula, which heavily weights green) even though neither
    is remotely as dark as true black scanner backing on every channel. Value
    keeps the whole card in one bright cluster against a near-zero backing.

    Corner extraction tries cv2.approxPolyDP first, which can capture a
    contour's true 4-point quadrilateral (including real perspective/keystone
    distortion from a handheld photo, not just in-plane rotation); if the
    contour doesn't simplify to exactly 4 points (noisy edges, rounded
    corners), falls back to cv2.minAreaRect's best-fit rotated rectangle.
    """
    value_channel = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 2]
    blurred = cv2.GaussianBlur(value_channel, (5, 5), 0)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    image_h, image_w = image.shape[:2]
    image_area = image_h * image_w
    candidates: list[tuple[float, np.ndarray]] = []
    for candidate_binary in (binary, cv2.bitwise_not(binary)):
        contour = _largest_contour(candidate_binary)
        if contour is None:
            continue
        area = cv2.contourArea(contour)
        if not (image_area * min_area_fraction <= area <= image_area * max_area_fraction):
            continue
        if _spans_whole_frame(contour, image_w, image_h):
            continue
        candidates.append((area, contour))

    if not candidates:
        # Nothing qualified on the first pass. Before giving up, try again with
        # the threshold mask closed and the area floor relaxed.
        #
        # Both exist for one real photograph, and each half was necessary. A
        # distant shot with flash glare put the card at 11.8% of the frame,
        # under the 15% floor -- that floor assumes the card fills a good part
        # of the picture, which a "far" shot does not. And glare had split the
        # card into pieces, so its largest fragment measured 1441x1414, an
        # aspect of 0.981 that is not a card at all. Closing at 0.5% of the
        # frame rejoins them into 2119x1542, aspect 0.727 against a card's
        # 0.716 -- a 1.5% match. Larger kernels over-merge, bridging the card
        # to whatever is beside it (0.946 at 1%, 0.960 at 2%).
        #
        # This runs only when the ordinary path finds nothing, so it changes no
        # existing behaviour: the closed contour is smoother than the real
        # boundary, which matters to the sub-pixel edge fit, and that cost is
        # worth paying only when the alternative is refusing the submission
        # outright.
        kernel = max(3, int(round(min(image_h, image_w) * _RESCUE_CLOSE_FRACTION)) | 1)
        closed_kernel = np.ones((kernel, kernel), np.uint8)
        for candidate_binary in (binary, cv2.bitwise_not(binary)):
            closed = cv2.morphologyEx(candidate_binary, cv2.MORPH_CLOSE, closed_kernel)
            contour = _largest_contour(closed)
            if contour is None:
                continue
            area = cv2.contourArea(contour)
            if not (image_area * _RESCUE_MIN_AREA_FRACTION <= area <= image_area * max_area_fraction):
                continue
            if _spans_whole_frame(contour, image_w, image_h):
                continue
            candidates.append((area, contour))

    if not candidates:
        raise ValueError(
            "Could not locate a card-sized region in the scan -- check scanner "
            "backing contrast and that the card is fully within the scan bed."
        )

    # Pick the candidate that is most *card-shaped*, not the largest.
    #
    # Taking the largest assumes the card is the biggest bright thing in the
    # frame, which holds only when the background is darker than the card.
    # Measured on real photographs it frequently is not: a card at HSV value
    # 77 on a desk at 122 gave a "card" spanning 42% of the frame with an
    # aspect of 0.932, and one shot detected the entire photograph -- 93.9% of
    # the frame, aspect 0.750 -- which slipped under the area ceiling and was
    # then fitted happily, because a photograph's own edges are straight lines.
    #
    # Every downstream number inherited that: px/mm came out at ~47.5, which is
    # the frame width divided by 63mm rather than anything about the card, and
    # corners then measured 24mm^2 of "missing material" against a boundary
    # that was not the card's.
    #
    # The card's aspect ratio is known -- it is the one piece of information
    # about the subject we have for free -- so it decides. Area only breaks
    # ties between candidates that are equally card-shaped.
    if expected_aspect:
        _, contour = min(
            candidates, key=lambda c: (round(_aspect_error(c[1], expected_aspect), 2), -c[0])
        )
    else:
        _, contour = max(candidates, key=lambda c: c[0])

    rect_center, rect_size, rect_angle = cv2.minAreaRect(contour)
    rect_area = rect_size[0] * rect_size[1]

    perimeter = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
    # Only trust the quad if it's a real trapezoid, not just minAreaRect's
    # own rectangle with one corner nudged by local damage/noise. Genuine
    # keystone perspective shrinks the quad's area well below its enclosing
    # minAreaRect box (a photographed rectangle viewed at an angle is
    # visibly smaller than the upright rectangle that bounds it); pure
    # in-plane rotation, whitening, or even a small chipped/rounded corner
    # all keep quad_area/rect_area close to 1.0 -- verified empirically
    # against synthetic fixtures (rotation-only and whitened-corner cases
    # land at ~0.997, a hard-clipped corner at ~0.986, a true keystoned
    # photo at ~0.86). Falling back to minAreaRect in the near-1.0 cases
    # preserves corner-damage detection (which relies on the deskewed crop
    # still including the ideal corner tip, not one already traced tight
    # around missing material).
    quad_area = cv2.contourArea(approx) if len(approx) == 4 else 0.0
    if len(approx) == 4 and rect_area > 0 and quad_area / rect_area < _QUAD_AREA_RATIO_THRESHOLD:
        box = approx.reshape(4, 2).astype("float32")
        method = "quad"
    else:
        box = cv2.boxPoints((rect_center, rect_size, rect_angle))
        method = "min_area_rect"

    info = {
        "method": method,
        "rect_center": rect_center,
        "rect_size": rect_size,
        "rect_angle": rect_angle,
        "box_points": box.tolist(),
        "contour_area_px": float(cv2.contourArea(contour)),
        # The boundary itself, not just its four-point summary. geometry.py
        # fits a line to each side from these; the quad above only decides
        # which points belong to which side. Never persisted -- `info` is
        # discarded by every caller but this one.
        "contour": contour.reshape(-1, 2).astype(np.float64),
    }
    return box, info


def snap_points_to_boundary(
    image: np.ndarray, points: list[list[float]], tolerance_fraction: float = 0.06
) -> list[list[float]]:
    """Refine a user's 4 manual crop corners toward the auto-detected card
    boundary: each corner snaps to the matching detected corner only when
    it's within `tolerance_fraction * max(h, w)` pixels of it, so a
    deliberately-placed corner is preserved and only sloppy near-misses get
    cleaned up. Returns the 4 points (raw pixel space) in top-left,
    top-right, bottom-right, bottom-left order. If no card boundary can be
    detected, the input points are returned unchanged (ordered)."""
    ordered_user = _order_points(np.array(points, dtype="float32"))
    try:
        box, _info = detect_boundary(image)
    except ValueError:
        return ordered_user.tolist()

    ordered_detected = _order_points(box)
    h, w = image.shape[:2]
    tolerance = tolerance_fraction * max(h, w)

    snapped = []
    for user_pt, detected_pt in zip(ordered_user, ordered_detected):
        if np.linalg.norm(user_pt - detected_pt) <= tolerance:
            snapped.append(detected_pt.tolist())
        else:
            snapped.append(user_pt.tolist())
    return snapped


def locate_and_deskew(
    image: np.ndarray, min_area_fraction: float = 0.15, max_area_fraction: float = 0.95
) -> tuple[np.ndarray, dict]:
    """Convenience wrapper: detect the boundary and warp to it in one call.

    Predates `rectify` and shares its shortcomings (see warp_to_points): no
    canonical scale, no line fitting, no aspect correction. Kept because the
    migration backfill and a good deal of the test suite want a plain deskewed
    card without needing to know the physical dimensions. Nothing in the
    analysis pipeline should call it."""
    box, info = detect_boundary(image, min_area_fraction, max_area_fraction)
    return warp_to_points(image, box), info


# --- Canonical rectification -------------------------------------------------
#
# Everything above produces a card image whose size comes from the detected
# quad's own edge lengths, so px/mm varies per scan and the card's true
# 63:88 aspect -- a known physical fact -- is never used. What follows fixes
# both: the output raster is the card's real shape, and its scale is one
# number rather than an average of two axes that can disagree.

#: How far outside the supplied crop to look for the real card boundary, as a
#: fraction of the crop's size. Thresholding needs to see backing on both
#: sides of the edge, so the region of interest must contain some; a crop
#: placed exactly on the boundary would otherwise leave nothing to detect
#: against. Generous enough to recover a crop dragged well inside the card.
ROI_MARGIN_FRACTION = 0.10

#: Fractional deviation from the card's true aspect ratio beyond which the
#: measured region is reported as not card-shaped.
#:
#: ARBITRARY, but bounded by measurement rather than picked. Across the fixture
#: set the legitimate captures land at 0.0002-0.0005, the deliberately bad one
#: at 0.036, and the tilted one at 0.049 -- perspective survives the
#: opposite-edge averaging in _canonical_size more than expected, and that is
#: the number the threshold has to clear. At 0.12 it sits about 2.5x above the
#: worst honest fixture, which means it catches a crop wrong by roughly an
#: eighth of a card dimension (about 8mm across) and nothing subtler.
#:
#: That is a coarse net on purpose. It is a second signal, not the primary
#: one: a crop this pipeline could not verify already carries
#: GEOMETRY_UNVERIFIED regardless of its shape.
MAX_ASPECT_DEVIATION = 0.12


class RectifiedCard:
    """A deskewed card plus the provenance of the geometry that produced it.

    `px_per_mm` here is exact rather than inferred: the output raster was
    *built* at that scale from the card's known physical size, so it is no
    longer an average of two axis measurements that a bad crop can pull apart.

    `mask` is where the card's material actually is, in the same canonical
    space as `image`. Because the raster is the card's *ideal* rectangle, any
    zero in that mask is material the card should have and does not -- which
    is what makes corner loss measurable in mm^2 rather than as a fraction of
    an arbitrary box. It is None when detection failed and a supplied crop
    stood in, because then there is no boundary to have found: nothing is
    claimed instead of claiming a perfect rectangle.
    """

    def __init__(
        self,
        image: np.ndarray,
        px_per_mm: float,
        geometry: dict,
        limitations: tuple[str, ...],
        mask: np.ndarray | None = None,
    ):
        self.image = image
        self.px_per_mm = px_per_mm
        self.geometry = geometry
        self.limitations = limitations
        self.mask = mask


def _expand_roi(quad: np.ndarray, shape: tuple[int, int]) -> tuple[int, int, int, int]:
    h, w = shape[:2]
    x0, y0 = quad.min(axis=0)
    x1, y1 = quad.max(axis=0)
    margin_x = (x1 - x0) * ROI_MARGIN_FRACTION
    margin_y = (y1 - y0) * ROI_MARGIN_FRACTION
    return (
        int(max(0, np.floor(x0 - margin_x))),
        int(max(0, np.floor(y0 - margin_y))),
        int(min(w, np.ceil(x1 + margin_x))),
        int(min(h, np.ceil(y1 + margin_y))),
    )


def _canonical_size(
    apexes: np.ndarray, width_mm: float, height_mm: float
) -> tuple[int, int, float, float, float]:
    """Output raster dimensions, its px/mm, and the observed aspect deviation.

    The scale is the *larger* of the two axes' observed resolutions, so the
    better-resolved axis is never thrown away -- a perspective warp resamples
    regardless, and discarding real detail to avoid interpolating some is the
    wrong trade.
    """
    tl, tr, br, bl = apexes
    # Opposite edges averaged rather than maxed: under perspective the near
    # edge is longer and the far edge shorter by roughly the same factor, so
    # the mean is much closer to the true dimension than either one.
    width_px = 0.5 * (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl))
    height_px = 0.5 * (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr))

    # A card scanned sideways is still a card. Without this the canonical
    # raster would squash a landscape capture into portrait and every
    # millimetre figure downstream would be wrong by the aspect ratio.
    if width_mm != height_mm:
        upright = abs((width_px / max(1e-6, height_px)) - (width_mm / height_mm))
        sideways = abs((width_px / max(1e-6, height_px)) - (height_mm / width_mm))
        if sideways < upright:
            width_mm, height_mm = height_mm, width_mm

    px_per_mm = max(width_px / width_mm, height_px / height_mm)
    observed_aspect = width_px / max(1e-6, height_px)
    expected_aspect = width_mm / height_mm
    deviation = abs(observed_aspect / expected_aspect - 1.0)

    out_w = max(2, int(round(width_mm * px_per_mm)))
    out_h = max(2, int(round(height_mm * px_per_mm)))
    return out_w, out_h, px_per_mm, deviation, expected_aspect


def rectify(
    image: np.ndarray,
    width_mm: float,
    height_mm: float,
    roi_quad: np.ndarray | None = None,
) -> RectifiedCard:
    """Deskew to a canonical raster, fitting the card's edges to find it.

    When `roi_quad` is given -- the customer's four dragged crop handles -- it
    is used as a *hint* about where to look, never as the geometry itself. The
    old behaviour warped straight to those handles, which made every
    measurement a function of where someone dropped a corner: half a
    millimetre inside the card and the damage is cropped away before anything
    sees it. The crop still does the job it exists for (rejecting background
    and neighbouring cards); it just no longer decides where the card's edges
    are.

    Falling back to the supplied quad is not silent. `limitations` carries
    GEOMETRY_UNVERIFIED, and the caller attaches it to the categories that
    depend on the boundary being right.
    """
    from zgrader.analysis import assessment, geometry

    offset = np.zeros(2)
    search = image
    if roi_quad is not None:
        roi_quad = np.asarray(roi_quad, dtype=np.float64).reshape(4, 2)
        x0, y0, x1, y1 = _expand_roi(roi_quad, image.shape)
        if x1 - x0 >= 8 and y1 - y0 >= 8:
            search = image[y0:y1, x0:x1]
            offset = np.array([x0, y0], dtype=np.float64)

    limitations: list[str] = []
    fitted = None
    material = None
    try:
        box, info = detect_boundary(
            search, expected_aspect=min(width_mm, height_mm) / max(width_mm, height_mm)
        )
        fitted = geometry.fit_card_geometry(search, info["contour"], box)
        # Where the card's material actually is, as one filled region. Built
        # from the *chosen contour* rather than from the raw threshold, so
        # dark artwork inside the card cannot read as a hole in it -- the only
        # question this mask has to answer is what is card and what is not.
        material = np.zeros(search.shape[:2], dtype=np.uint8)
        cv2.drawContours(
            material, [info["contour"].round().astype(np.int32)], -1, 255, thickness=-1
        )
    except ValueError:
        box = None

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
    elif roi_quad is not None:
        # Detection failed inside the region of interest, or the fit was not
        # trustworthy. The customer's crop is the only geometry left, so it
        # stands -- and every category that depends on the boundary is told
        # that is what happened.
        apexes = _order_points(roi_quad.astype("float32")).astype(np.float64)
        geometry_block = {"method": "user_crop", "apexes": apexes.round(2).tolist(), "sides": {}}
        limitations.append(assessment.GEOMETRY_UNVERIFIED)
    elif box is not None:
        apexes = _order_points(box).astype(np.float64) + offset
        geometry_block = {"method": "coarse_quad", "apexes": apexes.round(2).tolist(), "sides": {}}
        limitations.append(assessment.GEOMETRY_UNVERIFIED)
    else:
        raise ValueError(
            "Could not locate a card-sized region in the scan -- check scanner "
            "backing contrast and that the card is fully within the scan bed."
        )

    out_w, out_h, px_per_mm, deviation, expected = _canonical_size(apexes, width_mm, height_mm)
    if deviation > MAX_ASPECT_DEVIATION:
        # The region being measured is not the shape of a card. Usually a crop
        # placed short on one axis; occasionally a detection that caught the
        # scanner lid. Either way every millimetre figure derived from it is
        # scaled wrong, and saying so beats reporting them to two decimals.
        limitations.append(assessment.GEOMETRY_ASPECT_MISMATCH)

    destination = np.array(
        [[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], dtype="float32"
    )
    matrix = cv2.getPerspectiveTransform(apexes.astype("float32"), destination)
    card = cv2.warpPerspective(image, matrix, (out_w, out_h))

    canonical_mask = None
    if material is not None:
        # The mask is warped in the ROI's own coordinates, so it needs the
        # homography composed with the crop offset rather than the homography
        # alone -- otherwise it lands displaced by the crop and every corner
        # reads as destroyed.
        shift = np.array(
            [[1.0, 0.0, -offset[0]], [0.0, 1.0, -offset[1]], [0.0, 0.0, 1.0]], dtype="float64"
        )
        # INTER_NEAREST: this is a label image, and interpolating between
        # "card" and "not card" invents a fringe of half-material around every
        # edge, which at a corner is exactly the quantity being measured.
        canonical_mask = cv2.warpPerspective(
            material, (matrix @ shift).astype("float32"), (out_w, out_h), flags=cv2.INTER_NEAREST
        )

    geometry_block["px_per_mm"] = round(float(px_per_mm), 3)
    geometry_block["aspect_deviation"] = round(float(deviation), 4)
    geometry_block["expected_aspect"] = round(float(expected), 4)
    return RectifiedCard(
        card, float(px_per_mm), geometry_block, tuple(limitations), canonical_mask
    )
