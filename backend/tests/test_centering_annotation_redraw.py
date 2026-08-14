"""The drawn centering frame must follow the customer's adjustment.

Applying an adjustment moved the score but not the picture: the overlay is
drawn once at analysis time from the detected border, and nothing redrew it. On
screen that is merely confusing; in the published PDF it is a document
contradicting itself, showing detection's frame beside the customer's number.

These call the redraw directly rather than going through `generate_report`,
because report generation needs WeasyPrint and Pango, which are not installed on
the Windows dev box -- every PDF test is already among the known failures there.
Testing the drawing itself keeps this covered where the report tests cannot run.

They assert on **pixels**, not on the call happening. A redraw that runs and
produces the same image is the bug.
"""

import hashlib
import shutil

import numpy as np
import pytest
from PIL import Image

from zgrader.analysis import pipeline, recompute
from zgrader.models import (
    AnalysisCategory,
    AnalysisResult,
    AnalysisSide,
    Card,
    ScanImage,
    ScanSide,
    Submission,
    SubmissionStatus,
    User,
    UserRole,
)


def _submission_with_analysis(db_session, code, scan_path, tmp_path) -> Submission:
    user = User(email=f"{code.lower()}@example.com", hashed_password="x", role=UserRole.client)
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code=code, user_id=user.id, status=SubmissionStatus.draft_ready
    )
    db_session.add(submission)
    db_session.flush()
    db_session.add(Card(submission_id=submission.id, game="Pokemon", card_name="Test"))

    folder = tmp_path / code
    folder.mkdir(exist_ok=True)
    destination = folder / "scan_front.png"
    shutil.copy(scan_path, destination)
    with Image.open(destination) as image:
        width, height = image.size
    db_session.add(
        ScanImage(
            submission_id=submission.id,
            side=ScanSide.front,
            file_path=str(destination),
            original_filename="scan_front.png",
            dpi=600,
            width_px=width,
            height_px=height,
            checksum=hashlib.sha256(destination.read_bytes()).hexdigest(),
        )
    )
    db_session.commit()

    pipeline.run_analysis(db_session, submission)
    db_session.commit()
    return submission


def _centering_row(db_session, submission) -> AnalysisResult:
    return (
        db_session.query(AnalysisResult)
        .filter(
            AnalysisResult.submission_id == submission.id,
            AnalysisResult.category == AnalysisCategory.centering,
            AnalysisResult.side == AnalysisSide.front,
        )
        .one()
    )


# Rows to ignore when locating the frame: the label sits at y=10 and is drawn
# in the overlay colour, so it would otherwise be mistaken for the rectangle.
_LABEL_BAND_PX = 40


def _digest(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _frame_columns(path: str) -> list[int]:
    """Which columns carry the overlay colour, i.e. where the frame is drawn.

    Compared rather than the whole image so a failure says *the frame moved* or
    *it did not*, instead of only that some bytes differ.

    The top band is skipped because annotate_centering also writes its "L/R ..."
    label at (10, 10) in the same colour. Including it made the leftmost
    coloured column the label rather than the rectangle, so the frame could move
    a long way with the measurement pinned at 11.
    """
    with Image.open(path) as image:
        pixels = np.asarray(image.convert("RGB")).astype(int)
    pixels = pixels[_LABEL_BAND_PX:, :, :]
    # The overlay is drawn in a saturated colour; the card underneath is not.
    red, green, blue = pixels[..., 0], pixels[..., 1], pixels[..., 2]
    mask = (red > 150) & (green < 110) & (blue < 110)
    return sorted(set(np.nonzero(mask.any(axis=0))[0].tolist()))


@pytest.fixture
def analysed(db_session, tmp_path, sample_scan_paths):
    return _submission_with_analysis(
        db_session, "SUB-97001", sample_scan_paths["pokemon_front"], tmp_path
    )


def test_an_adjustment_moves_the_drawn_frame(db_session, analysed):
    row = _centering_row(db_session, analysed)
    if row.raw_score is None or not row.annotated_image_path:
        pytest.skip("centering was unmeasurable on this fixture, so nothing is drawn")

    before = _frame_columns(row.annotated_image_path)
    detected = row.measurements

    # Move the left border well inside where detection put it.
    analysed.centering_adjustments = {
        "front": {
            "left_px": detected["left_px"] + 40,
            "right_px": detected["right_px"],
            "top_px": detected["top_px"],
            "bottom_px": detected["bottom_px"],
        }
    }
    db_session.commit()

    rewritten = recompute.redraw_centering_annotations(db_session, analysed)
    assert row.annotated_image_path in rewritten

    after = _frame_columns(row.annotated_image_path)
    assert after != before, "the drawing did not follow the adjustment"
    # Specifically, the left edge of the frame moved right.
    assert min(after) > min(before)


def test_the_stored_measurement_still_records_what_was_detected(db_session, analysed):
    """The drawing is derived; the measurement is evidence. Redrawing must not
    quietly rewrite what the pipeline actually found."""
    row = _centering_row(db_session, analysed)
    if row.raw_score is None:
        pytest.skip("centering was unmeasurable on this fixture")
    detected_left = row.measurements["left_px"]

    analysed.centering_adjustments = {
        "front": {
            "left_px": detected_left + 40,
            "right_px": row.measurements["right_px"],
            "top_px": row.measurements["top_px"],
            "bottom_px": row.measurements["bottom_px"],
        }
    }
    db_session.commit()
    recompute.redraw_centering_annotations(db_session, analysed)
    db_session.refresh(row)

    assert row.measurements["left_px"] == detected_left


def test_clearing_the_adjustment_redraws_the_detected_frame(db_session, analysed):
    """The case the unconditional redraw exists for.

    Redrawing only when an adjustment is present would leave the adjusted lines
    on disk after the customer reverted -- stale in the opposite direction, and
    harder to notice.
    """
    row = _centering_row(db_session, analysed)
    if row.raw_score is None or not row.annotated_image_path:
        pytest.skip("centering was unmeasurable on this fixture")

    original = _frame_columns(row.annotated_image_path)

    analysed.centering_adjustments = {
        "front": {
            "left_px": row.measurements["left_px"] + 40,
            "right_px": row.measurements["right_px"],
            "top_px": row.measurements["top_px"],
            "bottom_px": row.measurements["bottom_px"],
        }
    }
    db_session.commit()
    recompute.redraw_centering_annotations(db_session, analysed)
    assert _frame_columns(row.annotated_image_path) != original

    analysed.centering_adjustments = None
    db_session.commit()
    recompute.redraw_centering_annotations(db_session, analysed)

    assert _frame_columns(row.annotated_image_path) == original


def test_redrawing_twice_with_no_change_is_a_no_op(db_session, analysed):
    """Idempotent, so it is safe to run on every report."""
    row = _centering_row(db_session, analysed)
    if not row.annotated_image_path:
        pytest.skip("nothing drawn for this fixture")

    recompute.redraw_centering_annotations(db_session, analysed)
    first = _digest(row.annotated_image_path)
    recompute.redraw_centering_annotations(db_session, analysed)

    assert _digest(row.annotated_image_path) == first
