"""An unmeasurable category must survive the whole chain as "no answer".

`raw_score` became nullable so the pipeline can decline to score something.
That is only worth anything if every reader downstream treats NULL as "we
could not tell" rather than as zero -- and the readers are spread across the
rules engine, the PDF builder and the recompute path, any one of which could
quietly turn a refusal into a bad grade.

Nothing emits NULL yet; these rows are constructed directly. That is the
point: the plumbing is proven before any category starts using it.
"""

import pytest

from zgrader.analysis import recompute, rules_engine
from zgrader.models import (
    AnalysisCategory,
    AnalysisResult,
    AnalysisSide,
    GradingCompanyComparison,
)
from zgrader.reports.builder import build_report_context

from tests.conftest import register_and_verify  # noqa: F401  (fixture wiring)


def _submission(db_session):
    from zgrader.models import Submission, SubmissionStatus, User
    from zgrader.auth.security import hash_password

    user = User(email="unmeasurable@example.com", hashed_password=hash_password("hunter2pass"), is_verified=True)
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code="SUB-90900", user_id=user.id, status=SubmissionStatus.draft_ready
    )
    db_session.add(submission)
    db_session.flush()
    return submission


def _add_result(db_session, submission, category, score, side=AnalysisSide.combined):
    row = AnalysisResult(
        submission_id=submission.id,
        category=category,
        side=side,
        raw_score=score,
        measurements={},
        flags={},
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_a_null_score_can_be_persisted(db_session):
    """The column change itself. While this was NOT NULL the honest answer
    could not be stored at all."""
    submission = _submission(db_session)
    row = _add_result(db_session, submission, AnalysisCategory.centering, None)
    db_session.commit()
    db_session.refresh(row)
    assert row.raw_score is None


def test_the_rules_engine_skips_an_unmeasurable_category(db_session):
    """The failure that would matter most.

    A missing measurement cannot be in or out of a company's tolerance.
    Scoring it would turn "we could not tell" into "this card has a problem",
    published against five named grading companies.
    """
    submission = _submission(db_session)
    _add_result(db_session, submission, AnalysisCategory.corners, None)
    _add_result(db_session, submission, AnalysisCategory.edges, 9.5)
    db_session.commit()

    rules_engine.evaluate(db_session, submission)
    db_session.commit()

    categories = {
        c.category
        for c in db_session.query(GradingCompanyComparison).filter(
            GradingCompanyComparison.submission_id == submission.id
        )
    }
    assert "corners" not in categories, "an unmeasurable category was given a company verdict"
    assert "edges" in categories, "a measurable category should still be compared"


def test_the_report_renders_no_number_for_an_unmeasurable_category(db_session):
    submission = _submission(db_session)
    _add_result(db_session, submission, AnalysisCategory.centering, None)
    _add_result(db_session, submission, AnalysisCategory.corners, 8.0)
    db_session.commit()

    from zgrader.models.settings import get_or_create_settings

    context = build_report_context(submission, get_or_create_settings(db_session))
    by_category = {row["category"]: row for row in context["scorecard"]}

    assert by_category["centering"]["combined_score"] is None
    assert by_category["corners"]["combined_score"] == 8.0


def test_recompute_ignores_an_unmeasurable_side(db_session):
    """A side with no score must contribute nothing, not a zero that drags the
    combined figure down."""
    submission = _submission(db_session)
    _add_result(db_session, submission, AnalysisCategory.corners, None, side=AnalysisSide.front)
    _add_result(db_session, submission, AnalysisCategory.corners, 9.0, side=AnalysisSide.back)
    combined = _add_result(db_session, submission, AnalysisCategory.corners, 9.0)
    combined.measurements = {"front": {"regions": []}, "back": {"regions": []}}
    db_session.commit()

    recompute.recompute_submission(db_session, submission)
    db_session.commit()
    db_session.refresh(combined)

    assert combined.raw_score is not None
    assert float(combined.raw_score) > 0.0


@pytest.mark.parametrize(
    "front,back,expected",
    [
        (None, None, None),
        (8.0, None, 8.0),
        (None, 8.0, 8.0),
    ],
)
def test_combining_sides_never_invents_a_score(front, back, expected):
    """One unreadable side must not cap the other at 70% of its value, and two
    unreadable sides must give no answer rather than zero."""
    from zgrader.analysis import scoring

    assert scoring.combine_front_back(front, back) == expected


def test_the_api_serialises_a_null_score_instead_of_returning_500(db_session):
    """The gap that reached production.

    Everything inside the pipeline was updated when raw_score became nullable
    -- the rules engine, the report builder, recompute, the Jinja template, and
    the frontend's own TypeScript type, which has said `number | null` all
    along. The Pydantic response model was not, and stayed a bare `float`.

    So the pipeline correctly declined to score a category, wrote NULL, and
    then FastAPI refused to serialise its own response: every request for that
    submission returned 500 with a ResponseValidationError, confirm-crop
    included. It failed on the first real card that proved a category can be
    unmeasurable.

    This exercises the HTTP boundary rather than the model, because that is
    where the mismatch lived. Asserting the field is Optional would have been a
    restatement of the annotation, and would have passed against the broken
    code just as readily once someone "fixed" it by changing the annotation
    alone.
    """
    from fastapi.testclient import TestClient

    from zgrader.api.main import app
    from zgrader.models import Submission

    client = TestClient(app)
    token = register_and_verify(client, "nullscore@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/submissions", headers=headers, json={"game": "pokemon", "card_name": "Unmeasurable"}
    )
    assert created.status_code in (200, 201), created.text
    code = created.json()["submission_code"]

    submission = db_session.query(Submission).filter_by(submission_code=code).one()
    _add_result(db_session, submission, AnalysisCategory.centering, None)
    _add_result(db_session, submission, AnalysisCategory.corners, 8.0)
    db_session.commit()

    resp = client.get(f"/submissions/{code}", headers=headers)

    assert resp.status_code == 200, resp.text
    by_category = {r["category"]: r["raw_score"] for r in resp.json()["analysis_results"]}
    assert by_category["centering"] is None, "an unmeasurable category must serialise as null"
    assert by_category["corners"] == 8.0
