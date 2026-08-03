"""How good the photograph is, before asking what the card is like.

The dominant error term in this pipeline is capture variance, not algorithm
choice. A soft, tilted, glared phone photo will defeat any corner detector, and
producing a confident number from one is worse than producing none -- so these
metrics exist to let each category decide whether it can honestly answer.

Everything is measured over the **deskewed card region only**. Including the
scanner backing or a cluttered desk would let the surroundings decide the
verdict on the card: dark backing drags illumination uniformity around, and a
busy background inflates a sharpness score that says nothing about the subject.

Each metric answers one question:

    sharpness      is there enough detail to see a frayed corner at all?
    px_per_mm      is the card big enough in frame for that detail to exist?
    clipping       has glare blown out part of the surface?
    uniformity     is one side of the card lit differently from the other?

Nothing here decides anything. The thresholds live with the categories that
consume them, because "sharp enough" means something different for centering
(a border position) than for corners (a few tenths of a millimetre of wear).

**Only px_per_mm is currently used to gate anything, and the fixture set is
why.** Measured across the catalogue, the other three turn out to track what
is printed on the card at least as strongly as they track the photograph:

    illumination_uniformity   pokemon_back        0.353
                              capture_glared      0.291   <- actual glare
                              white_border_clean  0.204   <- evenly lit!

    A perfectly-lit white-bordered card scores *worse* than the card with real
    glare, because a bright border around dark art is a genuine low-frequency
    luminance structure and no low-frequency measure can tell it apart from
    one-sided lighting. Thresholding on this would reliably flag the wrong
    card.

    sharpness (Tenengrad)     capture_soft            84
                              full_art_centered      284   <- in focus
                              pokemon_back           616
                              foil_bordered         3412   <- in focus
                              capture_low_resolution 2339   <- 7 px/mm

    Foil scores 5x a plain card at identical focus, uniform artwork scores low
    because it has few edges to find, and *downscaling raises the score*
    because it sharpens the edges that remain. Any absolute threshold catching
    the soft fixture without libelling the full-art one is a band too narrow
    to trust.

    clipping_fraction         capture_glared      0.000   <- actual glare
                              pokemon_front       0.001
                              foil_bordered       0.005

    Not a flaw in the metric -- the synthetic glare is an alpha blend topping
    out at 246, so nothing in it is clipped, while a printed white border
    genuinely does reach 255. It means only that the fixture set cannot
    validate this one; see tests/test_capture.py, which tests it on
    constructed pixels instead.

Both become usable once there is a reference image to compare against (the
registration work later in the brief): the question "is this darker on one
side than it should be" is answerable, where "is this darker on one side" is
not. Until then they are recorded and drift-tracked, not acted on -- an
honest diagnostic beats a confident misfire.

px_per_mm has no such problem. It is a physical fact about how much of the
sensor the card occupied, and means the same on every card ever printed.
"""

import cv2
import numpy as np

# --- Resolution gates -------------------------------------------------------
# The one capture metric that is content-independent, so the one worth acting
# on. Corner and edge wear are features of roughly 0.5-2mm; how many pixels
# cover them decides whether they are visible at all.
#
# REASONED. Below the floor a 0.5mm feature spans about three pixels, which is
# indistinguishable from compression noise -- there is nothing to measure and
# saying so is the only honest answer. Between floor and comfortable it spans
# six to twelve, which is enough to detect gross damage but not to grade it,
# so those categories keep scoring at reduced confidence.
#
# The comfortable figure follows the brief's ~25 px/mm, below which corner
# wear stops being reliably visible. The floor is set well under it so that a
# usable-but-modest capture still gets an answer rather than a refusal.
RESOLUTION_FLOOR_PX_PER_MM = 12.0
RESOLUTION_COMFORTABLE_PX_PER_MM = 25.0


def tenengrad(gray: np.ndarray) -> float:
    """Mean squared Sobel gradient magnitude -- a focus measure.

    Preferred over variance-of-Laplacian, which the codebase already computes
    in surface.py: the Laplacian is a second derivative and squares the noise
    along with the signal, so on a grainy phone photo it reports high values
    for what is actually sensor noise. Tenengrad's first-derivative response
    is markedly steadier on the noisy fixture.

    Scale-dependent by nature, so it is only meaningful next to px_per_mm --
    a downscaled image has fewer, sharper-looking edges.
    """
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    return float(np.mean(gx * gx + gy * gy))


def clipping_fraction(image: np.ndarray, threshold: int = 250) -> float:
    """Fraction of pixels at or near saturation in any channel.

    On foil this doubles as the glare metric: a blown highlight and a
    specular flare are the same measurement. Where this is high, surface
    analysis is reading a white patch rather than a card.
    """
    return float(np.mean(image.max(axis=2) >= threshold))


def illumination_uniformity(gray: np.ndarray) -> float:
    """How evenly the card is lit, as 1.0 (perfectly even) down towards 0.

    Taken from a heavily blurred luminance surface so that artwork -- which is
    supposed to vary -- does not read as uneven lighting. What remains at that
    blur is the low-frequency lighting gradient.

    One-sided lighting manufactures phantom surface defects and biases every
    saturation comparison the corner and edge detectors make, because both
    compare a region against a neighbouring reference that is now lit
    differently.
    """
    # Blur radius scales with the card so the measure means the same thing at
    # any resolution.
    radius = max(3, int(min(gray.shape[:2]) * 0.10) | 1)
    smooth = cv2.GaussianBlur(gray.astype(np.float32), (radius, radius), 0)
    lo, hi = float(np.percentile(smooth, 5)), float(np.percentile(smooth, 95))
    if hi <= 0:
        return 0.0
    # Percentiles rather than min/max: a single dark pixel should not decide
    # that the lighting is uneven.
    return float(max(0.0, 1.0 - (hi - lo) / hi))


def measure_capture(card: np.ndarray, px_per_mm: float) -> dict:
    """Every capture metric for one deskewed card.

    `card` must already be cropped to the card -- see the module docstring on
    why the backing must not be included.
    """
    gray = cv2.cvtColor(card, cv2.COLOR_BGR2GRAY)
    return {
        "px_per_mm": round(float(px_per_mm), 2),
        "sharpness": round(tenengrad(gray), 1),
        "clipping_fraction": round(clipping_fraction(card), 4),
        "illumination_uniformity": round(illumination_uniformity(gray), 3),
    }


def resolution_limitation(px_per_mm: float | None) -> tuple[str | None, bool]:
    """How the capture's resolution constrains a fine-detail category.

    Returns (limitation_code, is_unmeasurable). None/False means the capture
    is good enough to say nothing about.

    Shared by corners and edges so the two cannot drift apart on what "too
    small" means -- they measure features of the same scale and should agree.
    Centering deliberately does not use this: a border's *position* is a
    coarse measurement that survives a small image, which is exactly the
    per-category gating the brief asks for rather than one verdict on the
    whole photograph.

    A missing px_per_mm means the caller did not supply one, so nothing is
    claimed -- silence beats guessing at the scale.
    """
    from zgrader.analysis import assessment

    if px_per_mm is None:
        return None, False
    if px_per_mm < RESOLUTION_FLOOR_PX_PER_MM:
        return assessment.CAPTURE_TOO_LOW_RESOLUTION, True
    if px_per_mm < RESOLUTION_COMFORTABLE_PX_PER_MM:
        return assessment.CAPTURE_MODEST_RESOLUTION, False
    return None, False
