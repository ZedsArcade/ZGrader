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
