"""A declined corners category must reach the combined row and the PDF.

Corners has declined before -- on a capture too small to show wear -- but
rarely. It now declines on about a third of real photographs, which makes it
the most frequent decline path in the pipeline, and AGENTS.md records that
every time a category gained the ability to decline, something downstream
assumed it could not. This goes through run_dev_trigger, the whole pipeline
including the report, rather than trusting each piece separately.
"""

from pathlib import Path

import cv2
from pypdf import PdfReader

from tests.fixtures.generate_samples import build_fixture
from zgrader.analysis import assessment
from zgrader.dev_trigger import run_dev_trigger
from zgrader.models import AnalysisCategory, AnalysisResult, AnalysisSide, Submission


def test_a_declined_corners_category_reaches_the_report(db_session, tmp_path):
    front = tmp_path / "shadowed_front.png"
    cv2.imwrite(str(front), build_fixture("capture_shadowed_corner"))

    result = run_dev_trigger(
        front_path=str(front),
        back_path=None,
        game="Pokemon",
        card_name="Shadowed Corner",
        user_email="shadowed@example.com",
        submission_code="SUB-SHADOW1",
    )

    assert result["status"] == "draft_ready"
    submission = db_session.query(Submission).filter_by(submission_code="SUB-SHADOW1").one()
    rows = {
        (row.side, row.category): row
        for row in db_session.query(AnalysisResult).filter_by(submission_id=submission.id)
    }
    front_corners = rows[(AnalysisSide.front, AnalysisCategory.corners)]
    combined_corners = rows[(AnalysisSide.combined, AnalysisCategory.corners)]

    assert front_corners.raw_score is None
    assert (
        assessment.CORNERS_BOUNDARY_UNREADABLE
        in front_corners.measurements["assessment"]["limitations"]
    )
    assert combined_corners.raw_score is None

    pdf_path = Path(result["report_pdf_path"])
    assert pdf_path.exists()
    text = " ".join(
        " ".join(page.extract_text().split()) for page in PdfReader(str(pdf_path)).pages
    )
    assert "Not measurable" in text
    assert "wrong outline" in text
