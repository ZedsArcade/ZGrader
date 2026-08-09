"""SMTP transport selection, startup warnings, and the test-email endpoint.

The theme: a misconfigured relay must stop being silent. send_email swallows
SMTP errors by design -- correctly, since a notification must never break the
flow it hangs off -- which means every other surface in the app reports success
whether or not mail actually left the building. These are the three places
that tell the truth instead.
"""

import logging
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from zgrader.api.main import app
from zgrader.config import ZGraderConfig
from zgrader.email.client import send_email
from tests.conftest import register_and_verify

client = TestClient(app)


def _config(**overrides) -> ZGraderConfig:
    """A config with the SMTP knobs set, everything else defaulted."""
    return ZGraderConfig(**overrides)


# --- transport selection ------------------------------------------------


def test_implicit_tls_uses_smtp_ssl():
    """Port 465 is TLS from the first byte. Using plain SMTP there connects
    and then waits forever for a greeting that never comes."""
    with patch("zgrader.email.client.config", _config(smtp_implicit_tls=True, smtp_port=465)):
        with patch("smtplib.SMTP_SSL") as ssl_cls, patch("smtplib.SMTP") as plain_cls:
            send_email("someone@example.com", "hi", "<p>hi</p>")

    assert ssl_cls.call_count == 1, "implicit TLS must use SMTP_SSL"
    assert plain_cls.call_count == 0, "implicit TLS must not open a plaintext connection"


def test_starttls_uses_plain_smtp_then_upgrades():
    with patch("zgrader.email.client.config", _config(smtp_use_tls=True, smtp_port=587)):
        with patch("smtplib.SMTP") as plain_cls, patch("smtplib.SMTP_SSL") as ssl_cls:
            send_email("someone@example.com", "hi", "<p>hi</p>")

    assert plain_cls.call_count == 1
    assert ssl_cls.call_count == 0
    plain_cls.return_value.__enter__.return_value.starttls.assert_called_once()


def test_implicit_tls_does_not_also_call_starttls():
    """Both flags true is a misconfiguration the startup check warns about.
    If it happens anyway, STARTTLS on an already-encrypted socket is an error
    from the server, so implicit TLS has to win rather than stack."""
    config = _config(smtp_implicit_tls=True, smtp_use_tls=True, smtp_port=465)
    with patch("zgrader.email.client.config", config):
        with patch("smtplib.SMTP_SSL") as ssl_cls:
            send_email("someone@example.com", "hi", "<p>hi</p>")

    ssl_cls.return_value.__enter__.return_value.starttls.assert_not_called()


def test_send_failure_is_swallowed_but_reported():
    """The contract the contact form and the test-email endpoint both rely on:
    no exception escapes, and the boolean tells the truth."""
    with patch("smtplib.SMTP", side_effect=OSError("connection refused")):
        assert send_email("someone@example.com", "hi", "<p>hi</p>") is False


# --- startup warnings ---------------------------------------------------


def test_production_on_the_dev_relay_warns(caplog):
    """The exact state the deployment is in: host still points at the bundled
    mailhog, which only runs under the `dev` compose profile."""
    with caplog.at_level(logging.WARNING):
        _config(
            env="production",
            smtp_host="mailhog",
            secret_key="x" * 48,
            database_url="postgresql+psycopg://real:creds@db:5432/zgrader",
        )

    assert any("SMTP configuration problem" in r.getMessage() for r in caplog.records)


def test_port_465_without_implicit_tls_warns(caplog):
    with caplog.at_level(logging.WARNING):
        _config(smtp_port=465, smtp_implicit_tls=False)

    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "465" in messages


def test_a_working_configuration_warns_about_nothing(caplog):
    """A warning nobody can act on trains people to ignore the log."""
    with caplog.at_level(logging.WARNING):
        _config(smtp_host="mail.example.com", smtp_port=587, smtp_use_tls=True)

    assert not [r for r in caplog.records if "SMTP configuration problem" in r.getMessage()]


# --- the admin endpoint -------------------------------------------------


@pytest.fixture()
def operator_token(db_session):
    from zgrader.models import User, UserRole

    token = register_and_verify(client, "smtp-operator@example.com")
    user = db_session.query(User).filter(User.email == "smtp-operator@example.com").one()
    user.role = UserRole.operator
    db_session.commit()
    return token


def test_test_email_reports_success(operator_token):
    with patch("zgrader.api.routers.admin.send_test_email", return_value=True):
        resp = client.post(
            "/admin/test-email",
            json={"to": "someone@example.com"},
            headers={"Authorization": f"Bearer {operator_token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["sent"] is True


def test_test_email_reports_failure_as_200_not_500(operator_token):
    """A failed test is a successful test -- it answered the question. A 500
    would be indistinguishable from the endpoint itself being broken, which is
    the one thing the operator is trying to rule out."""
    with patch("zgrader.api.routers.admin.send_test_email", return_value=False):
        resp = client.post(
            "/admin/test-email",
            json={"to": "someone@example.com"},
            headers={"Authorization": f"Bearer {operator_token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["sent"] is False
    assert "unreachable" in resp.json()["detail"]


def test_test_email_requires_an_operator(db_session):
    """It makes the server send mail to an arbitrary address, so a customer
    token must not reach it."""
    token = register_and_verify(client, "smtp-customer@example.com")
    resp = client.post(
        "/admin/test-email",
        json={"to": "someone@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 403
