from fastapi.testclient import TestClient

from zgrader.api.main import app

client = TestClient(app)


def test_list_games_is_public_and_seeded(db_session):
    resp = client.get("/catalog/games")
    assert resp.status_code == 200
    games = {g["game"] for g in resp.json()}
    assert "Pokemon" in games
    assert "Yu-Gi-Oh!" in games
    fftcg = next(g for g in resp.json() if g["game"] == "Final Fantasy TCG")
    assert fftcg["verified"] is False


def test_get_branding_is_public_and_defaults_seeded(db_session):
    resp = client.get("/catalog/branding")
    assert resp.status_code == 200
    body = resp.json()
    assert body["business_name"] == "Card Care Center"
    assert "business_contact" in body


def test_branding_reflects_operator_updates(db_session):
    from zgrader.auth.security import hash_password
    from zgrader.models import User, UserRole

    op = User(
        email="brandingop@example.com",
        hashed_password=hash_password("hunter2pass"),
        role=UserRole.operator,
        is_verified=True,
    )
    db_session.add(op)
    db_session.commit()
    token = client.post(
        "/auth/login", data={"username": "brandingop@example.com", "password": "hunter2pass"}
    ).json()["access_token"]

    client.patch(
        "/admin/settings",
        json={"business_name": "Cedric's Card Grading"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = client.get("/catalog/branding")
    assert resp.json()["business_name"] == "Cedric's Card Grading"


def _operator_token(db_session, email: str) -> str:
    from zgrader.auth.security import hash_password
    from zgrader.models import User, UserRole

    db_session.add(
        User(
            email=email,
            hashed_password=hash_password("hunter2pass"),
            role=UserRole.operator,
            is_verified=True,
        )
    )
    db_session.commit()
    return client.post(
        "/auth/login", data={"username": email, "password": "hunter2pass"}
    ).json()["access_token"]


def test_branding_exposes_empty_contact_and_socials_on_a_fresh_install(db_session):
    """A brand-new deployment has no socials configured. The endpoint must
    still answer with the keys present and null, because the footer decides
    what to render from their absence rather than from a missing field."""
    body = client.get("/catalog/branding").json()
    for field in (
        "contact_email",
        "contact_response_days",
        "social_instagram",
        "social_facebook",
        "social_x",
        "social_whatsapp",
    ):
        assert field in body, field
        assert body[field] is None, field
    assert body["contact_in_person"] is False
    # Seeded so the contact page says something useful before first edit.
    assert body["contact_location"] == "Gibraltar"


def test_branding_publishes_contact_and_social_details(db_session):
    token = _operator_token(db_session, "socialop@example.com")
    resp = client.patch(
        "/admin/settings",
        json={
            "contact_email": "hello@example.com",
            "contact_location": "Gibraltar",
            "contact_response_days": 2,
            "contact_in_person": True,
            "social_instagram": "https://instagram.com/cardcarecentre",
            "social_whatsapp": "+350 5400 0000",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    body = client.get("/catalog/branding").json()
    assert body["contact_email"] == "hello@example.com"
    assert body["contact_response_days"] == 2
    assert body["contact_in_person"] is True
    assert body["social_instagram"] == "https://instagram.com/cardcarecentre"
    # Stored as digits only; the frontend builds the wa.me link from this.
    assert body["social_whatsapp"] == "35054000000"


def test_social_url_with_a_script_scheme_is_rejected(db_session):
    """These values land in an href on a public page, so a javascript: URL
    would be stored XSS against every visitor."""
    token = _operator_token(db_session, "xssop@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    for bad in ("javascript:alert(1)", "data:text/html,<script>alert(1)</script>", "notaurl"):
        resp = client.patch("/admin/settings", json={"social_facebook": bad}, headers=headers)
        assert resp.status_code == 422, bad

    resp = client.patch(
        "/admin/settings", json={"social_facebook": "https://facebook.com/ccc"}, headers=headers
    )
    assert resp.status_code == 200
    assert client.get("/catalog/branding").json()["social_facebook"] == "https://facebook.com/ccc"


def test_blank_values_clear_a_setting(db_session):
    """The admin form submits "" for a field the operator emptied; that has to
    clear the value, otherwise a link can be added but never removed."""
    token = _operator_token(db_session, "clearop@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.patch("/admin/settings", json={"social_x": "https://x.com/ccc"}, headers=headers)
    assert client.get("/catalog/branding").json()["social_x"] == "https://x.com/ccc"

    resp = client.patch(
        "/admin/settings", json={"social_x": "", "contact_email": ""}, headers=headers
    )
    assert resp.status_code == 200
    body = client.get("/catalog/branding").json()
    assert body["social_x"] is None
    assert body["contact_email"] is None
