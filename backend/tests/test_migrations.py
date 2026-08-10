"""Every migration, applied to an empty database, the way production does it.

AGENTS.md says it plainly: the test database is not the production schema.
`conftest.py` builds it with `Base.metadata.create_all`, which creates what the
models declare and never runs a single migration. So a broken migration passes
the entire suite.

That is not hypothetical. `b7f4c2e19a83` shipped using
`sa.Enum(..., create_type=False)` -- a postgresql.ENUM parameter that the
generic sa.Enum accepts and silently ignores -- so `create_table` re-emitted
CREATE TYPE for an enum the migration had just created, and the whole thing
died with DuplicateObject. Alembic runs a migration in one transaction, so it
rolled back completely: no table, no type, `alembic_version` unmoved. It looked
like the migration had never been attempted rather than that it had failed.

In production that stopped the `migrate` service completing, which stopped
`backend` and `worker` -- both wait on `service_completed_successfully` -- from
ever starting. The stack had to be started by hand after every redeploy, and
nothing in the test suite noticed for six merges.

Alembic runs in a SUBPROCESS here, which matters. `alembic/env.py` sets the URL
from `zgrader_config.database_url` -- a singleton built at import time -- so an
in-process run ignores whatever URL the caller passes and migrates the *test*
database instead. The first version of this file did exactly that. A subprocess
with ZGRADER_DATABASE_URL set is also precisely how the migrate container does
it, so this exercises the real path rather than an approximation of it.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from tests.conftest import TEST_DATABASE_URL

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _scratch_url() -> str:
    """A database of this test's own, beside the suite's.

    Deliberately not the suite's database: this drops and recreates it, and
    conftest is entitled to assume its own schema stays put.
    """
    return re.sub(r"/([^/?]+)(\?|$)", r"/\1_migrations\2", TEST_DATABASE_URL)


@pytest.fixture()
def scratch_database():
    url = _scratch_url()
    # Belt and braces after getting this wrong once: if the substitution ever
    # fails to change the name, refuse rather than drop the suite's database.
    assert url != TEST_DATABASE_URL, "scratch URL is the suite's own database"

    name = url.rsplit("/", 1)[-1].split("?")[0]
    admin_url = url.rsplit("/", 1)[0] + "/postgres"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    except Exception as exc:  # noqa: BLE001
        admin.dispose()
        pytest.skip(f"cannot create a scratch database for migration tests: {exc}")

    yield url

    with admin.connect() as conn:
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :name AND pid <> pg_backend_pid()"
            ),
            {"name": name},
        )
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
    admin.dispose()


def _alembic(url: str, *args: str) -> None:
    """Run alembic against `url`, the way the migrate container does."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_ROOT,
        env={**os.environ, "ZGRADER_DATABASE_URL": url},
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"
    )


def _query(url: str, sql: str):
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return conn.execute(text(sql)).scalar()
    finally:
        engine.dispose()


def test_the_whole_chain_applies_to_an_empty_database(scratch_database):
    """The test that would have caught b7f4c2e19a83 before it shipped."""
    _alembic(scratch_database, "upgrade", "head")

    assert _query(scratch_database, "SELECT version_num FROM alembic_version"), (
        "migrations ran but stamped no version"
    )
    # The index created by raw SQL rather than by a model. It does not exist in
    # the create_all schema at all, which is the other half of why migrations
    # need a test of their own.
    assert _query(
        scratch_database, "SELECT 1 FROM pg_indexes WHERE indexname = 'ix_users_email_lower'"
    ), "ix_users_email_lower is missing -- case-insensitive emails are unenforced"


def test_the_head_migration_can_be_reversed_and_reapplied(scratch_database):
    """A downgrade nobody runs is a downgrade nobody knows is broken.

    Also where a NameError in `downgrade()` surfaces -- fixing b7f4c2e19a83
    renamed a module-level constant and left the downgrade referencing the old
    one, which no other test would ever have executed.
    """
    _alembic(scratch_database, "upgrade", "head")
    before = _query(scratch_database, "SELECT version_num FROM alembic_version")

    _alembic(scratch_database, "downgrade", "-1")
    _alembic(scratch_database, "upgrade", "head")

    assert _query(scratch_database, "SELECT version_num FROM alembic_version") == before


def test_the_migrated_schema_has_the_tables_the_models_declare(scratch_database):
    """Catches a model added without a migration -- which passes every other
    test in the suite, because create_all builds tables straight from the
    models and never consults alembic."""
    _alembic(scratch_database, "upgrade", "head")

    import zgrader.models  # noqa: F401 -- registers every model on Base
    from zgrader.db import Base

    engine = create_engine(scratch_database)
    try:
        with engine.connect() as conn:
            migrated = set(
                conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                ).scalars()
            )
    finally:
        engine.dispose()

    missing = sorted(set(Base.metadata.tables) - migrated)
    assert not missing, f"models declare tables no migration creates: {missing}"
