"""A placed centering must reach the combined row, the comparisons and the PDF.

Goes through run_dev_trigger -- the whole pipeline on a full-art fixture whose
centering declines -- then places lines and generates the report, rather than
trusting each piece separately. AGENTS.md: every time a category gained the
ability to decline, something downstream assumed it could not; this is the
first time a declined category can be un-declined, and the same applies.
"""

import cv2
from pypdf import PdfReader

from tests.fixtures.generate_samples import build_fixture
from zgrader.analysis import assessment, centering, recompute
from zgrader.dev_trigger import run_dev_trigger
from zgrader.models import (
    AnalysisCategory,
    AnalysisResult,
    AnalysisSide,
    GradingCompanyComparison,
    Submission,
)
from zgrader.reports import builder


def _pdf_text(path) -> str:
    return " ".join(" ".join(page.extract_text().split()) for page in PdfReader(str(path)).pages)


def test_a_placed_centering_reaches_the_report(db_session, tmp_path):
    front = tmp_path / "full_art_front.png"
    cv2.imwrite(str(front), build_fixture("full_art_centered"))
    result = run_dev_trigger(
        front_path=str(front),
        back_path=None,
        game="Pokemon",
        card_name="Full Art",
        user_email="placed@example.com",
        submission_code="SUB-PLACE1",
    )
    assert result["status"] == "draft_ready"

    submission = db_session.query(Submission).filter_by(submission_code="SUB-PLACE1").one()
    front_row = (
        db_session.query(AnalysisResult)
        .filter_by(submission_id=submission.id, side=AnalysisSide.front, category=AnalysisCategory.centering)
        .one()
    )
    assert front_row.raw_score is None
    assert centering.placement_eligible(front_row.measurements)

    ppm = front_row.measurements["card_geometry"]["px_per_mm"]
    submission.centering_adjustments = {
        "front": {
            "left_px": round(2.5 * ppm, 1),
            "right_px": round(3.5 * ppm, 1),
            "top_px": round(3.0 * ppm, 1),
            "bottom_px": round(3.0 * ppm, 1),
        }
    }
    recompute.recompute_submission(db_session, submission)
    db_session.commit()

    db_session.expire_all()
    combined = (
        db_session.query(AnalysisResult)
        .filter_by(submission_id=submission.id, side=AnalysisSide.combined, category=AnalysisCategory.centering)
        .one()
    )
    assert combined.raw_score is not None
    assert assessment.CENTERING_CLIENT_PLACED in combined.measurements["assessment"]["limitations"]
    assert (
        db_session.query(GradingCompanyComparison)
        .filter_by(submission_id=submission.id, category="centering")
        .count()
        > 0
    )

    report = builder.generate_report(db_session, submission)
    db_session.commit()
    assert report.pdf_path.endswith("_client_adjusted.pdf")
    assert "placed by hand" in _pdf_text(report.pdf_path)
