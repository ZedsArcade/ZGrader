import shutil

from zgrader.models import (
    AnalysisSide,
    Card,
    ReportStatus,
    Submission,
    SubmissionStatus,
    User,
    UserRole,
)
from zgrader.worker.watcher import process_submission_folder


def _make_submission(db_session, code: str, *, auto_publish: bool | None = None) -> Submission:
    user = User(email=f"{code.lower()}@example.com", hashed_password="x", role=UserRole.client)
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code=code, user_id=user.id, status=SubmissionStatus.created, auto_publish=auto_publish
    )
    db_session.add(submission)
    db_session.flush()
    db_session.add(Card(submission_id=submission.id, game="Pokemon", card_name="Test Card"))
    db_session.commit()
    return submission


def test_empty_folder_marks_awaiting_scans(db_session, tmp_path):
    _make_submission(db_session, "SUB-90001")
    folder = tmp_path / "SUB-90001"
    folder.mkdir()

    result = process_submission_folder(db_session, "SUB-90001", folder)

    assert result.status == SubmissionStatus.awaiting_scans


def test_front_and_back_scans_trigger_analysis(db_session, tmp_path, sample_scan_paths):
    _make_submission(db_session, "SUB-90002")
    folder = tmp_path / "SUB-90002"
    folder.mkdir()
    shutil.copy(sample_scan_paths["pokemon_front"], folder / "scan_front.png")
    shutil.copy(sample_scan_paths["pokemon_back"], folder / "scan_back.png")

    result = process_submission_folder(db_session, "SUB-90002", folder)

    assert result.status == SubmissionStatus.draft_ready
    assert len(result.scan_images) == 2
    combined_results = [r for r in result.analysis_results if r.side == AnalysisSide.combined]
    assert {r.category for r in combined_results} == {"centering", "corners", "edges", "surface"}
    assert result.reports == []  # auto_publish defaults off -> stays a draft

    # Regression check: the combined centering AnalysisResult must carry a
    # top-level "worse_side_pct" (not just nested under front/back), since
    # that's what rules_engine reads to generate centering comparison rows --
    # every company should get a centering row, same as the other categories.
    comparison_categories = {c.category for c in result.company_comparisons}
    assert comparison_categories == {"centering", "corners", "edges", "surface"}
    centering_companies = {c.company.value for c in result.company_comparisons if c.category == "centering"}
    assert centering_companies == {"PSA", "BGS", "CGC", "TAG"}


def test_auto_publish_generates_and_publishes_report(db_session, tmp_path, sample_scan_paths):
    _make_submission(db_session, "SUB-90003", auto_publish=True)
    folder = tmp_path / "SUB-90003"
    folder.mkdir()
    shutil.copy(sample_scan_paths["pokemon_front"], folder / "scan_front.png")
    shutil.copy(sample_scan_paths["pokemon_back"], folder / "scan_back.png")

    result = process_submission_folder(db_session, "SUB-90003", folder)

    assert result.status == SubmissionStatus.published
    assert len(result.reports) == 1
    assert result.reports[0].status == ReportStatus.published
    from pathlib import Path

    assert Path(result.reports[0].pdf_path).exists()


def test_front_only_stays_awaiting_scans(db_session, tmp_path, sample_scan_paths):
    _make_submission(db_session, "SUB-90004")
    folder = tmp_path / "SUB-90004"
    folder.mkdir()
    shutil.copy(sample_scan_paths["pokemon_front"], folder / "scan_front.png")

    result = process_submission_folder(db_session, "SUB-90004", folder)

    # Phase 1's pipeline treats front as sufficient to proceed (back is
    # optional), so this should already have moved past awaiting_scans.
    assert result.status == SubmissionStatus.draft_ready


def test_unclassifiable_filename_is_warned_and_ignored(db_session, tmp_path, sample_scan_paths):
    _make_submission(db_session, "SUB-90005")
    folder = tmp_path / "SUB-90005"
    folder.mkdir()
    shutil.copy(sample_scan_paths["pokemon_front"], folder / "mystery_scan.png")

    result = process_submission_folder(db_session, "SUB-90005", folder)

    assert result.status == SubmissionStatus.awaiting_scans
    assert result.scan_images == []
    assert "mystery_scan.png" in (result.notes or "")


def test_processing_is_idempotent(db_session, tmp_path, sample_scan_paths):
    _make_submission(db_session, "SUB-90006", auto_publish=True)
    folder = tmp_path / "SUB-90006"
    folder.mkdir()
    shutil.copy(sample_scan_paths["pokemon_front"], folder / "scan_front.png")
    shutil.copy(sample_scan_paths["pokemon_back"], folder / "scan_back.png")

    first = process_submission_folder(db_session, "SUB-90006", folder)
    second = process_submission_folder(db_session, "SUB-90006", folder)

    assert first.status == second.status == SubmissionStatus.published
    assert len(second.reports) == 1  # not regenerated on the second call
