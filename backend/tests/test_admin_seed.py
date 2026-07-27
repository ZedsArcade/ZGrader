from sqlalchemy import func

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


def test_capitalised_admin_email_matches_the_stored_lowercase_account(db_session, monkeypatch):
    """The regression that left a live deployment with no operator.

    Addresses are stored lowercased and guarded by a unique index on
    lower(email). A capitalised ZGRADER_ADMIN_EMAIL used to miss the existing
    row, try to insert a second one, and blow up on that index -- silently,
    because startup swallows seeding errors.
    """
    db_session.add(
        User(
            email="mixed@example.com",
            hashed_password=hash_password("their-own-pass"),
            role=UserRole.client,
        )
    )
    db_session.commit()

    monkeypatch.setattr(config, "admin_email", "Mixed@Example.COM")
    monkeypatch.setattr(config, "admin_password", "whatever")
    seed_admin_user(db_session)

    users = db_session.query(User).filter(func.lower(User.email) == "mixed@example.com").all()
    assert len(users) == 1, "a second row was created instead of matching the existing one"
    assert users[0].role == UserRole.operator
    assert users[0].email == "mixed@example.com", "the stored address must stay normalised"


def test_new_admin_email_is_stored_lowercased(db_session, monkeypatch):
    monkeypatch.setattr(config, "admin_email", "  Shouty@Example.COM  ")
    monkeypatch.setattr(config, "admin_password", "s3cret-pass")

    seed_admin_user(db_session)

    user = db_session.query(User).one()
    assert user.email == "shouty@example.com"
    # And it must be loginable, which is the whole point -- login looks the
    # address up case-insensitively against the normalised column.
    assert verify_password("s3cret-pass", user.hashed_password)


def test_reset_flag_replaces_the_password_and_signs_sessions_out(db_session, monkeypatch):
    db_session.add(
        User(
            email="locked@example.com",
            hashed_password=hash_password("forgotten-pass"),
            role=UserRole.operator,
            is_verified=True,
        )
    )
    db_session.commit()
    original_version = db_session.query(User).one().token_version

    monkeypatch.setattr(config, "admin_email", "locked@example.com")
    monkeypatch.setattr(config, "admin_password", "recovery-pass")
    monkeypatch.setattr(config, "admin_reset_password", True)
    seed_admin_user(db_session)

    user = db_session.query(User).one()
    assert verify_password("recovery-pass", user.hashed_password)
    # Whoever locked the account out may be holding a live token; the reset
    # has to retire it, exactly as a password change does.
    assert user.token_version == original_version + 1


def test_reset_flag_defaults_off_so_a_redeploy_keeps_your_password(db_session, monkeypatch):
    """A password set in the app must survive restarts.

    Otherwise every redeploy silently reverts it to whatever is in the
    environment file, which is a genuinely horrible thing to debug.
    """
    db_session.add(
        User(
            email="steady@example.com",
            hashed_password=hash_password("chosen-in-the-app"),
            role=UserRole.operator,
            is_verified=True,
        )
    )
    db_session.commit()

    monkeypatch.setattr(config, "admin_email", "steady@example.com")
    monkeypatch.setattr(config, "admin_password", "stale-env-value")
    seed_admin_user(db_session)

    user = db_session.query(User).one()
    assert verify_password("chosen-in-the-app", user.hashed_password)
