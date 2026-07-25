from zgrader.auth.security import hash_password, verify_password
from zgrader.config import config
from zgrader.models import User, UserRole
from zgrader.seed import seed_admin_user


def test_seed_creates_operator(db_session, monkeypatch):
    monkeypatch.setattr(config, "admin_email", "boss@example.com")
    monkeypatch.setattr(config, "admin_password", "s3cret-pass")

    seed_admin_user(db_session)

    user = db_session.query(User).filter(User.email == "boss@example.com").first()
    assert user is not None
    assert user.role == UserRole.operator
    assert user.is_verified is True
    assert verify_password("s3cret-pass", user.hashed_password)


def test_seed_is_idempotent(db_session, monkeypatch):
    monkeypatch.setattr(config, "admin_email", "boss2@example.com")
    monkeypatch.setattr(config, "admin_password", "first-pass")
    seed_admin_user(db_session)
    original_hash = db_session.query(User).filter(User.email == "boss2@example.com").first().hashed_password

    # A second run with a different password must NOT overwrite an existing
    # operator's credentials.
    monkeypatch.setattr(config, "admin_password", "different-pass")
    seed_admin_user(db_session)

    users = db_session.query(User).filter(User.email == "boss2@example.com").all()
    assert len(users) == 1
    assert users[0].hashed_password == original_hash


def test_seed_promotes_existing_client(db_session, monkeypatch):
    db_session.add(
        User(
            email="existing@example.com",
            hashed_password=hash_password("their-own-pass"),
            role=UserRole.client,
        )
    )
    db_session.commit()

    monkeypatch.setattr(config, "admin_email", "existing@example.com")
    monkeypatch.setattr(config, "admin_password", "ignored-when-promoting")
    seed_admin_user(db_session)

    user = db_session.query(User).filter(User.email == "existing@example.com").first()
    assert user.role == UserRole.operator
    # Promotion keeps the user's own password, it doesn't reset it.
    assert verify_password("their-own-pass", user.hashed_password)


def test_seed_noop_without_env(db_session, monkeypatch):
    monkeypatch.setattr(config, "admin_email", None)
    monkeypatch.setattr(config, "admin_password", None)

    seed_admin_user(db_session)

    assert db_session.query(User).count() == 0
