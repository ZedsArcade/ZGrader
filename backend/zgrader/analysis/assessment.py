"""What a score is worth, alongside the score itself.

A bare "corners: 7.5" is a claim the pipeline often cannot support. The same
number means something quite different on a sharp 1200dpi flatbed scan of a
black-bordered card than on a soft phone photo of a white-bordered one, and
until now nothing in the output said so.

Every category therefore carries an `assessment` block next to its
measurements:

    state         measured | unmeasurable
    confidence    0.0-1.0
    score_low     bottom of the plausible range
    score_high    top of it
    limitations   codes naming what specifically constrained this reading

Two decisions worth not undoing:

**Limitations are codes, not sentences.** Region notes are localised at
analysis time and stored as text, which means changing the wording needs a
re-analysis and a card analysed in Spanish is stuck in Spanish forever.
Storing codes lets the language be chosen when the page is rendered.

**`unmeasurable` is a state, not a low score.** "We looked and it is bad" and
"we could not tell" are different answers, and collapsing them into 0.0 is the
kind of confident wrongness this whole rework exists to remove. The state is
defined here from the outset so the contract does not change twice, but
nothing emits it until `AnalysisResult.raw_score` becomes nullable -- a NOT
NULL column cannot represent "no score", which is the point.
"""

import dataclasses

# --- Limitation codes -------------------------------------------------------
# Rendered through reports/strings.py and the frontend dictionaries, so adding
# one here means adding copy in both languages. That coupling is deliberate: a
# limitation nobody wrote words for should not reach a customer.
# ----------------------------------------------------------------------------

#: Flatbed and phone lighting is diffuse; graders use raking light.
SURFACE_DIFFUSE_LIGHT = "surface_diffuse_light"
#: Corners are assessed for discolouration only -- material loss is not measured.
CORNERS_WHITENING_ONLY = "corners_whitening_only"
#: Whitening is a loss of saturation, so a pale or white border has little to lose.
CORNERS_PALE_BORDER = "corners_pale_border"
#: No clean printed border was found -- full-art, or artwork bleeding to the edge.
CENTERING_NO_FRAME = "centering_no_frame"
#: A printed frame was found on some sides but not all of them.
CENTERING_PARTIAL_FRAME = "centering_partial_frame"
#: One or more edges could not be sampled and were left out of the score.
EDGES_PARTIAL = "edges_partial"
#: The printed border is too narrow to sample clean card beside the cut.
EDGES_THIN_BORDER = "edges_thin_border"
#: The card occupies too few pixels for wear of this scale to exist in the image.
CAPTURE_TOO_LOW_RESOLUTION = "capture_too_low_resolution"
#: Enough resolution to spot gross damage, not enough to grade it finely.
CAPTURE_MODEST_RESOLUTION = "capture_modest_resolution"
#: The card's edges could not be fitted, so the boundary is the supplied crop.
GEOMETRY_UNVERIFIED = "geometry_unverified"
#: What was measured is not the shape of a card, so its scale is wrong.
GEOMETRY_ASPECT_MISMATCH = "geometry_aspect_mismatch"

ALL_LIMITATION_CODES = (
    SURFACE_DIFFUSE_LIGHT,
    CORNERS_WHITENING_ONLY,
    CORNERS_PALE_BORDER,
    CENTERING_NO_FRAME,
    CENTERING_PARTIAL_FRAME,
    EDGES_PARTIAL,
    EDGES_THIN_BORDER,
    CAPTURE_TOO_LOW_RESOLUTION,
    CAPTURE_MODEST_RESOLUTION,
    GEOMETRY_UNVERIFIED,
    GEOMETRY_ASPECT_MISMATCH,
)

MEASURED = "measured"
UNMEASURABLE = "unmeasurable"

# --- Confidence ------------------------------------------------------------
# ARBITRARY, every one of them. There is no labelled set to fit against, so
# these encode a ranking we can defend in words -- centering measured off a
# clean printed border is the most trustworthy thing here; surface under
# diffuse light is the least -- rather than a probability anyone measured.
#
# They are collected here so that ranking is visible in one place and can be
# argued with, instead of being implied by four unrelated flag strings.
# ----------------------------------------------------------------------------

CONFIDENCE_CENTERING_CLEAN_FRAME = 0.9
CONFIDENCE_CENTERING_NO_FRAME = 0.2
#: A frame on some sides only. The ratio still comes from real borders, but
#: one of the two axes may rest on a single confident side.
CONFIDENCE_CENTERING_PARTIAL_FRAME = 0.6
#: Corners now measure material loss in mm^2 as well as discolouration, which
#: is a physical quantity against a known apex rather than a colour comparison.
#: That is a materially better position than the whitening-only reading this
#: number described before, hence the rise.
CONFIDENCE_CORNERS = 0.8
#: No card mask, so discolouration is all there was.
CONFIDENCE_CORNERS_WHITENING_ONLY = 0.55
#: Pale border *and* no material measurement -- the old worst case, where the
#: only channel available is the one the border defeats.
CONFIDENCE_CORNERS_PALE_BORDER = 0.35
#: Pale border but material loss measured. One channel of two is weak, which is
#: a far better position than the line above and should not be scored as if it
#: were the same.
CONFIDENCE_CORNERS_PALE_BORDER_WITH_MATERIAL = 0.6
CONFIDENCE_EDGES = 0.75
CONFIDENCE_EDGES_PARTIAL = 0.4
#: Border too narrow for a photometric reference, so the edge rests on its
#: geometric channel alone. Lower than a full reading, well above a guess --
#: the shape measurement is real and is the one that works on a colourless
#: border.
CONFIDENCE_EDGES_THIN_BORDER = 0.5
CONFIDENCE_SURFACE = 0.4

#: Applied to corners and edges on a modest capture. Multiplicative rather than
#: absolute, so it compounds with whatever else already limited the reading --
#: a white-bordered card photographed small is worse than either alone, and a
#: fixed value would hide that.
CONFIDENCE_MODEST_RESOLUTION_FACTOR = 0.6

#: Applied when the card's boundary could not be fitted and a supplied crop
#: stands in for it. ARBITRARY, and deliberately harsh: every distance these
#: categories measure is measured *from* that boundary, so if it is in the
#: wrong place the reading is not merely noisier, it is measuring a different
#: line. Kept above zero because a hand-placed crop is usually close.
CONFIDENCE_UNVERIFIED_GEOMETRY_FACTOR = 0.5

#: Applied when the measured region is not card-shaped. Harsher still: the
#: aspect error means the pixel-to-millimetre scale is wrong on at least one
#: axis, so every figure in millimetres is wrong by a factor nobody knows.
CONFIDENCE_ASPECT_MISMATCH_FACTOR = 0.35

#: ARBITRARY. Below this mean CIELAB chroma in a corner's reference region, the
#: border has too little colour for "lost colour" to register -- the documented
#: blind spot for white-bordered cards. A white border sits near 0-5.
#:
#: Chroma, not HSV saturation: corners.py now measures whitening in Lab, where
#: lightness and colourfulness are separate axes. Saturation conflated them,
#: so a dark border scored as pale on a scale meant to detect colourless ones.
PALE_BORDER_CHROMA = 25.0

#: At zero confidence the interval spans this far either side of the score.
#: Chosen so 0.9 confidence gives roughly +/-0.5 and 0.4 gives +/-3.0 -- wide
#: enough that a low-confidence reading visibly refuses to commit.
MAX_INTERVAL_HALF_WIDTH = 5.0


@dataclasses.dataclass(frozen=True)
class Assessment:
    state: str
    confidence: float
    score_low: float | None
    score_high: float | None
    limitations: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "state": self.state,
            "confidence": round(self.confidence, 2),
            "score_low": self.score_low,
            "score_high": self.score_high,
            "limitations": list(self.limitations),
        }


def interval_for(score: float, confidence: float) -> tuple[float, float]:
    """The plausible range around a score, widening as confidence drops.

    The brief's point: "Corners 8.5-9.5, confidence 0.7" is defensible where
    "Corners: 9" is a claim we cannot support and a customer will screenshot
    when the card comes back an 8.
    """
    half = (1.0 - confidence) * MAX_INTERVAL_HALF_WIDTH
    return (round(max(0.0, score - half), 2), round(min(10.0, score + half), 2))


def measured(score: float, confidence: float, limitations: tuple[str, ...] = ()) -> Assessment:
    low, high = interval_for(score, confidence)
    return Assessment(
        state=MEASURED,
        confidence=confidence,
        score_low=low,
        score_high=high,
        limitations=limitations,
    )


#: How much each limitation that can be discovered *outside* a category costs
#: that category's confidence. Kept as data so pipeline.py applies them in one
#: pass rather than every analyser learning about geometry.
EXTERNAL_LIMITATION_FACTORS = {
    GEOMETRY_UNVERIFIED: CONFIDENCE_UNVERIFIED_GEOMETRY_FACTOR,
    GEOMETRY_ASPECT_MISMATCH: CONFIDENCE_ASPECT_MISMATCH_FACTOR,
}


def with_limitations(
    block: dict | None, codes: tuple[str, ...], score: float | None = None
) -> dict | None:
    """Attach limitations discovered after a category finished measuring.

    Geometry is established once per scan, not once per category, so threading
    it into all four analysers would put the same argument in four signatures
    to be used the same way. This applies it in one place instead.

    Confidence is multiplied, never overwritten -- a card whose corners were
    already only a whitening estimate and whose boundary is also unverified is
    worse off than either alone. An unmeasurable block keeps its zero
    confidence and simply gains the codes: there is no reading to devalue, but
    the reasons still belong in the record.
    """
    if block is None or not codes:
        return block

    updated = dict(block)
    updated["limitations"] = sorted(set(block.get("limitations", ())) | set(codes))
    if block["state"] != MEASURED:
        return updated

    confidence = block["confidence"]
    for code in codes:
        confidence *= EXTERNAL_LIMITATION_FACTORS.get(code, 1.0)
    updated["confidence"] = round(confidence, 2)
    # The interval has to follow the confidence, or a reading whose trust just
    # halved keeps advertising the same precision. It is recomputed from the
    # score rather than from the old interval's midpoint, because the interval
    # is clamped to 0-10 and a score near either end is not at its midpoint.
    if score is not None:
        updated["score_low"], updated["score_high"] = interval_for(score, confidence)
    return updated


def unmeasurable(limitations: tuple[str, ...]) -> Assessment:
    """No score at all, and a reason why.

    Confidence is zero and there is no interval: an interval implies a score
    exists somewhere inside it, which is exactly the claim being declined.
    """
    return Assessment(
        state=UNMEASURABLE,
        confidence=0.0,
        score_low=None,
        score_high=None,
        limitations=limitations,
    )
