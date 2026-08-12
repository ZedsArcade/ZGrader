"""Re-running analysis must replace the previous assessment, not add to it.

Nothing in the persistence path upserts: `_persist_side` and
`rules_engine.evaluate` both insert fresh rows. So without an explicit delete, a
rerun leaves two complete sets behind, then three. One production submission
reached three.

It surfaces as storage growth rather than wrong numbers only because every
consumer happens to read the newest row. That is a property of today's
consumers, not a guarantee -- anything that aggregated instead of taking the
latest would multiply-count silently, which is the kind of wrong that gets
published before anyone notices.

The cleanup used to live in the watcher, guarded by `status == draft_ready`, so
it covered exactly one of the several ways analysis gets re-run: `dev_trigger`
never cleaned up, and neither did a rerun from the error state. These tests go
through `run_analysis` directly for that reason -- the guarantee has to hold for
every caller, not for the one path that happened to be covered.
"""

import hashlib
import shutil

import pytest
from PIL import Image

from zgrader.analysis import pipeline
from zgrader.models import (
    AnalysisResult,
    Card,
    GradingCompanyComparison,
    ScanImage,
    ScanSide,
    Submission,
    SubmissionStatus,
    User,
    UserRole,
)


def _submission_with_front_scan(db_session, code: str, scan_path, tmp_path) -> Submission:
    user = User(email=f"{code.lower()}@example.com", hashed_password="x", role=UserRole.client)
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code=code, user_id=user.id, status=SubmissionStatus.created
    )
    db_session.add(submission)
    db_session.flush()
    db_session.add(Card(submission_id=submission.id, game="Pokemon", card_name="Test Card"))

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
            # All NOT NULL. dpi in particular is recorded but not used for
            # scale -- that comes from the card's physical size, never from
            # image metadata.
            dpi=600,
            width_px=width,
            height_px=height,
            checksum=hashlib.sha256(destination.read_bytes()).hexdigest(),
        )
    )
    db_session.commit()
    return submission


def _counts(db_session, submission) -> tuple[int, int]:
    results = (
        db_session.query(AnalysisResult)
        .filter(AnalysisResult.submission_id == submission.id)
        .count()
    )
    comparisons = (
        db_session.query(GradingCompanyComparison)
        .filter(GradingCompanyComparison.submission_id == submission.id)
        .count()
    )
    return results, comparisons


def test_a_second_run_replaces_the_rows_rather_than_adding_a_set(
    db_session, tmp_path, sample_scan_paths
):
    submission = _submission_with_front_scan(
        db_session, "SUB-95001", sample_scan_paths["pokemon_front"], tmp_path
    )

    pipeline.run_analysis(db_session, submission)
    db_session.commit()
    first = _counts(db_session, submission)
    assert first[0] > 0, "the first run produced no analysis results"

    pipeline.run_analysis(db_session, submission)
    db_session.commit()

    assert _counts(db_session, submission) == first


def test_a_third_run_does_not_creep(db_session, tmp_path, sample_scan_paths):
    """The production case was three sets, not two -- so check the invariant
    holds on repeat rather than merely on the second run."""
    submission = _submission_with_front_scan(
        db_session, "SUB-95002", sample_scan_paths["pokemon_front"], tmp_path
    )

    counts = []
    for _ in range(3):
        pipeline.run_analysis(db_session, submission)
        db_session.commit()
        counts.append(_counts(db_session, submission))

    assert counts[0] == counts[1] == counts[2]


def test_exactly_one_row_survives_per_side_and_category(
    db_session, tmp_path, sample_scan_paths
):
    """Row counts alone would pass if a rerun deleted one set and wrote two.

    This is the assertion that actually pins the shape: after any number of
    runs, a (side, category) pair identifies exactly one row -- which is the
    thing every consumer's "take the newest" behaviour is quietly relying on.
    """
    submission = _submission_with_front_scan(
        db_session, "SUB-95003", sample_scan_paths["pokemon_front"], tmp_path
    )

    pipeline.run_analysis(db_session, submission)
    db_session.commit()
    pipeline.run_analysis(db_session, submission)
    db_session.commit()

    rows = (
        db_session.query(AnalysisResult)
        .filter(AnalysisResult.submission_id == submission.id)
        .all()
    )
    seen: dict[tuple, int] = {}
    for row in rows:
        seen[(row.side, row.category)] = seen.get((row.side, row.category), 0) + 1
    duplicated = {k: v for k, v in seen.items() if v > 1}
    assert not duplicated, f"duplicated (side, category) rows after a rerun: {duplicated}"


def test_the_scores_are_the_same_as_a_single_run(db_session, tmp_path, sample_scan_paths):
    """A rerun on unchanged inputs must land on the same numbers.

    Guards the delete itself: clearing rows the pipeline then reads back --
    `_persist_combined` and `rules_engine.evaluate` both walk the relationship
    collections -- would produce a second run that scores differently from the
    first, which is a worse failure than duplicate rows.
    """
    submission = _submission_with_front_scan(
        db_session, "SUB-95004", sample_scan_paths["pokemon_front"], tmp_path
    )

    def scores() -> dict[tuple, float | None]:
        rows = (
            db_session.query(AnalysisResult)
            .filter(AnalysisResult.submission_id == submission.id)
            .all()
        )
        return {(r.side, r.category): r.raw_score for r in rows}

    pipeline.run_analysis(db_session, submission)
    db_session.commit()
    first = scores()

    pipeline.run_analysis(db_session, submission)
    db_session.commit()
    second = scores()

    assert set(first) == set(second)
    for key, value in first.items():
        if value is None:
            assert second[key] is None, f"{key} scored on the rerun but not the first run"
        else:
            assert second[key] == pytest.approx(value), f"{key} moved on a rerun"
