"""Enabling/disabling a whole grading company from the admin panel.

`active` lives on each tolerance rule rather than on the company, so these
tests care that a toggle reaches all of one company's rules and none of
anyone else's.
"""

import pytest
from fastapi.testclient import TestClient

from zgrader.analysis import rules_engine
from zgrader.api.main import app
from zgrader.auth.security import hash_password
from zgrader.models import (
    AnalysisCategory,
    AnalysisResult,
    AnalysisSide,
    AuditLog,
    GradingCompany,
    Submission,
    SubmissionStatus,
    User,
    UserRole,
)
from zgrader.models.grading_comparison import GradingCompanyToleranceRule

client = TestClient(app)


def _operator_headers(db_session, email: str) -> dict:
    db_session.add(
        User(
            email=email,
            hashed_password=hash_password("hunter2pass"),
            role=UserRole.operator,
            is_verified=True,
        )
    )
    db_session.commit()
    token = client.post(
        "/auth/login", data={"username": email, "password": "hunter2pass"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_submission(db_session, code: str) -> Submission:
    user = User(email=f"{code.lower()}@example.com", hashed_password="x", role=UserRole.client)
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code=code, user_id=user.id, status=SubmissionStatus.draft_ready
    )
    db_session.add(submission)
    db_session.flush()
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
    return submission


@pytest.fixture()
def op_headers(db_session):
    return _operator_headers(db_session, "companyop@example.com")


def test_lists_every_company_active_by_default(db_session, op_headers):
    body = client.get("/admin/grading-companies", headers=op_headers).json()
    assert [c["company"] for c in body] == [c.value for c in GradingCompany]
    assert all(c["active"] for c in body)
    assert all(c["rule_count"] == 4 for c in body)


def test_disabling_removes_only_that_company_from_the_comparison(db_session, op_headers):
    submission = _make_submission(db_session, "SUB-TOG1")

    before = {c.company for c in rules_engine.evaluate(db_session, submission)}
    assert GradingCompany.ACE in before

    resp = client.patch(
        "/admin/grading-companies/ACE", json={"active": False}, headers=op_headers
    )
    assert resp.status_code == 200
    assert resp.json() == {"company": "ACE", "active": False, "rule_count": 4}

    db_session.expire_all()
    after = {c.company for c in rules_engine.evaluate(db_session, submission)}
    assert GradingCompany.ACE not in after
    # Everyone else is untouched -- the UPDATE must not spill across companies.
    assert after == before - {GradingCompany.ACE}


def test_disabling_and_re_enabling_round_trips(db_session, op_headers):
    submission = _make_submission(db_session, "SUB-TOG2")

    client.patch("/admin/grading-companies/TAG", json={"active": False}, headers=op_headers)
    db_session.expire_all()
    assert GradingCompany.TAG not in {
        c.company for c in rules_engine.evaluate(db_session, submission)
    }

    client.patch("/admin/grading-companies/TAG", json={"active": True}, headers=op_headers)
    db_session.expire_all()
    assert GradingCompany.TAG in {
        c.company for c in rules_engine.evaluate(db_session, submission)
    }

    listed = {c["company"]: c["active"] for c in client.get(
        "/admin/grading-companies", headers=op_headers
    ).json()}
    assert all(listed.values())


def test_disabled_company_drops_out_of_public_branding(db_session, op_headers):
    """The public copy names the companies from this list, so it has to track
    the toggle -- otherwise the landing page keeps advertising a comparison
    that no longer runs."""
    assert "CGC" in client.get("/catalog/branding").json()["grading_companies"]

    client.patch("/admin/grading-companies/CGC", json={"active": False}, headers=op_headers)

    listed = client.get("/catalog/branding").json()["grading_companies"]
    assert "CGC" not in listed
    # Still in enum order, and unauthenticated.
    assert listed == [c.value for c in GradingCompany if c.value != "CGC"]


def test_toggle_is_audited(db_session, op_headers):
    client.patch("/admin/grading-companies/BGS", json={"active": False}, headers=op_headers)
    entry = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "grading_company_disabled")
        .one()
    )
    assert entry.detail == {"company": "BGS", "rules_updated": 4}
    assert entry.user_id is not None


def test_unknown_company_is_rejected(db_session, op_headers):
    for bad in ("NOPE", "psa", "'; DROP TABLE settings; --"):
        resp = client.patch(
            f"/admin/grading-companies/{bad}", json={"active": False}, headers=op_headers
        )
        assert resp.status_code == 404, bad


def test_only_operators_can_toggle(db_session):
    client.post("/auth/register", json={"email": "togclient@example.com", "password": "hunter2pass"})
    token = client.post(
        "/auth/login", data={"username": "togclient@example.com", "password": "hunter2pass"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/admin/grading-companies", headers=headers).status_code == 403
    assert client.patch(
        "/admin/grading-companies/PSA", json={"active": False}, headers=headers
    ).status_code == 403
    assert client.patch(
        "/admin/grading-companies/PSA", json={"active": False}
    ).status_code == 401


def test_already_stored_comparisons_survive_a_disable(db_session, op_headers):
    """Disabling only writes to the rules table. A submission analysed while a
    company was enabled keeps its rows until something re-runs the engine for
    that submission -- reports aren't rewritten underneath a client."""
    submission = _make_submission(db_session, "SUB-TOG3")
    rules_engine.evaluate(db_session, submission)
    db_session.commit()

    stored_before = {c.company for c in submission.company_comparisons}
    assert GradingCompany.PSA in stored_before

    client.patch("/admin/grading-companies/PSA", json={"active": False}, headers=op_headers)
    db_session.expire_all()

    assert GradingCompany.PSA in {c.company for c in submission.company_comparisons}


def test_disabling_every_company_leaves_an_empty_comparison(db_session, op_headers):
    """An operator can switch the whole feature off. Nothing should error --
    the comparison is simply absent."""
    submission = _make_submission(db_session, "SUB-TOG4")
    for company in GradingCompany:
        client.patch(
            f"/admin/grading-companies/{company.value}", json={"active": False}, headers=op_headers
        )
    db_session.expire_all()

    assert rules_engine.evaluate(db_session, submission) == []
    assert client.get("/catalog/branding").json()["grading_companies"] == []
    assert db_session.query(GradingCompanyToleranceRule).filter(
        GradingCompanyToleranceRule.active.is_(True)
    ).count() == 0
