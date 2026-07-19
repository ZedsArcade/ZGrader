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
    assert body["business_name"] == "ZGrader"
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
