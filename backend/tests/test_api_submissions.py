from fastapi.testclient import TestClient

from zgrader.api.main import app
from zgrader.auth.security import hash_password
from zgrader.models import User, UserRole

from tests.conftest import register_and_verify

client = TestClient(app)


def _register_and_login(email: str) -> str:
    return register_and_verify(client, email)


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_operator(db_session, email: str) -> str:
    user = User(email=email, hashed_password=hash_password("hunter2pass"), role=UserRole.operator, is_verified=True)
    db_session.add(user)
    db_session.commit()
    resp = client.post("/auth/login", data={"username": email, "password": "hunter2pass"})
    return resp.json()["access_token"]


def _upload(token: str, code: str, side: str, path) -> dict:
    with open(path, "rb") as f:
        resp = client.post(
            f"/submissions/{code}/scans",
            files={"file": (f"{side}.png", f, "image/png")},
            data={"side": side},
            headers=_auth_headers(token),
        )
    return resp.json()


def _confirm_crop(token: str, code: str, side: str):
    """Self-serve uploads no longer auto-analyze -- this mirrors what the
    real crop-adjust UI does: fetch the auto-detect suggestion, then accept
    it verbatim, to advance a submission past the manual-confirm gate in
    tests that aren't specifically exercising the crop endpoints."""
    suggestion = client.get(
        f"/submissions/{code}/scans/{side}/suggest-crop", headers=_auth_headers(token)
    ).json()
    return client.post(
        f"/submissions/{code}/scans/{side}/confirm-crop",
        json={"points": suggestion["points"]},
        headers=_auth_headers(token),
    )


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


def test_upload_alone_does_not_trigger_analysis(db_session, sample_scan_paths):
    # Self-serve uploads are untrusted/inconsistent input -- analysis must
    # wait for the crop to be confirmed via the manual crop-adjust UI,
    # unlike the operator flatbed-drop path which auto-confirms.
    token = _register_and_login("uploader1@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    body = _upload(token, code, "front", sample_scan_paths["pokemon_front"])
    assert body["scan_sides"] == ["front"]
    assert body["confirmed_sides"] == []
    assert body["status"] != "draft_ready"


def test_confirm_crop_advances_front_only_to_draft_ready(db_session, sample_scan_paths):
    token = _register_and_login("uploader1b@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    _upload(token, code, "front", sample_scan_paths["pokemon_front"])
    resp = _confirm_crop(token, code, "front")

    assert resp.status_code == 200
    body = resp.json()
    assert body["confirmed_sides"] == ["front"]
    assert body["status"] == "draft_ready"


def test_upload_front_then_back_replaces_partial_with_complete(db_session, sample_scan_paths):
    token = _register_and_login("uploader2@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    _upload(token, code, "front", sample_scan_paths["pokemon_front"])
    _confirm_crop(token, code, "front")
    _upload(token, code, "back", sample_scan_paths["pokemon_back"])
    resp = _confirm_crop(token, code, "back")

    assert resp.status_code == 200
    body = resp.json()
    assert set(body["scan_sides"]) == {"front", "back"}
    assert set(body["confirmed_sides"]) == {"front", "back"}
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

    _upload(token, code, "front", sample_scan_paths["pokemon_front"])
    _confirm_crop(token, code, "front")
    _upload(token, code, "back", sample_scan_paths["pokemon_back"])
    _confirm_crop(token, code, "back")

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


def test_side_photo_404_before_analysis(db_session):
    token = _register_and_login("photonone@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    resp = client.get(f"/submissions/{code}/scans/front/photo", headers=_auth_headers(token))
    assert resp.status_code == 404


def test_side_photo_available_after_analysis(db_session, sample_scan_paths):
    token = _register_and_login("photoyes@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    _upload(token, code, "front", sample_scan_paths["pokemon_front"])
    _confirm_crop(token, code, "front")

    resp = client.get(f"/submissions/{code}/scans/front/photo", headers=_auth_headers(token))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert len(resp.content) > 0


def test_side_photo_403_for_non_owner(db_session, sample_scan_paths):
    token_a = _register_and_login("photoowner@example.com")
    token_b = _register_and_login("photointruder@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token_a)
    )
    code = create_resp.json()["submission_code"]

    resp = client.get(f"/submissions/{code}/scans/front/photo", headers=_auth_headers(token_b))
    assert resp.status_code == 403


def test_region_crop_available_for_flagged_region(db_session, sample_scan_paths):
    # pokemon_front is generated with whiten_top_left_corner=True (see
    # tests/fixtures/generate_samples.py's write_sample_set), so this
    # corner is guaranteed to come back flagged with a real crop file.
    token = _register_and_login("cropyes@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    _upload(token, code, "front", sample_scan_paths["pokemon_front"])
    _confirm_crop(token, code, "front")

    resp = client.get(
        f"/submissions/{code}/scans/front/regions/corners/top_left/crop", headers=_auth_headers(token)
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert len(resp.content) > 0


def test_region_crop_404_for_region_that_was_never_flagged(db_session, sample_scan_paths):
    token = _register_and_login("cropmissing@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    _upload(token, code, "front", sample_scan_paths["pokemon_front"])
    _confirm_crop(token, code, "front")

    # bottom_right isn't whitened/clipped by pokemon_front's fixture -- no
    # crop file was ever generated for it.
    resp = client.get(
        f"/submissions/{code}/scans/front/regions/corners/bottom_right/crop", headers=_auth_headers(token)
    )
    assert resp.status_code == 404


def test_region_crop_404_for_invalid_region_id(db_session):
    token = _register_and_login("cropinvalid@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    # Uppercase/hyphenated region_id doesn't match _REGION_ID_RE
    # (^[a-z0-9_]+$) -- rejected before ever touching disk.
    resp = client.get(
        f"/submissions/{code}/scans/front/regions/corners/TOP-LEFT/crop", headers=_auth_headers(token)
    )
    assert resp.status_code == 404


def test_raw_scan_404_before_upload(db_session):
    token = _register_and_login("rawnone@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    resp = client.get(f"/submissions/{code}/scans/front/raw", headers=_auth_headers(token))
    assert resp.status_code == 404


def test_raw_scan_available_after_upload(db_session, sample_scan_paths):
    token = _register_and_login("rawyes@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    _upload(token, code, "front", sample_scan_paths["pokemon_front"])
    resp = client.get(f"/submissions/{code}/scans/front/raw", headers=_auth_headers(token))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert len(resp.content) > 0


def test_raw_scan_403_for_non_owner(db_session, sample_scan_paths):
    token_a = _register_and_login("rawowner@example.com")
    token_b = _register_and_login("rawintruder@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token_a)
    )
    code = create_resp.json()["submission_code"]
    _upload(token_a, code, "front", sample_scan_paths["pokemon_front"])

    resp = client.get(f"/submissions/{code}/scans/front/raw", headers=_auth_headers(token_b))
    assert resp.status_code == 403


def test_suggest_crop_404_before_upload(db_session):
    token = _register_and_login("suggestnone@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    resp = client.get(f"/submissions/{code}/scans/front/suggest-crop", headers=_auth_headers(token))
    assert resp.status_code == 404


def test_suggest_crop_returns_four_points_within_bounds(db_session, sample_scan_paths):
    token = _register_and_login("suggestyes@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]
    _upload(token, code, "front", sample_scan_paths["pokemon_front"])

    resp = client.get(f"/submissions/{code}/scans/front/suggest-crop", headers=_auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["points"]) == 4
    assert body["width_px"] > 0 and body["height_px"] > 0
    for x, y in body["points"]:
        assert 0 <= x <= body["width_px"]
        assert 0 <= y <= body["height_px"]


def test_snap_crop_returns_four_points(db_session, sample_scan_paths):
    token = _register_and_login("snapyes@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]
    _upload(token, code, "front", sample_scan_paths["pokemon_front"])
    suggestion = client.get(
        f"/submissions/{code}/scans/front/suggest-crop", headers=_auth_headers(token)
    ).json()

    resp = client.post(
        f"/submissions/{code}/scans/front/snap-crop",
        json={"points": suggestion["points"]},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()["points"]) == 4


def test_snap_crop_404_without_scan(db_session):
    token = _register_and_login("snapnone@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    resp = client.post(
        f"/submissions/{code}/scans/front/snap-crop",
        json={"points": [[0, 0], [10, 0], [10, 10], [0, 10]]},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 404


def test_snap_crop_400_for_wrong_point_count(db_session, sample_scan_paths):
    token = _register_and_login("snapcount@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]
    _upload(token, code, "front", sample_scan_paths["pokemon_front"])

    resp = client.post(
        f"/submissions/{code}/scans/front/snap-crop",
        json={"points": [[0, 0], [10, 0]]},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 400


def test_snap_crop_403_for_non_owner(db_session, sample_scan_paths):
    token_a = _register_and_login("snapowner@example.com")
    token_b = _register_and_login("snapintruder@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token_a)
    )
    code = create_resp.json()["submission_code"]
    _upload(token_a, code, "front", sample_scan_paths["pokemon_front"])

    resp = client.post(
        f"/submissions/{code}/scans/front/snap-crop",
        json={"points": [[0, 0], [10, 0], [10, 10], [0, 10]]},
        headers=_auth_headers(token_b),
    )
    assert resp.status_code == 403


def test_confirm_crop_404_without_scan(db_session):
    token = _register_and_login("confirmnone@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    resp = client.post(
        f"/submissions/{code}/scans/front/confirm-crop",
        json={"points": [[0, 0], [10, 0], [10, 10], [0, 10]]},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 404


def test_confirm_crop_400_for_wrong_point_count(db_session, sample_scan_paths):
    token = _register_and_login("confirmcount@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]
    _upload(token, code, "front", sample_scan_paths["pokemon_front"])

    resp = client.post(
        f"/submissions/{code}/scans/front/confirm-crop",
        json={"points": [[0, 0], [10, 0], [10, 10]]},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 400


def test_confirm_crop_400_for_out_of_bounds_points(db_session, sample_scan_paths):
    token = _register_and_login("confirmbounds@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]
    body = _upload(token, code, "front", sample_scan_paths["pokemon_front"])

    resp = client.post(
        f"/submissions/{code}/scans/front/confirm-crop",
        json={"points": [[-5, 0], [10, 0], [10, 10], [0, 10]]},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 400


def test_confirm_crop_403_for_non_owner(db_session, sample_scan_paths):
    token_a = _register_and_login("confirmowner@example.com")
    token_b = _register_and_login("confirmintruder@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token_a)
    )
    code = create_resp.json()["submission_code"]
    _upload(token_a, code, "front", sample_scan_paths["pokemon_front"])
    suggestion = client.get(
        f"/submissions/{code}/scans/front/suggest-crop", headers=_auth_headers(token_a)
    ).json()

    resp = client.post(
        f"/submissions/{code}/scans/front/confirm-crop",
        json={"points": suggestion["points"]},
        headers=_auth_headers(token_b),
    )
    assert resp.status_code == 403


def test_confirm_crop_409_once_published(db_session, sample_scan_paths):
    token = _register_and_login("confirmpub@example.com")
    create_resp = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    )
    code = create_resp.json()["submission_code"]

    _upload(token, code, "front", sample_scan_paths["pokemon_front"])
    _confirm_crop(token, code, "front")
    _upload(token, code, "back", sample_scan_paths["pokemon_back"])
    _confirm_crop(token, code, "back")

    op_token = _make_operator(db_session, "confirmpubop@example.com")
    client.post(f"/submissions/{code}/approve", headers=_auth_headers(op_token))

    resp = client.post(
        f"/submissions/{code}/scans/front/confirm-crop",
        json={"points": [[0, 0], [10, 0], [10, 10], [0, 10]]},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 409


def _combined_score(body: dict, category: str) -> float:
    for r in body["analysis_results"]:
        if r["side"] == "combined" and r["category"] == category:
            return float(r["raw_score"])
    raise AssertionError(f"no combined {category} result")


def _draft_ready_front(token: str, code: str, sample_scan_paths) -> dict:
    _upload(token, code, "front", sample_scan_paths["pokemon_front"])
    return _confirm_crop(token, code, "front").json()


def test_toggle_region_dismiss_raises_score_and_reverts(db_session, sample_scan_paths):
    # pokemon_front is generated with a whitened top-left corner, so that
    # corner comes back flagged and low-scoring; dismissing it must raise
    # the corners combined score, and restoring it must revert exactly.
    token = _register_and_login("toggle1@example.com")
    code = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    ).json()["submission_code"]
    body = _draft_ready_front(token, code, sample_scan_paths)
    assert body["status"] == "draft_ready"
    before = _combined_score(body, "corners")

    resp = client.post(
        f"/submissions/{code}/regions/toggle",
        json={"region_key": "front:corners:top_left", "dismissed": True},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200
    adjusted = resp.json()
    assert adjusted["dismissed_regions"] == ["front:corners:top_left"]
    assert _combined_score(adjusted, "corners") > before

    restored = client.post(
        f"/submissions/{code}/regions/toggle",
        json={"region_key": "front:corners:top_left", "dismissed": False},
        headers=_auth_headers(token),
    ).json()
    assert restored["dismissed_regions"] == []
    assert _combined_score(restored, "corners") == before


def test_toggle_region_preserves_original_score_for_display(db_session, sample_scan_paths):
    token = _register_and_login("toggle2@example.com")
    code = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    ).json()["submission_code"]
    _draft_ready_front(token, code, sample_scan_paths)

    adjusted = client.post(
        f"/submissions/{code}/regions/toggle",
        json={"region_key": "front:corners:top_left", "dismissed": True},
        headers=_auth_headers(token),
    ).json()

    combined_corners = next(
        r for r in adjusted["analysis_results"] if r["side"] == "combined" and r["category"] == "corners"
    )
    # the pristine auto-detected score is preserved for the "was X.X" display
    original = combined_corners["measurements"]["original_raw_score"]
    assert float(original) < float(combined_corners["raw_score"])


def test_toggle_region_400_for_bad_key(db_session, sample_scan_paths):
    token = _register_and_login("toggle3@example.com")
    code = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    ).json()["submission_code"]
    _draft_ready_front(token, code, sample_scan_paths)

    resp = client.post(
        f"/submissions/{code}/regions/toggle",
        json={"region_key": "front:corners:TOP-LEFT", "dismissed": True},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 400


def test_toggle_region_409_when_not_draft_ready(db_session):
    # A freshly-created submission (no scans) is in 'created', not
    # 'draft_ready' -- findings can't be adjusted yet.
    token = _register_and_login("toggle4@example.com")
    code = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    ).json()["submission_code"]

    resp = client.post(
        f"/submissions/{code}/regions/toggle",
        json={"region_key": "front:corners:top_left", "dismissed": True},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 409


def test_toggle_region_403_for_non_owner(db_session, sample_scan_paths):
    token_a = _register_and_login("toggleowner@example.com")
    token_b = _register_and_login("toggleintruder@example.com")
    code = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token_a)
    ).json()["submission_code"]
    _draft_ready_front(token_a, code, sample_scan_paths)

    resp = client.post(
        f"/submissions/{code}/regions/toggle",
        json={"region_key": "front:corners:top_left", "dismissed": True},
        headers=_auth_headers(token_b),
    )
    assert resp.status_code == 403


def test_delete_submission_removes_rows_and_files(db_session, sample_scan_paths):
    from pathlib import Path

    from zgrader.config import config

    token = _register_and_login("del1@example.com")
    code = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    ).json()["submission_code"]
    _draft_ready_front(token, code, sample_scan_paths)

    scans_dir = Path(config.scans_dir) / code
    reports_dir = Path(config.reports_dir) / code
    assert scans_dir.exists()
    assert reports_dir.exists()

    resp = client.delete(f"/submissions/{code}", headers=_auth_headers(token))
    assert resp.status_code == 204

    assert client.get(f"/submissions/{code}", headers=_auth_headers(token)).status_code == 404
    assert not scans_dir.exists()
    assert not reports_dir.exists()


def test_delete_submission_writes_audit_and_detaches_old_rows(db_session, sample_scan_paths):
    from zgrader.models import AuditLog

    token = _register_and_login("del2@example.com")
    code = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Pikachu"}, headers=_auth_headers(token)
    ).json()["submission_code"]
    _draft_ready_front(token, code, sample_scan_paths)
    # Create a prior audit row tied to this submission by adjusting a finding.
    client.post(
        f"/submissions/{code}/regions/toggle",
        json={"region_key": "front:corners:top_left", "dismissed": True},
        headers=_auth_headers(token),
    )

    client.delete(f"/submissions/{code}", headers=_auth_headers(token))

    # A deletion audit row exists (submission_id null, code in detail).
    deletion = db_session.query(AuditLog).filter(AuditLog.action == "submission_deleted").all()
    assert any(r.detail.get("deleted_code") == code for r in deletion)
    # The earlier toggle audit row survived, with its submission_id nulled so
    # it no longer dangles against the deleted submission.
    toggles = db_session.query(AuditLog).filter(AuditLog.action == "region_dismissed").all()
    assert toggles and all(r.submission_id is None for r in toggles)


def test_delete_submission_403_for_non_owner(db_session, sample_scan_paths):
    token_a = _register_and_login("delowner@example.com")
    token_b = _register_and_login("delintruder@example.com")
    code = client.post(
        "/submissions", json={"game": "Pokemon", "card_name": "Secret"}, headers=_auth_headers(token_a)
    ).json()["submission_code"]

    resp = client.delete(f"/submissions/{code}", headers=_auth_headers(token_b))
    assert resp.status_code == 403
    # still there for the owner
    assert client.get(f"/submissions/{code}", headers=_auth_headers(token_a)).status_code == 200


def test_delete_submission_404_for_missing(db_session):
    token = _register_and_login("delmissing@example.com")
    resp = client.delete("/submissions/SUB-99999", headers=_auth_headers(token))
    assert resp.status_code == 404
