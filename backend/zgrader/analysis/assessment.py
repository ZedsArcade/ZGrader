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
#: One or more edges could not be sampled and were left out of the score.
EDGES_PARTIAL = "edges_partial"
#: The card occupies too few pixels for wear of this scale to exist in the image.
CAPTURE_TOO_LOW_RESOLUTION = "capture_too_low_resolution"
#: Enough resolution to spot gross damage, not enough to grade it finely.
CAPTURE_MODEST_RESOLUTION = "capture_modest_resolution"

ALL_LIMITATION_CODES = (
    SURFACE_DIFFUSE_LIGHT,
    CORNERS_WHITENING_ONLY,
    CORNERS_PALE_BORDER,
    CENTERING_NO_FRAME,
    EDGES_PARTIAL,
    CAPTURE_TOO_LOW_RESOLUTION,
    CAPTURE_MODEST_RESOLUTION,
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
CONFIDENCE_CORNERS = 0.7
CONFIDENCE_CORNERS_PALE_BORDER = 0.35
CONFIDENCE_EDGES = 0.75
CONFIDENCE_EDGES_PARTIAL = 0.4
CONFIDENCE_SURFACE = 0.4

#: Applied to corners and edges on a modest capture. Multiplicative rather than
#: absolute, so it compounds with whatever else already limited the reading --
#: a white-bordered card photographed small is worse than either alone, and a
#: fixed value would hide that.
CONFIDENCE_MODEST_RESOLUTION_FACTOR = 0.6

#: ARBITRARY. Below this mean HSV saturation (0-255) in a corner's reference
#: region, the border is pale enough that "lost saturation" barely registers --
#: which is the documented blind spot for white-bordered cards. A white border
#: sits near 0-10; 40 leaves room for genuinely pale colours too.
PALE_BORDER_SATURATION = 40.0

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
