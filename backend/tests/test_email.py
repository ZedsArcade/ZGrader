import smtplib
from unittest.mock import MagicMock, patch

from zgrader.email.client import send_email
from zgrader.email.notifications import send_report_published, send_submission_received
from zgrader.models import Settings


def test_send_email_calls_smtp_with_expected_message():
    with patch("zgrader.email.client.smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

        send_email("client@example.com", "Subject line", "<p>hello</p>")

        mock_smtp.send_message.assert_called_once()
        sent_message = mock_smtp.send_message.call_args[0][0]
        assert sent_message["To"] == "client@example.com"
        assert sent_message["Subject"] == "Subject line"


def test_send_email_swallows_connection_errors():
    with patch("zgrader.email.client.smtplib.SMTP", side_effect=OSError("connection refused")):
        # Must not raise -- a notification failure can't break the caller's flow.
        send_email("client@example.com", "Subject", "<p>hi</p>")


def test_send_email_swallows_smtp_exceptions():
    with patch("zgrader.email.client.smtplib.SMTP", side_effect=smtplib.SMTPException("bad auth")):
        send_email("client@example.com", "Subject", "<p>hi</p>")


class _FakeUser:
    email = "client@example.com"


class _FakeCard:
    card_name = "Test Card"


class _FakeSubmission:
    submission_code = "SUB-00099"
    card = _FakeCard()


def test_submission_received_uses_business_name_from_settings():
    with patch("zgrader.email.notifications.send_email") as mock_send:
        settings = Settings(business_name="Cedric's Card Grading")
        send_submission_received(_FakeUser(), _FakeSubmission(), settings)

        mock_send.assert_called_once()
        to, subject, html = mock_send.call_args[0]
        assert to == "client@example.com"
        assert "Cedric's Card Grading" in subject
        assert "SUB-00099" in subject
        assert "SUB-00099" in html
        assert "Test Card" in html


def test_report_published_falls_back_to_default_business_name_when_settings_missing():
    with patch("zgrader.email.notifications.send_email") as mock_send:
        send_report_published(_FakeUser(), _FakeSubmission(), None)

        mock_send.assert_called_once()
        _to, subject, _html = mock_send.call_args[0]
        assert "ZGrader" in subject


# --- Wiring: the real request/worker flows actually trigger these, not just
# the notification builder in isolation. ---


def test_creating_a_submission_sends_a_received_email():
    from fastapi.testclient import TestClient

    from zgrader.api.main import app

    client = TestClient(app)
    client.post("/auth/register", json={"email": "emailwire1@example.com", "password": "hunter2pass"})
    token = client.post(
        "/auth/login", data={"username": "emailwire1@example.com", "password": "hunter2pass"}
    ).json()["access_token"]

    with patch("zgrader.api.routers.submissions.send_submission_received") as mock_send:
        resp = client.post(
            "/submissions",
            json={"game": "Pokemon", "card_name": "Wired Card"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        mock_send.assert_called_once()


def test_approving_a_submission_sends_a_published_email(db_session, tmp_path, sample_scan_paths):
    import shutil

    from fastapi.testclient import TestClient

    from zgrader.api.main import app
    from zgrader.auth.security import hash_password
    from zgrader.models import User, UserRole
    from zgrader.worker.watcher import process_submission_folder

    client = TestClient(app)
    client.post("/auth/register", json={"email": "emailwire2@example.com", "password": "hunter2pass"})
    client_token = client.post(
        "/auth/login", data={"username": "emailwire2@example.com", "password": "hunter2pass"}
    ).json()["access_token"]
    resp = client.post(
        "/submissions",
        json={"game": "Pokemon", "card_name": "Wired Card 2"},
        headers={"Authorization": f"Bearer {client_token}"},
    )
    code = resp.json()["submission_code"]

    folder = tmp_path / code
    folder.mkdir()
    shutil.copy(sample_scan_paths["pokemon_front"], folder / "scan_front.png")
    shutil.copy(sample_scan_paths["pokemon_back"], folder / "scan_back.png")
    process_submission_folder(db_session, code, folder)

    db_session.add(
        User(
            email="emailwireop@example.com",
            hashed_password=hash_password("hunter2pass"),
            role=UserRole.operator,
            is_verified=True,
        )
    )
    db_session.commit()
    op_token = client.post(
        "/auth/login", data={"username": "emailwireop@example.com", "password": "hunter2pass"}
    ).json()["access_token"]

    with patch("zgrader.api.routers.submissions.send_report_published") as mock_send:
        resp = client.post(f"/submissions/{code}/approve", headers={"Authorization": f"Bearer {op_token}"})
        assert resp.status_code == 200
        mock_send.assert_called_once()


def test_auto_publish_sends_a_published_email(db_session, tmp_path, sample_scan_paths):
    import shutil

    from zgrader.models import Submission, SubmissionStatus, User, UserRole
    from zgrader.worker.watcher import process_submission_folder

    user = User(email="autowire@example.com", hashed_password="x", role=UserRole.client)
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code="SUB-90010", user_id=user.id, status=SubmissionStatus.created, auto_publish=True
    )
    db_session.add(submission)
    db_session.commit()

    folder = tmp_path / "SUB-90010"
    folder.mkdir()
    shutil.copy(sample_scan_paths["pokemon_front"], folder / "scan_front.png")
    shutil.copy(sample_scan_paths["pokemon_back"], folder / "scan_back.png")

    with patch("zgrader.worker.watcher.send_report_published") as mock_send:
        result = process_submission_folder(db_session, "SUB-90010", folder)
        assert result.status == SubmissionStatus.published
        mock_send.assert_called_once()
