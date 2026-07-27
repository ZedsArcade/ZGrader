"""Service tier banner images: upload, public read, delete.

These are the first images the API serves without authentication, so the
tests care as much about who can reach each endpoint as about the bytes.
"""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from zgrader import images
from zgrader.api.main import app
from zgrader.auth.security import hash_password
from zgrader.config import config
from zgrader.models import User, UserRole

client = TestClient(app)


def _png_bytes(size=(400, 300), mode="RGB") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, "red").save(buf, format="PNG")
    return buf.getvalue()


def _operator_token(db_session, email: str) -> str:
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


def _client_token(email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "hunter2pass", "accept_terms": True})
    return client.post(
        "/auth/login", data={"username": email, "password": "hunter2pass"}
    ).json()["access_token"]


@pytest.fixture()
def op_headers(db_session):
    return {"Authorization": f"Bearer {_operator_token(db_session, 'imgop@example.com')}"}


def test_manifest_is_empty_before_anything_is_uploaded(db_session):
    resp = client.get("/catalog/service-images")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_upload_stores_a_reencoded_jpeg_and_publishes_it(db_session, op_headers):
    resp = client.put(
        "/admin/service-images/analysis",
        files={"file": ("banner.png", _png_bytes(), "image/png")},
        headers=op_headers,
    )
    assert resp.status_code == 204

    # Stored as JPEG regardless of what was uploaded -- the bytes on disk are
    # ones Pillow produced, which is what makes serving them publicly safe.
    path = images.service_image_path(config.public_media_dir, "analysis")
    assert path.is_file()
    assert path.suffix == ".jpg"
    with Image.open(path) as stored:
        assert stored.format == "JPEG"

    manifest = client.get("/catalog/service-images").json()
    assert set(manifest) == {"analysis"}
    assert isinstance(manifest["analysis"], int)

    served = client.get("/catalog/service-images/analysis")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/jpeg"


def test_oversized_images_are_scaled_down(db_session, op_headers):
    client.put(
        "/admin/service-images/subscription",
        files={"file": ("huge.png", _png_bytes(size=(3000, 2000)), "image/png")},
        headers=op_headers,
    )
    with Image.open(images.service_image_path(config.public_media_dir, "subscription")) as stored:
        assert stored.width <= images.SERVICE_IMAGE_MAX_SIZE[0]
        assert stored.height <= images.SERVICE_IMAGE_MAX_SIZE[1]


def test_transparent_png_is_accepted(db_session, op_headers):
    """JPEG has no alpha channel, so an RGBA upload has to be converted
    rather than blowing up in the save."""
    resp = client.put(
        "/admin/service-images/packaging",
        files={"file": ("alpha.png", _png_bytes(mode="RGBA"), "image/png")},
        headers=op_headers,
    )
    assert resp.status_code == 204


def test_serving_a_service_image_needs_no_token(db_session, op_headers):
    """Every other image route in the API requires a Bearer token because it
    serves a customer's card. These are marketing images on a public page."""
    client.put(
        "/admin/service-images/restoration",
        files={"file": ("b.png", _png_bytes(), "image/png")},
        headers=op_headers,
    )
    assert client.get("/catalog/service-images").status_code == 200
    assert client.get("/catalog/service-images/restoration").status_code == 200


def test_only_operators_can_upload_or_delete(db_session):
    headers = {"Authorization": f"Bearer {_client_token('imgclient@example.com')}"}
    resp = client.put(
        "/admin/service-images/analysis",
        files={"file": ("b.png", _png_bytes(), "image/png")},
        headers=headers,
    )
    assert resp.status_code == 403
    assert client.delete("/admin/service-images/analysis", headers=headers).status_code == 403
    # Anonymous too.
    assert client.put(
        "/admin/service-images/analysis",
        files={"file": ("b.png", _png_bytes(), "image/png")},
    ).status_code == 401


def test_unknown_slug_is_rejected_everywhere(db_session, op_headers):
    """The slug picks a filename, so anything outside the fixed tier list is
    refused before the filesystem is touched."""
    for slug in ("nope", "../../etc/passwd", "analysis.jpg"):
        assert (
            client.put(
                f"/admin/service-images/{slug}",
                files={"file": ("b.png", _png_bytes(), "image/png")},
                headers=op_headers,
            ).status_code
            == 404
        )
        assert client.get(f"/catalog/service-images/{slug}").status_code == 404


def test_a_non_image_upload_is_refused(db_session, op_headers):
    resp = client.put(
        "/admin/service-images/collection",
        files={"file": ("evil.png", b"<script>alert(1)</script>", "image/png")},
        headers=op_headers,
    )
    assert resp.status_code == 400
    assert not images.service_image_path(config.public_media_dir, "collection").exists()


def test_oversized_upload_is_refused(db_session, op_headers):
    resp = client.put(
        "/admin/service-images/collection",
        files={"file": ("big.png", b"\x89PNG\r\n\x1a\n" + b"x" * images.MAX_UPLOAD_BYTES, "image/png")},
        headers=op_headers,
    )
    assert resp.status_code == 413


def test_upload_replaces_and_bumps_the_version(db_session, op_headers):
    import os
    import time

    client.put(
        "/admin/service-images/personalised",
        files={"file": ("a.png", _png_bytes(size=(400, 300)), "image/png")},
        headers=op_headers,
    )
    first = client.get("/catalog/service-images").json()["personalised"]

    # mtime has one-second resolution, so age the file rather than sleeping.
    path = images.service_image_path(config.public_media_dir, "personalised")
    os.utime(path, (time.time() - 60, time.time() - 60))
    aged = client.get("/catalog/service-images").json()["personalised"]
    assert aged < first or aged != first

    client.put(
        "/admin/service-images/personalised",
        files={"file": ("b.png", _png_bytes(size=(500, 200)), "image/png")},
        headers=op_headers,
    )
    assert client.get("/catalog/service-images").json()["personalised"] != aged


def test_delete_removes_it_from_the_manifest(db_session, op_headers):
    client.put(
        "/admin/service-images/analysis",
        files={"file": ("b.png", _png_bytes(), "image/png")},
        headers=op_headers,
    )
    assert "analysis" in client.get("/catalog/service-images").json()

    assert client.delete("/admin/service-images/analysis", headers=op_headers).status_code == 204
    assert client.get("/catalog/service-images").json() == {}
    assert client.get("/catalog/service-images/analysis").status_code == 404
    # Deleting again is not an error -- the desired end state already holds.
    assert client.delete("/admin/service-images/analysis", headers=op_headers).status_code == 204


def test_disclaimer_default_names_ace(db_session):
    """ACE is named in the non-affiliation statement printed on every report."""
    from zgrader.models.settings import get_or_create_settings

    assert "ACE" in get_or_create_settings(db_session).disclaimer_text
