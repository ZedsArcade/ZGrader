"""Shared steps for the first-check-flow tests: an account, a draft, a photo, a crop.

The charging rule is only visible end to end -- create, upload, confirm -- so
every test in this family walks that path, and doing it through one set of
helpers keeps them all walking it the same way.
"""

import datetime

from fastapi.testclient import TestClient

from zgrader.api.main import app
from zgrader.models import (
    AnalysisCategory,
    AnalysisResult,
    AnalysisSide,
    PlanEntitlement,
    SubmissionStatus,
    User,
)

from tests.conftest import register_and_verify

client = TestClient(app)

CATEGORIES = (
    AnalysisCategory.centering,
    AnalysisCategory.corners,
    AnalysisCategory.edges,
    AnalysisCategory.surface,
)


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(email: str) -> str:
    return register_and_verify(client, email)


def create(token: str, **fields):
    return client.post("/submissions", json={"game": "Pokemon", **fields}, headers=headers(token))


def create_code(token: str, **fields) -> str:
    resp = create(token, **fields)
    assert resp.status_code == 201, resp.text
    return resp.json()["submission_code"]


def upload(token: str, code: str, side: str, path):
    with open(path, "rb") as f:
        return client.post(
            f"/submissions/{code}/scans",
            files={"file": (f"{side}.png", f, "image/png")},
            data={"side": side},
            headers=headers(token),
        )


def confirm(token: str, code: str, side: str):
    """Accept the suggested crop verbatim, as a customer who changes nothing would."""
    suggestion = client.get(
        f"/submissions/{code}/scans/{side}/suggest-crop", headers=headers(token)
    ).json()
    return client.post(
        f"/submissions/{code}/scans/{side}/confirm-crop",
        json={"points": suggestion["points"]},
        headers=headers(token),
    )


def detail(token: str, code: str) -> dict:
    return client.get(f"/submissions/{code}", headers=headers(token)).json()


def quota(token: str) -> dict:
    return client.get("/submissions/quota", headers=headers(token)).json()


def set_free_limit(db_session, limit, period_days: int = 7) -> None:
    row = db_session.query(PlanEntitlement).filter(PlanEntitlement.plan == "free").one()
    row.submission_limit = limit
    row.period_days = period_days
    db_session.commit()


def spend(db_session, email: str, used: int) -> None:
    """Stand in for `used` scored checks already spent this window."""
    user = db_session.query(User).filter(User.email == email).one()
    user.quota_used = used
    user.quota_period_started_at = datetime.datetime.now(datetime.timezone.utc)
    db_session.commit()


def fake_analysis(score: float | None):
    """A stand-in for pipeline.run_analysis writing four combined rows at `score`.

    None reproduces the all-declined result a failed geometry fit produces,
    which the sample fixtures never do -- all 23 fit cleanly, see AGENTS.md.
    Patch it in with monkeypatch.setattr(pipeline, "run_analysis", ...).
    """

    def run(db, submission):
        db.query(AnalysisResult).filter(AnalysisResult.submission_id == submission.id).delete(
            synchronize_session=False
        )
        for category in CATEGORIES:
            db.add(
                AnalysisResult(
                    submission_id=submission.id,
                    category=category,
                    side=AnalysisSide.combined,
                    raw_score=score,
                    measurements={},
                    flags={},
                )
            )
        submission.status = SubmissionStatus.draft_ready
        db.flush()
        db.expire(submission, ["analysis_results"])

    return run
