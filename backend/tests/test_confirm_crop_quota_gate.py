"""An uncharged draft cannot be analysed once the account is out of checks.

The refusal has to come before the crop is saved. confirm-crop stores the
crop points first; a 402 raised after that would leave the front confirmed,
and the worker's poll -- which never refuses -- would then analyse it anyway
and charge the account past its limit.
"""

import threading

from zgrader.api import capacity
from zgrader.models import User

from tests import checkflow_helpers as h


def test_confirm_is_refused_with_402_before_the_crop_is_saved(db_session, sample_scan_paths):
    h.set_free_limit(db_session, 1)
    token = h.login("gate-refused@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])
    h.spend(db_session, "gate-refused@example.com", 1)

    resp = h.confirm(token, code, "front")

    assert resp.status_code == 402
    assert resp.json()["detail"]["limit"] == 1
    body = h.detail(token, code)
    assert body["confirmed_sides"] == []
    assert body["status"] in ("created", "awaiting_scans")
    assert body["charged"] is False


def test_a_charged_submission_can_add_its_back_when_out_of_checks(db_session, sample_scan_paths):
    """The back completes a check already paid for; it is not a new one."""
    h.set_free_limit(db_session, 1)
    token = h.login("gate-back@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])
    assert h.confirm(token, code, "front").json()["charged"] is True
    assert h.quota(token)["remaining"] == 0

    h.upload(token, code, "back", sample_scan_paths["pokemon_back"])
    assert h.confirm(token, code, "back").status_code == 200


def test_a_capacity_refusal_leaves_the_crop_unsaved(db_session, sample_scan_paths):
    """A capacity refusal (409 per-user, 503 global) has to come before the
    crop is saved too, for the same reason as the quota 402 above: a refused
    request that left the crop stored would confirm the front anyway, and the
    worker's poll would analyse and charge it later with no quota check at
    all."""
    token = h.login("capacity-refused@example.com")
    user = db_session.query(User).filter(User.email == "capacity-refused@example.com").one()
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])

    entered, release = threading.Event(), threading.Event()

    def hold():
        with capacity.analysis_slot(user.id, "SUB-OTHER-HOLD"):
            entered.set()
            release.wait(timeout=5)

    holder = threading.Thread(target=hold)
    holder.start()
    try:
        assert entered.wait(timeout=5), "holder thread never entered the guarded section"
        resp = h.confirm(token, code, "front")
    finally:
        release.set()
        holder.join(timeout=5)

    assert resp.status_code == 409, resp.text
    body = h.detail(token, code)
    assert body["confirmed_sides"] == []
    assert body["charged"] is False
