"""The link-preview image, and the staleness it must not have.

What most people see of a shared report is the unfurl, not the page, so this
image is a published artefact in the same sense the PDF is. The invariant that
applies is the one behind `redraw_centering_annotations` being unconditional: a
picture derived from the measurements goes stale the moment a client adjusts a
border or dismisses a finding.

This module gets that guarantee from the cache key rather than from remembering
to redraw, so most of what is worth testing is the fingerprint -- particularly
that it changes *back* when an adjustment is cleared, which is the direction
nobody thinks to check and exactly where the equivalent bug lived before.
"""

import datetime

import pytest
from PIL import Image

from zgrader.analysis import og_image
from zgrader.config import config
from zgrader.models import (
    AnalysisCategory,
    AnalysisResult,
    AnalysisSide,
    Card,
    Report,
    ReportStatus,
    Submission,
    SubmissionLanguage,
    SubmissionStatus,
    User,
    UserRole,
)


def _submission(db_session, code="SUB-70001", language=SubmissionLanguage.en) -> Submission:
    user = User(email=f"{code.lower()}@example.com", hashed_password="x", role=UserRole.client)
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code=code,
        user_id=user.id,
        status=SubmissionStatus.published,
        language=language,
    )
    db_session.add(submission)
    db_session.flush()
    db_session.add(
        Card(
            submission_id=submission.id,
            game="Pokemon",
            card_name="Charizard",
            set_name="Base Set",
            card_number="4",
            foil=True,
        )
    )
    for category, score in (
        (AnalysisCategory.centering, 8.5),
        (AnalysisCategory.corners, 9.6),
        (AnalysisCategory.edges, 9.9),
        # Unmeasurable, so the drawing has to show that rather than a zero.
        (AnalysisCategory.surface, None),
    ):
        db_session.add(
            AnalysisResult(
                submission_id=submission.id,
                side=AnalysisSide.combined,
                category=category,
                raw_score=score,
                measurements={},
                flags={},
            )
        )
    db_session.add(
        Report(
            submission_id=submission.id,
            version=1,
            status=ReportStatus.published,
            pdf_path="/tmp/x.pdf",
            generated_at=datetime.datetime.now(datetime.timezone.utc),
        )
    )
    db_session.commit()
    db_session.refresh(submission)
    return submission


# --- the fingerprint is the invalidation ---------------------------------


def test_fingerprint_is_stable_for_unchanged_state(db_session):
    submission = _submission(db_session)

    assert og_image.fingerprint(submission) == og_image.fingerprint(submission)


def test_applying_an_adjustment_changes_the_fingerprint(db_session):
    submission = _submission(db_session)
    before = og_image.fingerprint(submission)

    submission.centering_adjustments = {
        "front": {"left_px": 90.0, "right_px": 90.0, "top_px": 120.0, "bottom_px": 120.0}
    }
    db_session.commit()

    assert og_image.fingerprint(submission) != before


def test_clearing_an_adjustment_returns_the_original_fingerprint(db_session):
    """The direction that actually breaks.

    Regenerating only when an adjustment *exists* leaves the cleared case
    carrying the adjusted picture forever -- stale in the direction nobody
    checks. Deriving the key from current state makes reverting restore the old
    filename, so the correct image is already on disk and served again.
    """
    submission = _submission(db_session)
    original = og_image.fingerprint(submission)

    submission.centering_adjustments = {"front": {"left_px": 90.0, "right_px": 90.0,
                                                  "top_px": 120.0, "bottom_px": 120.0}}
    db_session.commit()
    assert og_image.fingerprint(submission) != original

    submission.centering_adjustments = None
    db_session.commit()

    assert og_image.fingerprint(submission) == original


def test_dismissing_a_finding_changes_the_fingerprint(db_session):
    submission = _submission(db_session)
    before = og_image.fingerprint(submission)

    submission.dismissed_regions = ["front:surface:blob_1"]
    db_session.commit()

    assert og_image.fingerprint(submission) != before


def test_a_changed_score_changes_the_fingerprint(db_session):
    """The scores are the whole point of the picture, so a recompute that moves
    one must not leave the old preview addressable."""
    submission = _submission(db_session)
    before = og_image.fingerprint(submission)

    row = next(
        r for r in submission.analysis_results if r.category == AnalysisCategory.corners
    )
    row.raw_score = 7.0
    db_session.commit()
    db_session.refresh(submission)

    assert og_image.fingerprint(submission) != before


# --- what gets drawn ------------------------------------------------------


def test_render_produces_a_1200x630_jpeg(db_session):
    submission = _submission(db_session)

    path = og_image.ensure(submission, "Card Care Center", config.reports_dir)

    with Image.open(path) as image:
        assert image.size == (og_image.OG_WIDTH, og_image.OG_HEIGHT) == (1200, 630)
        assert image.format == "JPEG"


def test_the_preview_stays_under_the_size_that_stops_whatsapp_showing_it(db_session):
    """WhatsApp has historically refused to render a preview much above 300KB,
    and it is the client this feature was asked for first. The card photo is
    absent in this fixture, so treat this as a floor rather than a guarantee --
    it catches a change that makes the composition wildly heavier."""
    submission = _submission(db_session)

    path = og_image.ensure(submission, "Card Care Center", config.reports_dir)

    assert path.stat().st_size < 300_000


def test_ensure_is_idempotent_and_reaps_the_previous_version(db_session):
    submission = _submission(db_session)
    first = og_image.ensure(submission, "Card Care Center", config.reports_dir)
    assert og_image.ensure(submission, "Card Care Center", config.reports_dir) == first

    submission.dismissed_regions = ["front:surface:blob_1"]
    db_session.commit()
    second = og_image.ensure(submission, "Card Care Center", config.reports_dir)

    assert second != first
    # The old one is gone rather than left addressable beside the new one.
    assert not first.exists()
    assert len(list(second.parent.glob("og_*.jpg"))) == 1


def test_the_filename_carries_no_submission_code_or_email(db_session):
    """The path is not public, but it is one rename away from being -- and the
    code is the thing this whole feature exists to keep out of public reach."""
    submission = _submission(db_session)

    path = og_image.ensure(submission, "Card Care Center", config.reports_dir)

    assert submission.submission_code not in path.name
    assert "example.com" not in path.name


def test_a_missing_card_photo_still_renders(db_session):
    """A submission whose front_base.png is absent must still get a preview.
    Returning nothing would mean no unfurl at all, which is worse than a
    preview without the card on it."""
    submission = _submission(db_session)

    path = og_image.ensure(submission, "Card Care Center", config.reports_dir)

    assert path.is_file()


@pytest.mark.parametrize("language", [SubmissionLanguage.en, SubmissionLanguage.es])
def test_both_languages_render(db_session, language):
    submission = _submission(db_session, code=f"SUB-7100{language.value == 'es'}", language=language)

    path = og_image.ensure(submission, "Card Care Center", config.reports_dir)

    with Image.open(path) as image:
        assert image.size == (1200, 630)


def test_an_absurd_business_name_does_not_break_the_footer(db_session):
    """`business_name` is operator-editable and unbounded, and the Spanish
    disclaimer is already the longer of the two footer strings. Both at full
    length would meet in the middle, so the layout has to fit rather than
    assume."""
    submission = _submission(db_session, language=SubmissionLanguage.es)

    path = og_image.ensure(submission, "A" * 200, config.reports_dir)

    with Image.open(path) as image:
        assert image.size == (1200, 630)


def test_the_font_can_draw_accented_spanish(db_session):
    """The assertion the first version of this file was missing.

    `test_both_languages_render` checks the image's dimensions, which are the
    same whether the Spanish labels are words or a row of missing-glyph boxes --
    and Pillow's bundled fallback face renders a-acute and n-tilde as exactly
    that. A preview full of boxes on the Spanish half of an acquisition channel
    is not something to leave to whoever eventually looks at one.
    """
    assert og_image.fonts_cover_spanish(), (
        "The resolved font cannot draw accented characters, so Spanish previews "
        "would render as boxes. Check zgrader/assets/fonts/."
    )


def test_language_changes_the_fingerprint(db_session):
    """The image carries translated labels, so two languages are two pictures
    and must not share a cache entry."""
    en = _submission(db_session, code="SUB-72001", language=SubmissionLanguage.en)
    es = _submission(db_session, code="SUB-72002", language=SubmissionLanguage.es)

    assert og_image.fingerprint(en) != og_image.fingerprint(es)
