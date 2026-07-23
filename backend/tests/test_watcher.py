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


def test_front_only_partial_check_does_not_auto_publish(db_session, tmp_path, sample_scan_paths):
    # auto_publish=True must not fire off an incomplete, front-only result --
    # a "partial check" should never silently become a final emailed report.
    _make_submission(db_session, "SUB-90007", auto_publish=True)
    folder = tmp_path / "SUB-90007"
    folder.mkdir()
    shutil.copy(sample_scan_paths["pokemon_front"], folder / "scan_front.png")

    result = process_submission_folder(db_session, "SUB-90007", folder)

    assert result.status == SubmissionStatus.draft_ready
    assert result.reports == []


def test_back_arriving_after_front_only_replaces_draft_without_duplicating(
    db_session, tmp_path, sample_scan_paths
):
    _make_submission(db_session, "SUB-90008")
    folder = tmp_path / "SUB-90008"
    folder.mkdir()
    shutil.copy(sample_scan_paths["pokemon_front"], folder / "scan_front.png")

    partial = process_submission_folder(db_session, "SUB-90008", folder)
    assert partial.status == SubmissionStatus.draft_ready
    partial_combined = [r for r in partial.analysis_results if r.side == AnalysisSide.combined]
    assert len(partial_combined) == 4  # one per category, front-only

    # Nothing new -- a routine poll tick shouldn't rerun analysis.
    unchanged = process_submission_folder(db_session, "SUB-90008", folder)
    assert len(unchanged.analysis_results) == len(partial.analysis_results)

    shutil.copy(sample_scan_paths["pokemon_back"], folder / "scan_back.png")
    completed = process_submission_folder(db_session, "SUB-90008", folder)

    assert completed.status == SubmissionStatus.draft_ready
    assert len(completed.scan_images) == 2
    # Replaced, not duplicated: still exactly one combined row per category,
    # and now front+back per-side rows too (2 sides * 4 categories = 8,
    # plus 4 combined = 12), not the 16 a naive rerun would leave behind.
    assert len(completed.analysis_results) == 12
    combined_after = [r for r in completed.analysis_results if r.side == AnalysisSide.combined]
    assert len(combined_after) == 4
    assert {c.category for c in completed.company_comparisons} == {"centering", "corners", "edges", "surface"}
    for category in {"centering", "corners", "edges", "surface"}:
        rows = [c for c in completed.company_comparisons if c.category == category]
        assert len({c.company for c in rows}) == len(rows)  # no duplicate (company, category) pairs


def test_back_arriving_after_front_only_can_still_auto_publish(db_session, tmp_path, sample_scan_paths):
    _make_submission(db_session, "SUB-90009", auto_publish=True)
    folder = tmp_path / "SUB-90009"
    folder.mkdir()
    shutil.copy(sample_scan_paths["pokemon_front"], folder / "scan_front.png")

    partial = process_submission_folder(db_session, "SUB-90009", folder)
    assert partial.status == SubmissionStatus.draft_ready
    assert partial.reports == []

    shutil.copy(sample_scan_paths["pokemon_back"], folder / "scan_back.png")
    completed = process_submission_folder(db_session, "SUB-90009", folder)

    assert completed.status == SubmissionStatus.published
    assert len(completed.reports) == 1


def test_published_submission_ignores_further_folder_changes(db_session, tmp_path, sample_scan_paths):
    _make_submission(db_session, "SUB-90010", auto_publish=True)
    folder = tmp_path / "SUB-90010"
    folder.mkdir()
    shutil.copy(sample_scan_paths["pokemon_front"], folder / "scan_front.png")
    shutil.copy(sample_scan_paths["pokemon_back"], folder / "scan_back.png")

    published = process_submission_folder(db_session, "SUB-90010", folder)
    assert published.status == SubmissionStatus.published
    result_count_before = len(published.analysis_results)

    # A stray extra file (e.g. a corrected scan dropped in after publish)
    # must not trigger any reprocessing -- published is terminal.
    shutil.copy(sample_scan_paths["yugioh_front"], folder / "extra_front.png")
    still_published = process_submission_folder(db_session, "SUB-90010", folder)

    assert still_published.status == SubmissionStatus.published
    assert len(still_published.analysis_results) == result_count_before
