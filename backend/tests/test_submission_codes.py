"""Submission codes must never be issued twice.

The code is not just a label. It names the scans and reports directories on
disk, and those are NOT removed by a database delete -- `purge_submission_files`
is the only thing that removes them, and it can fail on a directory owned by an
earlier APP_UID. So a reused code does not merely collide on a unique index; it
drops one customer's submission into another customer's folder.

That is exactly how this failed in production: nine test submissions deleted,
three directories left behind, `COUNT(*) + 1` restarting at SUB-00001, and the
first real analysis dying with PermissionError writing into a directory it did
not own.
"""

from fastapi.testclient import TestClient

from zgrader.api.main import app
from zgrader.models import Submission

from tests.conftest import register_and_verify

client = TestClient(app)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create(token: str) -> str:
    resp = client.post(
        "/submissions",
        json={"game": "Pokemon", "card_name": "Pikachu"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["submission_code"]


def _number(code: str) -> int:
    return int(code.removeprefix("SUB-"))


def test_codes_increase_and_are_unique(db_session):
    token = register_and_verify(client, "codes-unique@example.com")

    codes = [_create(token) for _ in range(3)]

    assert len(set(codes)) == 3, f"a code was issued twice: {codes}"
    numbers = [_number(c) for c in codes]
    assert numbers == sorted(numbers), f"codes went backwards: {codes}"


def test_deleting_a_submission_does_not_free_its_code(db_session):
    """The bug this file exists for. Under COUNT(*) + 1 the code below came
    back around and the next submission inherited a directory full of someone
    else's scans."""
    token = register_and_verify(client, "codes-delete@example.com")

    first = _create(token)
    client.delete(f"/submissions/{first}", headers=_auth(token))
    second = _create(token)

    assert second != first, "a deleted submission's code was reissued"
    assert _number(second) > _number(first)


def test_emptying_the_table_does_not_restart_the_numbering(db_session):
    """Deleting *every* submission used to be the safe case -- the counter
    restarted consistently. It is not safe: the directories outlive the rows,
    so restarting means walking straight back over them."""
    token = register_and_verify(client, "codes-empty@example.com")

    codes = [_create(token) for _ in range(2)]
    for code in codes:
        client.delete(f"/submissions/{code}", headers=_auth(token))
    assert db_session.query(Submission).count() == 0

    after = _create(token)

    assert _number(after) > max(_number(c) for c in codes)


def test_a_rolled_back_create_leaves_a_gap_rather_than_reusing(db_session):
    """nextval is non-transactional, so a create that fails still consumes its
    number. That is the right trade: a gap in the sequence is harmless, and
    reissuing the number is what this whole file is about."""
    token = register_and_verify(client, "codes-gap@example.com")
    first = _create(token)

    # Consume a number outside any request, the way a rolled-back transaction
    # would have done.
    from zgrader.models.submission import submission_code_seq

    db_session.execute(submission_code_seq.next_value().select())
    db_session.commit()

    second = _create(token)

    assert _number(second) > _number(first) + 1, "the skipped number was reused"


def test_the_code_matches_the_scans_directory_that_was_created(db_session, tmp_path):
    """The code and the directory are the same fact. If they can disagree, the
    on-disk collision is back by another route."""
    from pathlib import Path

    from zgrader.config import config

    token = register_and_verify(client, "codes-dir@example.com")
    code = _create(token)

    assert (Path(config.scans_dir) / code).is_dir(), (
        f"no scans directory was created for {code}"
    )
