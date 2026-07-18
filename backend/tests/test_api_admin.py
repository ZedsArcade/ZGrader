import shutil

from fastapi.testclient import TestClient

from zgrader.api.main import app
from zgrader.auth.security import hash_password
from zgrader.models import ReportStatus, Submission, SubmissionStatus, User, UserRole
from zgrader.worker.watcher import process_submission_folder

client = TestClient(app)


def _register_and_login(email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "hunter2pass"})
    resp = client.post("/auth/login", data={"username": email, "password": "hunter2pass"})
    return resp.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_operator(db_session, email: str) -> str:
    user = User(email=email, hashed_password=hash_password("hunter2pass"), role=UserRole.operator, is_verified=True)
    db_session.add(user)
    db_session.commit()
    resp = client.post("/auth/login", data={"username": email, "password": "hunter2pass"})
    return resp.json()["access_token"]


def _create_draft_ready_submission(db_session, tmp_path, sample_scan_paths, code: str) -> Submission:
    client_token = _register_and_login(f"{code.lower()}@example.com")
    resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "X"}, headers=_auth_headers(client_token)
    )
    real_code = resp.json()["submission_code"]

    folder = tmp_path / real_code
    folder.mkdir()
    shutil.copy(sample_scan_paths["pokemon_front"], folder / "scan_front.png")
    shutil.copy(sample_scan_paths["pokemon_back"], folder / "scan_back.png")
    process_submission_folder(db_session, real_code, folder)
    return real_code


def test_non_operator_cannot_access_admin_settings(db_session):
    token = _register_and_login("nonop@example.com")
    resp = client.get("/admin/settings", headers=_auth_headers(token))
    assert resp.status_code == 403


def test_operator_can_read_and_update_settings(db_session):
    op_token = _make_operator(db_session, "settingsop@example.com")

    resp = client.get("/admin/settings", headers=_auth_headers(op_token))
    assert resp.status_code == 200
    assert resp.json()["business_name"] == "ZGrader"

    resp = client.patch(
        "/admin/settings",
        json={"business_name": "Cedric's Card Grading", "auto_publish_default": True},
        headers=_auth_headers(op_token),
    )
    assert resp.status_code == 200
    assert resp.json()["business_name"] == "Cedric's Card Grading"
    assert resp.json()["auto_publish_default"] is True


def test_operator_can_view_stats(db_session):
    op_token = _make_operator(db_session, "statsop@example.com")
    resp = client.get("/admin/stats", headers=_auth_headers(op_token))
    assert resp.status_code == 200
    body = resp.json()
    assert "total_submissions" in body
    assert "by_status" in body


def test_approve_publishes_a_draft_ready_submission(db_session, tmp_path, sample_scan_paths):
    code = _create_draft_ready_submission(db_session, tmp_path, sample_scan_paths, "SUB-APPROVE1")
    op_token = _make_operator(db_session, "approveop1@example.com")

    resp = client.post(f"/submissions/{code}/approve", headers=_auth_headers(op_token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"

    resp = client.get(f"/submissions/{code}/report", headers=_auth_headers(op_token))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


def test_client_cannot_approve_their_own_submission(db_session, tmp_path, sample_scan_paths):
    client_token = _register_and_login("selfapprove@example.com")
    resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Y"}, headers=_auth_headers(client_token)
    )
    code = resp.json()["submission_code"]

    resp = client.post(f"/submissions/{code}/approve", headers=_auth_headers(client_token))
    assert resp.status_code == 403


def test_approve_rejects_submission_not_yet_draft_ready(db_session):
    client_token = _register_and_login("notready@example.com")
    resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Z"}, headers=_auth_headers(client_token)
    )
    code = resp.json()["submission_code"]
    op_token = _make_operator(db_session, "notreadyop@example.com")

    resp = client.post(f"/submissions/{code}/approve", headers=_auth_headers(op_token))
    assert resp.status_code == 409


def test_operator_can_set_per_submission_auto_publish_override(db_session):
    client_token = _register_and_login("override@example.com")
    resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "W"}, headers=_auth_headers(client_token)
    )
    code = resp.json()["submission_code"]
    op_token = _make_operator(db_session, "overrideop@example.com")

    resp = client.patch(
        f"/submissions/{code}/auto-publish", json={"auto_publish": True}, headers=_auth_headers(op_token)
    )
    assert resp.status_code == 200

    from zgrader.db import SessionLocal

    db = SessionLocal()
    submission = db.query(Submission).filter(Submission.submission_code == code).first()
    assert submission.auto_publish is True
    db.close()
