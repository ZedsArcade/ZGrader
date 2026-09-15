"""Card details are labels the customer can change at any time -- except foil,
which changes the analysis (assessment.CARD_IS_FOIL) and is therefore locked
once the card has been analysed."""

from zgrader.analysis import pipeline

from tests import checkflow_helpers as h


def _patch(token, code, body):
    return h.client.patch(f"/submissions/{code}/card", json=body, headers=h.headers(token))


def test_labels_can_be_set_and_cleared(db_session):
    token = h.login("card-labels@example.com")
    code = h.create_code(token, set_name="Base")

    resp = _patch(token, code, {"card_name": " Pikachu ", "set_name": None, "card_number": "58"})

    assert resp.status_code == 200
    card = resp.json()["card"]
    assert card["card_name"] == "Pikachu"
    assert card["set_name"] is None
    assert card["card_number"] == "58"


def test_omitted_fields_are_left_alone(db_session):
    token = h.login("card-omitted@example.com")
    code = h.create_code(token, card_name="Pikachu", set_name="Base")
    card = _patch(token, code, {"card_number": "58"}).json()["card"]
    assert card["card_name"] == "Pikachu"
    assert card["set_name"] == "Base"


def test_foil_can_change_before_analysis(db_session):
    token = h.login("card-foil-before@example.com")
    code = h.create_code(token)
    assert _patch(token, code, {"foil": True}).json()["card"]["foil"] is True


def test_foil_is_locked_after_analysis(db_session, sample_scan_paths, monkeypatch):
    token = h.login("card-foil-after@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])
    monkeypatch.setattr(pipeline, "run_analysis", h.fake_analysis(9.0))
    h.confirm(token, code, "front")

    assert _patch(token, code, {"foil": True}).status_code == 409
    # Sending the value it already has is not a change, and names still edit.
    assert _patch(token, code, {"foil": False, "card_name": "Later"}).status_code == 200


def test_unknown_fields_are_refused(db_session):
    token = h.login("card-extra@example.com")
    code = h.create_code(token)
    assert _patch(token, code, {"game": "Magic"}).status_code == 422


def test_an_overlong_name_is_a_422(db_session):
    token = h.login("card-long@example.com")
    code = h.create_code(token)
    assert _patch(token, code, {"card_name": "x" * 201}).status_code == 422


def test_someone_elses_card_is_403(db_session):
    owner = h.login("card-owner@example.com")
    code = h.create_code(owner)
    other = h.login("card-other@example.com")
    assert _patch(other, code, {"card_name": "Mine now"}).status_code == 403
