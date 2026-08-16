"""What an unauthenticated visitor to a shared report is allowed to see.

Deliberately a separate module from `schemas.submission`, and deliberately
without `from_attributes` anywhere in it.

That second part is the whole design. `SubmissionDetail` sets
`ConfigDict(from_attributes=True)` and is handed the ORM row, so it publishes
whatever the model declares -- which is right for the account's own view of its
own submission, and exactly wrong here. A public serializer built that way leaks
**by addition**: the next column added to `Submission` is on the public page the
moment it is declared, with nobody having decided that. Every model below is
built field by field from primitives by `build_public_report`, so a new column
reaches this page only if somebody writes a line to put it there.

The same reasoning applies one level down, and is easier to miss.
`AnalysisResultOut.measurements` is a bare `dict` straight out of JSONB, so
anything the pipeline starts writing into it is published too. It is projected
here onto a closed set of keys -- exactly what the page renders and nothing
else.

Never present, and asserted absent by tests/test_public_share.py:
submission_code, id, user_id, batch_id, notes, status, auto_publish,
error_message, the owner's email, quota, audit.
"""

import datetime

from pydantic import BaseModel

from zgrader.analysis import og_image

# The measurement keys the public page actually reads. Each one is here because
# something renders it; see the frontend reference beside it. Anything else in
# `measurements` is dropped.
#
#   regions            -> AnnotatedPhoto draws the overlay and the breakout crops
#   assessment         -> the limitation notes under each score
#   original_raw_score -> the struck-through pre-adjustment score
#   ai_observations    -> the written notes beside the photo
#   card_geometry      -> px_per_mm, needed to turn border widths into ratios
#   {left,right,top,bottom}_px -> the centering ratios ("47/53")
_CENTERING_WIDTH_KEYS = ("left_px", "right_px", "top_px", "bottom_px")


class PublicCardOut(BaseModel):
    """The card itself. Public because it is what the customer is showing off,
    and it identifies a card rather than a person."""

    game: str
    card_name: str
    set_name: str | None
    card_number: str | None
    foil: bool


class PublicAssessmentOut(BaseModel):
    """What a score is worth, beside the score. Mirrors
    `analysis.assessment.Assessment.as_dict`."""

    state: str
    confidence: float
    score_low: float | None
    score_high: float | None
    # Codes rather than sentences, so the page can render them in either
    # language -- the same contract the authenticated view uses.
    limitations: list[str] = []


class PublicRegionOut(BaseModel):
    """One flagged area on the card. Mirrors `analysis.regions._region`."""

    id: str
    kind: str
    severity: str
    score: float
    bbox_norm: list[float]
    anchor_norm: list[float]
    note: str | None = None
    # Present only on some kinds; omitted rather than nulled so the payload
    # stays the shape the frontend's optional fields already expect.
    area_fraction: float | None = None
    length_mm: float | None = None
    low_confidence: bool | None = None
    line_norm: list[float] | None = None


class PublicMeasurementsOut(BaseModel):
    """The projection of `AnalysisResult.measurements`.

    A closed set. The authenticated schema passes this dict through untouched,
    which is the single most likely way something private ends up on a public
    page without anyone editing this file.
    """

    regions: list[PublicRegionOut] = []
    assessment: PublicAssessmentOut | None = None
    original_raw_score: float | None = None
    ai_observations: list[dict] = []
    px_per_mm: float | None = None
    left_px: float | None = None
    right_px: float | None = None
    top_px: float | None = None
    bottom_px: float | None = None


class PublicFlagsOut(BaseModel):
    """`AnalysisResult.flags`, projected for the same reason as measurements."""

    lower_confidence: bool = False
    reason: str | None = None


class PublicAnalysisResultOut(BaseModel):
    category: str
    side: str
    # Nullable, and it matters. A category that could not be measured has no
    # score, which is a different answer from a bad one -- render it as "not
    # measurable", never as zero. This is the fifth place downstream of
    # `raw_score` becoming nullable; the previous four all assumed it could not.
    raw_score: float | None
    flags: PublicFlagsOut
    measurements: PublicMeasurementsOut


class PublicComparisonOut(BaseModel):
    company: str
    category: str
    severity: str
    contention_note: str


class PublicReportOut(BaseModel):
    card: PublicCardOut | None
    # What the submission was created in. Drives the server-rendered metadata
    # only -- a crawler has no locale switcher to read. The page body follows
    # the viewer's own choice like every other page.
    language: str
    created_at: datetime.datetime
    client_adjusted: bool
    dismissed_count: int
    sides: list[str] = []
    results: list[PublicAnalysisResultOut] = []
    comparisons: list[PublicComparisonOut] = []
    centering_adjustments: dict[str, dict[str, float]] = {}
    # The companies with an active tolerance rule, so the "not affiliated with"
    # line on a public page can never name one the operator has switched off.
    # Same source as the rest of the site: catalog._active_grading_companies.
    grading_companies: list[str] = []
    # A hash of everything the link-preview image is drawn from, appended to its
    # URL as ?v=. Changing state changes this, so a crawler that re-unfurls
    # after an adjustment asks for a different URL and cannot be handed a
    # cached picture of the old numbers. Not a secret: it is derived from what
    # the page already shows.
    og_version: str = ""


class ShareStateOut(BaseModel):
    """Whether a submission is shared, and where. Authenticated surface only --
    this carries the token, in the URL, to the owner who is entitled to it."""

    enabled: bool
    url: str | None = None
    enabled_at: datetime.datetime | None = None


def _project_measurements(raw: dict | None) -> PublicMeasurementsOut:
    """Pull the closed set of keys out of the stored JSONB blob.

    Reads defensively throughout: these come from a pipeline that has changed
    shape before, and a public page 500ing because one key moved would take out
    every shared link at once.
    """
    m = raw or {}
    geometry = m.get("card_geometry")
    px_per_mm = geometry.get("px_per_mm") if isinstance(geometry, dict) else None

    regions = [
        PublicRegionOut(**{k: v for k, v in region.items() if k in PublicRegionOut.model_fields})
        for region in m.get("regions") or []
        if isinstance(region, dict) and "id" in region
    ]

    assessment_block = m.get("assessment")
    assessment = (
        PublicAssessmentOut(
            **{
                k: v
                for k, v in assessment_block.items()
                if k in PublicAssessmentOut.model_fields
            }
        )
        if isinstance(assessment_block, dict) and "state" in assessment_block
        else None
    )

    widths = {
        key: float(m[key])
        for key in _CENTERING_WIDTH_KEYS
        if isinstance(m.get(key), (int, float))
    }

    return PublicMeasurementsOut(
        regions=regions,
        assessment=assessment,
        original_raw_score=m.get("original_raw_score"),
        # Only the note survives; whatever else an observation grows stays out.
        ai_observations=[
            {"note": obs["note"]}
            for obs in m.get("ai_observations") or []
            if isinstance(obs, dict) and isinstance(obs.get("note"), str)
        ],
        px_per_mm=px_per_mm if isinstance(px_per_mm, (int, float)) else None,
        **widths,
    )


def build_public_report(
    submission, grading_companies: list[str]
) -> PublicReportOut:
    """Map a Submission onto the public payload, one field at a time.

    Takes the ORM object but never hands it to a model -- the explicit mapping
    is the point. `grading_companies` is passed in rather than queried here so
    this stays a pure function of its arguments and the router owns the session.
    """
    card = submission.card

    def flags_of(result) -> dict:
        return result.flags or {}

    return PublicReportOut(
        card=(
            PublicCardOut(
                game=card.game,
                card_name=card.card_name,
                set_name=card.set_name,
                card_number=card.card_number,
                foil=card.foil,
            )
            if card is not None
            else None
        ),
        language=submission.language.value,
        created_at=submission.created_at,
        client_adjusted=submission.client_adjusted,
        dismissed_count=len(submission.dismissed_regions or []),
        sides=submission.scan_sides,
        results=[
            PublicAnalysisResultOut(
                category=result.category.value,
                side=result.side.value,
                raw_score=(float(result.raw_score) if result.raw_score is not None else None),
                flags=PublicFlagsOut(
                    lower_confidence=bool(flags_of(result).get("lower_confidence")),
                    reason=flags_of(result).get("reason"),
                ),
                measurements=_project_measurements(result.measurements),
            )
            for result in submission.analysis_results
        ],
        comparisons=[
            PublicComparisonOut(
                company=comparison.company.value,
                # A plain String column, unlike company/severity -- no .value.
                category=comparison.category,
                severity=comparison.severity.value,
                contention_note=comparison.contention_note,
            )
            for comparison in submission.company_comparisons
        ],
        centering_adjustments=submission.centering_adjustments or {},
        grading_companies=grading_companies,
        og_version=og_image.fingerprint(submission),
    )
