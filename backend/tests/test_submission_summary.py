"""The dashboard list says which card each row is and how it scored, and
costs the same number of queries however many rows there are."""

from sqlalchemy import event

from zgrader.analysis import pipeline
from zgrader.auth.security import hash_password
from zgrader.db import engine
from zgrader.models import Card, Submission, SubmissionLanguage, SubmissionStatus, User
from zgrader.models.settings import get_or_create_settings
from zgrader.reports.builder import build_report_context

from tests import checkflow_helpers as h


def _rows(token) -> dict:
    resp = h.client.get("/submissions", headers=h.headers(token))
    assert resp.status_code == 200
    return {row["submission_code"]: row for row in resp.json()}


def test_the_list_carries_name_game_scores_and_charge(db_session, sample_scan_paths, monkeypatch):
    h.set_free_limit(db_session, 5)
    token = h.login("summary-fields@example.com")
    named = h.create_code(token, card_name="Pikachu")
    unnamed = h.create_code(token)
    h.upload(token, named, "front", sample_scan_paths["pokemon_front"])
    monkeypatch.setattr(pipeline, "run_analysis", h.fake_analysis(9.0))
    h.confirm(token, named, "front")

    rows = _rows(token)

    assert rows[named]["card_name"] == "Pikachu"
    assert rows[named]["game"] == "Pokemon"
    assert rows[named]["charged"] is True
    assert rows[named]["scores"] == {"centering": 9.0, "corners": 9.0, "edges": 9.0, "surface": 9.0}
    assert rows[unnamed]["card_name"] is None
    assert rows[unnamed]["charged"] is False
    assert rows[unnamed]["mail_in"] is False
    assert rows[unnamed]["scores"] == {}


def test_an_unmeasurable_category_is_null_not_zero(db_session, sample_scan_paths, monkeypatch):
    token = h.login("summary-null@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])
    monkeypatch.setattr(pipeline, "run_analysis", h.fake_analysis(None))
    h.confirm(token, code, "front")

    assert set(_rows(token)[code]["scores"].values()) == {None}


def test_listing_costs_the_same_queries_for_one_row_as_for_three(db_session):
    token = h.login("summary-queries@example.com")
    h.create_code(token)

    def count() -> int:
        statements: list[str] = []

        def listener(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", listener)
        try:
            _rows(token)
        finally:
            event.remove(engine, "before_cursor_execute", listener)
        return len(statements)

    one = count()
    h.create_code(token)
    h.create_code(token)
    assert count() == one


def test_the_report_names_an_untitled_card_in_its_language(db_session):
    user = User(email="summary-pdf@example.com", hashed_password=hash_password("hunter2pass"), is_verified=True)
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code="SUB-90903",
        user_id=user.id,
        status=SubmissionStatus.draft_ready,
        language=SubmissionLanguage.es,
    )
    db_session.add(submission)
    db_session.flush()
    db_session.add(Card(submission_id=submission.id, game="Pokemon", card_name=None))
    db_session.flush()
    db_session.refresh(submission)

    context = build_report_context(submission, get_or_create_settings(db_session))

    assert context["card"]["card_name"] == "Carta sin nombre"
