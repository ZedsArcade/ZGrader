"""Where the printed border ends and the artwork begins.

Two categories need this and for different reasons, which is why it is neither
of theirs:

* **edges** needs it to know how far in it can sample clean card as a
  reference. Getting it wrong made an undamaged white-bordered card score
  0.00/10, because the reference landed on artwork and the ordinary difference
  between a border and the art it frames read as whitening.
* **centering** needs it because it *is* the measurement. The width of the
  printed border on each of the four sides, compared left-to-right and
  top-to-bottom, is what centering means.

They were about to grow separate copies. `analysis/scoring.py` exists because
two modules computing the same number in two places drift apart silently, and
this is the same hazard one layer down.

WHY A COLOUR PROFILE RATHER THAN A GRADIENT PEAK
------------------------------------------------
Centering previously took the strongest Laplacian response within a search
window. That finds *an* edge, not necessarily the border: card text, a set
symbol, a holo pattern or a bright element of artwork all produce strong
gradients, and the brightest one wins regardless of what it is. On a card with
no border at all it returns the argmax of noise, which is a confident number
about nothing.

Departure from the border's own colour is a better question. The border is a
large, uniform, printed region hard against the cut; the artwork is not. Asking
"how far in does the colour stop matching the border" is answerable, and when
the answer is "it never matched anything" that is real information rather than
a silent failure.
"""

import numpy as np

#: How far inward to look. Comfortably past any real card's border without
#: reaching the middle of the artwork.
MAX_SEARCH_MM = 12.0

#: Skipped before sampling the border's own colour. The outermost sliver is
#: exactly the part that frays, so including it would let a badly whitened edge
#: define "normal" for itself.
SAMPLE_INSET_MM = 0.6

#: How much card, just past the inset, establishes the border colour.
COLOUR_SAMPLE_MM = 0.5

#: ARBITRARY. Colour step, in 8-bit Lab units, that marks the transition.
#: Measured across the fixture set the real steps are enormous -- 112 and 192
#: in lightness alone -- so this only has to clear within-border variation,
#: which on a real photograph is the noisier quantity.
TRANSITION_DELTA_E = 25.0


def edge_band(lab: np.ndarray, name: str, exclusion: float, depth_px: int) -> np.ndarray:
    """A band along one edge, oriented so axis 0 is depth inward from the cut
    and axis 1 runs along the edge.

    The flips are what let one analysis function serve all four edges, exactly
    as corners.corner_crops does for corners.
    """
    h, w = lab.shape[:2]
    ex_h, ex_w = int(h * exclusion), int(w * exclusion)
    depth_px = max(2, min(depth_px, h // 2, w // 2))

    if name == "top":
        return lab[0:depth_px, ex_w : w - ex_w]
    if name == "bottom":
        return lab[h - depth_px : h, ex_w : w - ex_w][::-1]
    if name == "left":
        return np.transpose(lab[ex_h : h - ex_h, 0:depth_px], (1, 0, 2))
    return np.transpose(lab[ex_h : h - ex_h, w - depth_px : w][:, ::-1], (1, 0, 2))


def border_colour(band: np.ndarray, px_per_mm: float) -> np.ndarray | None:
    """The border's own Lab colour, taken just inside the fraying zone.

    Median along the edge, so a defect at one position cannot move it: this is
    a question about how the card was printed, not about its wear.
    """
    inset = max(1, int(round(SAMPLE_INSET_MM * px_per_mm)))
    if band.shape[0] <= inset + 2 or band.shape[1] < 1:
        return None
    profile = np.median(band, axis=1)
    width = max(2, int(round(COLOUR_SAMPLE_MM * px_per_mm)))
    return np.median(profile[inset : inset + width], axis=0)


def transition_depth_px(band: np.ndarray, px_per_mm: float) -> int | None:
    """One depth for the whole edge, from its median profile.

    None means no transition within the search window -- a full-art card, where
    artwork runs to the cut. That is a real answer: for edges it means the
    reference is adjacent artwork, which is still a valid local comparison.
    """
    inset = max(1, int(round(SAMPLE_INSET_MM * px_per_mm)))
    reference = border_colour(band, px_per_mm)
    if reference is None:
        return None

    profile = np.median(band, axis=1)
    delta = np.linalg.norm(profile - reference, axis=1)
    beyond = np.nonzero(delta[inset:] > TRANSITION_DELTA_E)[0]
    if not len(beyond):
        return None
    return int(beyond[0] + inset)


def transition_depths(band: np.ndarray, px_per_mm: float) -> np.ndarray:
    """The transition depth at *every position* along the edge, as a float
    array with NaN where none was found.

    This is what centering needs and the median version cannot give: a single
    depth per side hides whether the border runs parallel to the cut. A card
    printed straight but trimmed at an angle -- a diamond cut, which graders
    penalise on its own -- has a border that widens steadily along the side,
    and its median looks like a perfectly ordinary centred card.
    """
    inset = max(1, int(round(SAMPLE_INSET_MM * px_per_mm)))
    reference = border_colour(band, px_per_mm)
    if reference is None:
        return np.full(band.shape[1] if band.ndim == 3 else 0, np.nan)

    delta = np.linalg.norm(band - reference, axis=2)
    beyond = delta > TRANSITION_DELTA_E
    beyond[:inset] = False

    found = beyond.any(axis=0)
    depths = np.where(found, np.argmax(beyond, axis=0).astype(np.float64), np.nan)
    return depths
