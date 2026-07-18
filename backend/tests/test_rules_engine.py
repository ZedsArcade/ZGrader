from zgrader.analysis import rules_engine
from zgrader.models import (
    AnalysisCategory,
    AnalysisResult,
    AnalysisSide,
    GradingCompany,
    Submission,
    SubmissionStatus,
    ToleranceSeverity,
    User,
    UserRole,
)


def _make_submission(db_session, code: str) -> Submission:
    user = User(email=f"{code.lower()}@example.com", hashed_password="x", role=UserRole.client)
    db_session.add(user)
    db_session.flush()
    submission = Submission(submission_code=code, user_id=user.id, status=SubmissionStatus.processing)
    db_session.add(submission)
    db_session.flush()
    return submission


def test_severity_differs_across_companies_for_borderline_centering(db_session):
    submission = _make_submission(db_session, "SUB-RULE1")
    db_session.add(
        AnalysisResult(
            submission_id=submission.id,
            category=AnalysisCategory.centering,
            side=AnalysisSide.combined,
            raw_score=6.4,
            measurements={"worse_side_pct": 68.0, "lr_ratio": [68.0, 32.0], "tb_ratio": [50.0, 50.0]},
            flags={},
        )
    )
    db_session.flush()

    comparisons = rules_engine.evaluate(db_session, submission)
    by_company = {c.company: c for c in comparisons if c.category == "centering"}

    assert by_company[GradingCompany.PSA].severity == ToleranceSeverity.minor
    assert by_company[GradingCompany.BGS].severity == ToleranceSeverity.major
    assert by_company[GradingCompany.CGC].severity == ToleranceSeverity.major
    assert by_company[GradingCompany.TAG].severity == ToleranceSeverity.major
    assert "68" in by_company[GradingCompany.PSA].contention_note


def test_severity_none_for_pristine_scores(db_session):
    submission = _make_submission(db_session, "SUB-RULE2")
    for category in (AnalysisCategory.corners, AnalysisCategory.edges, AnalysisCategory.surface):
        db_session.add(
            AnalysisResult(
                submission_id=submission.id,
                category=category,
                side=AnalysisSide.combined,
                raw_score=10.0,
                measurements={},
                flags={},
            )
        )
    db_session.flush()

    comparisons = rules_engine.evaluate(db_session, submission)
    assert all(c.severity == ToleranceSeverity.none for c in comparisons)


def test_never_emits_a_numeric_grade_prediction(db_session):
    submission = _make_submission(db_session, "SUB-RULE3")
    db_session.add(
        AnalysisResult(
            submission_id=submission.id,
            category=AnalysisCategory.corners,
            side=AnalysisSide.combined,
            raw_score=5.0,
            measurements={},
            flags={},
        )
    )
    db_session.flush()

    comparisons = rules_engine.evaluate(db_session, submission)
    for comp in comparisons:
        # The note must not contain a "X/10" style grade for any company
        # other than the input raw_score being restated -- never a distinct
        # predicted grade value.
        assert "predicted grade" not in comp.contention_note.lower()
        assert "would score" not in comp.contention_note.lower()
