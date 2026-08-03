"""The estimate a declined measurement leaves behind.

When centering cannot be measured the reading is kept as
`indicative_estimate` -- useful to show a customer, clearly labelled as
non-binding. The whole risk of keeping it is that something downstream
mistakes it for a measurement, so these tests are mostly about where it must
*not* end up.
"""

import numpy as np

from zgrader.analysis import assessment, centering


def _borderless():
    """Uniform noise: no printed border anywhere, so no side clears the
    significance bar."""
    rng = np.random.default_rng(0)
    return rng.integers(90, 160, size=(800, 600, 3), dtype=np.uint8)


def test_a_declined_measurement_still_reports_its_reading():
    result = centering.measure_centering(_borderless(), px_per_mm=600 / 25.4)
    estimate = result["measurements"]["indicative_estimate"]

    assert result["raw_score"] is None
    # The reading is preserved in full -- it is worth showing, just not worth
    # treating as a measurement.
    assert "worse_side_pct" in estimate
    assert "lr_ratio" in estimate and "tb_ratio" in estimate


def test_the_estimate_never_occupies_the_measurement_key():
    """The single most important property here.

    rules_engine reads `worse_side_pct` off the top level of a combined
    result's measurements and skips the rule when it is absent. That skip is
    the correct behaviour for an unmeasurable card. If the estimate were
    stored under that key it would silently reappear as a centering verdict
    from every enabled grading company, on a card nothing could measure.
    """
    measurements = centering.measure_centering(_borderless(), px_per_mm=600 / 25.4)[
        "measurements"
    ]

    assert "worse_side_pct" not in measurements
    assert "lr_ratio" not in measurements
    assert "tb_ratio" not in measurements


def test_a_measured_card_has_no_estimate():
    """Belt and braces: the two states are mutually exclusive, so nothing can
    read one while the other is what applies."""
    from tests.fixtures.generate_samples import build_fixture
    from zgrader.analysis import preprocessing, scale

    card, _info = preprocessing.locate_and_deskew(build_fixture("pokemon_back"))
    px_per_mm = scale.px_per_mm(card.shape[:2], 63.0, 88.0)
    result = centering.measure_centering(card, px_per_mm)

    assert result["raw_score"] is not None
    assert "indicative_estimate" not in result["measurements"]
    assert result["measurements"]["assessment"]["state"] == assessment.MEASURED


def test_a_declined_category_produces_no_company_verdicts(db_session):
    """End to end, through the pipeline rather than a constructed row.

    This is the failure the separate key exists to prevent: if the estimate
    were hoisted like a measurement, an unmeasurable card would come back with
    a centering verdict from every enabled grading company.
    """
    from zgrader.analysis import pipeline, rules_engine
    from zgrader.models import (
        AnalysisCategory,
        AnalysisResult,
        AnalysisSide,
        GradingCompanyComparison,
        Submission,
        SubmissionStatus,
        User,
    )
    from zgrader.auth.security import hash_password

    user = User(
        email="fullart@example.com", hashed_password=hash_password("hunter2pass"), is_verified=True
    )
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code="SUB-90901", user_id=user.id, status=SubmissionStatus.draft_ready
    )
    db_session.add(submission)
    db_session.flush()

    unmeasured = centering.measure_centering(_borderless(), px_per_mm=600 / 25.4)
    db_session.add(
        AnalysisResult(
            submission_id=submission.id,
            category=AnalysisCategory.centering,
            side=AnalysisSide.combined,
            raw_score=unmeasured["raw_score"],
            measurements=unmeasured["measurements"],
            flags=unmeasured["flags"],
        )
    )
    db_session.commit()

    rules_engine.evaluate(db_session, submission)
    db_session.commit()

    verdicts = (
        db_session.query(GradingCompanyComparison)
        .filter(GradingCompanyComparison.submission_id == submission.id)
        .all()
    )
    assert verdicts == [], "an unmeasurable card was given centering verdicts"


def test_the_combined_assessment_takes_the_weaker_side():
    """A clean back must not talk up an unreadable front."""
    from zgrader.analysis.pipeline import _combine_assessments
    from zgrader.analysis import assessment as a

    front = a.unmeasurable((a.CENTERING_NO_FRAME,)).as_dict()
    back = a.measured(9.0, a.CONFIDENCE_CENTERING_CLEAN_FRAME, ()).as_dict()

    merged = _combine_assessments(front, back)
    assert merged["state"] == a.UNMEASURABLE
    assert merged["confidence"] == 0.0
    assert a.CENTERING_NO_FRAME in merged["limitations"]
