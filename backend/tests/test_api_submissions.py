from fastapi.testclient import TestClient

from zgrader.api.main import app
from zgrader.auth.security import hash_password
from zgrader.models import User, UserRole

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


def test_create_submission_generates_code_and_scan_folder(db_session):
    token = _register_and_login("client1@example.com")
    resp = client.post(
        "/submissions",
        json={"game": "Pokemon", "card_name": "Pikachu", "set_name": "Base Set", "card_number": "58/102"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["submission_code"].startswith("SUB-")
    assert body["status"] == "created"
    assert body["card"]["card_name"] == "Pikachu"

    from pathlib import Path

    from zgrader.config import config

    assert (Path(config.scans_dir) / body["submission_code"]).is_dir()


def test_client_only_sees_own_submissions(db_session):
    token_a = _register_and_login("clienta@example.com")
    token_b = _register_and_login("clientb@example.com")

    client.post(
        "/submissions",
        json={"game": "Pokemon", "card_name": "A's card"},
        headers=_auth_headers(token_a),
    )
    client.post(
        "/submissions",
        json={"game": "Pokemon", "card_name": "B's card"},
        headers=_auth_headers(token_b),
    )

    resp_a = client.get("/submissions", headers=_auth_headers(token_a))
    names_a = {s["submission_code"] for s in resp_a.json()}
    resp_b = client.get("/submissions", headers=_auth_headers(token_b))
    names_b = {s["submission_code"] for s in resp_b.json()}

    assert names_a.isdisjoint(names_b)
    assert len(resp_a.json()) == 1
    assert len(resp_b.json()) == 1


def test_operator_sees_all_submissions(db_session):
    token_a = _register_and_login("opclienta@example.com")
    token_b = _register_and_login("opclientb@example.com")
    op_token = _make_operator(db_session, "operator1@example.com")

    client.post("/submissions", json={"game": "Pokemon", "card_name": "X"}, headers=_auth_headers(token_a))
    client.post("/submissions", json={"game": "Pokemon", "card_name": "Y"}, headers=_auth_headers(token_b))

    resp = client.get("/submissions", headers=_auth_headers(op_token))
    assert len(resp.json()) >= 2


def test_cannot_view_someone_elses_submission(db_session):
    token_a = _register_and_login("owner@example.com")
    token_b = _register_and_login("intruder@example.com")

    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Secret"}, headers=_auth_headers(token_a)
    )
    code = create_resp.json()["submission_code"]

    resp = client.get(f"/submissions/{code}", headers=_auth_headers(token_b))
    assert resp.status_code == 403

    resp = client.get(f"/submissions/{code}", headers=_auth_headers(token_a))
    assert resp.status_code == 200


def test_report_download_404_before_report_exists(db_session):
    token = _register_and_login("noreport@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Z"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    resp = client.get(f"/submissions/{code}/report", headers=_auth_headers(token))
    assert resp.status_code == 404


def test_upload_front_only_is_a_valid_partial_check(db_session, sample_scan_paths):
    token = _register_and_login("uploader1@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    with open(sample_scan_paths["pokemon_front"], "rb") as f:
        resp = client.post(
            f"/submissions/{code}/scans",
            files={"file": ("front.png", f, "image/png")},
            data={"side": "front"},
            headers=_auth_headers(token),
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["scan_sides"] == ["front"]
    assert body["status"] == "draft_ready"


def test_upload_front_then_back_replaces_partial_with_complete(db_session, sample_scan_paths):
    token = _register_and_login("uploader2@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    with open(sample_scan_paths["pokemon_front"], "rb") as f:
        client.post(
            f"/submissions/{code}/scans",
            files={"file": ("front.png", f, "image/png")},
            data={"side": "front"},
            headers=_auth_headers(token),
        )
    with open(sample_scan_paths["pokemon_back"], "rb") as f:
        resp = client.post(
            f"/submissions/{code}/scans",
            files={"file": ("back.png", f, "image/png")},
            data={"side": "back"},
            headers=_auth_headers(token),
        )

    assert resp.status_code == 200
    body = resp.json()
    assert set(body["scan_sides"]) == {"front", "back"}
    assert body["status"] == "draft_ready"


def test_upload_rejects_invalid_image(db_session):
    token = _register_and_login("uploader3@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    resp = client.post(
        f"/submissions/{code}/scans",
        files={"file": ("front.png", b"not an image", "image/png")},
        data={"side": "front"},
        headers=_auth_headers(token),
    )

    assert resp.status_code == 400


def test_upload_rejects_reupload_of_same_side(db_session, sample_scan_paths):
    token = _register_and_login("uploader4@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    with open(sample_scan_paths["pokemon_front"], "rb") as f:
        client.post(
            f"/submissions/{code}/scans",
            files={"file": ("front.png", f, "image/png")},
            data={"side": "front"},
            headers=_auth_headers(token),
        )
    with open(sample_scan_paths["pokemon_front"], "rb") as f:
        resp = client.post(
            f"/submissions/{code}/scans",
            files={"file": ("front.png", f, "image/png")},
            data={"side": "front"},
            headers=_auth_headers(token),
        )

    assert resp.status_code == 409


def test_upload_rejected_once_published(db_session, sample_scan_paths):
    token = _register_and_login("uploader5@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    with open(sample_scan_paths["pokemon_front"], "rb") as f:
        client.post(
            f"/submissions/{code}/scans",
            files={"file": ("front.png", f, "image/png")},
            data={"side": "front"},
            headers=_auth_headers(token),
        )
    with open(sample_scan_paths["pokemon_back"], "rb") as f:
        client.post(
            f"/submissions/{code}/scans",
            files={"file": ("back.png", f, "image/png")},
            data={"side": "back"},
            headers=_auth_headers(token),
        )

    op_token = _make_operator(db_session, "uploadop@example.com")
    client.post(f"/submissions/{code}/approve", headers=_auth_headers(op_token))

    resp = client.post(
        f"/submissions/{code}/scans",
        files={"file": ("front2.png", b"irrelevant", "image/png")},
        data={"side": "front"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 409


def test_cannot_upload_to_someone_elses_submission(db_session, sample_scan_paths):
    token_a = _register_and_login("uploadowner@example.com")
    token_b = _register_and_login("uploadintruder@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Secret"}, headers=_auth_headers(token_a)
    )
    code = create_resp.json()["submission_code"]

    with open(sample_scan_paths["pokemon_front"], "rb") as f:
        resp = client.post(
            f"/submissions/{code}/scans",
            files={"file": ("front.png", f, "image/png")},
            data={"side": "front"},
            headers=_auth_headers(token_b),
        )

    assert resp.status_code == 403
