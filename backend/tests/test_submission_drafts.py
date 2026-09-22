"""Photo drafts: created without a name, capped per account, never charged
until analysis scores them. Mail-in submissions are exempt from the cap --
their card is in the post and there is nothing for the customer to finish.
"""

from zgrader.analysis import pipeline
from zgrader.auth.security import hash_password
from zgrader.config import config
from zgrader.models import User, UserRole

from tests import checkflow_helpers as h


def test_a_draft_needs_no_card_name(db_session):
    token = h.login("draft-noname@example.com")
    resp = h.create(token)
    assert resp.status_code == 201
    assert resp.json()["card"]["card_name"] is None
    assert resp.json()["mail_in"] is False


def test_a_blank_card_name_is_stored_as_none(db_session):
    token = h.login("draft-blank@example.com")
    assert h.create(token, card_name="   ").json()["card"]["card_name"] is None


def test_mail_in_requires_a_card_name(db_session):
    """The operator matches the physical card to its submission by name."""
    token = h.login("draft-mailin-noname@example.com")
    assert h.create(token, mail_in=True).status_code == 422
    assert h.create(token, mail_in=True, card_name="Charizard").status_code == 201


def test_a_fourth_open_draft_is_refused_with_409(db_session):
    token = h.login("draft-cap@example.com")
    for _ in range(3):
        h.create_code(token)

    refused = h.create(token)

    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "too_many_drafts"


def test_mail_in_submissions_do_not_count_toward_the_cap(db_session):
    token = h.login("draft-cap-mailin@example.com")
    for _ in range(3):
        h.create_code(token)
    assert h.create(token, mail_in=True, card_name="Posted").status_code == 201


def test_an_analysed_draft_no_longer_counts(db_session, sample_scan_paths, monkeypatch):
    h.set_free_limit(db_session, 10)
    token = h.login("draft-cap-analysed@example.com")
    codes = [h.create_code(token) for _ in range(3)]
    h.upload(token, codes[0], "front", sample_scan_paths["pokemon_front"])
    monkeypatch.setattr(pipeline, "run_analysis", h.fake_analysis(9.0))
    assert h.confirm(token, codes[0], "front").status_code == 200

    assert h.create(token).status_code == 201


def test_operators_are_exempt_from_the_cap(db_session):
    db_session.add(
        User(email="draft-op@example.com", hashed_password=hash_password("hunter2pass"), role=UserRole.operator, is_verified=True)
    )
    db_session.commit()
    token = h.client.post(
        "/auth/login", data={"username": "draft-op@example.com", "password": "hunter2pass"}
    ).json()["access_token"]
    for _ in range(4):
        assert h.create(token).status_code == 201


def test_the_cap_comes_from_config(db_session, monkeypatch):
    monkeypatch.setattr(config, "max_open_drafts", 1)
    token = h.login("draft-cap-config@example.com")
    h.create_code(token)
    assert h.create(token).status_code == 409
