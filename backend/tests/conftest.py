import os
from pathlib import Path

# Must happen before any `zgrader.*` import: zgrader.db creates its engine
# from zgrader.config at import time, so the test DB URL has to be in the
# environment before that first import anywhere in the process.
os.environ["ZGRADER_DATABASE_URL"] = "postgresql+psycopg://zgrader:zgrader@localhost:5432/zgrader_test"
os.environ.setdefault("ZGRADER_REPORTS_DIR", "/tmp/zgrader-test/reports")
os.environ.setdefault("ZGRADER_SCANS_DIR", "/tmp/zgrader-test/scans")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import zgrader.models  # noqa: E402,F401  (registers all tables on Base.metadata)
from zgrader.db import Base  # noqa: E402
from zgrader.seed import seed_all  # noqa: E402

TEST_DATABASE_URL = os.environ["ZGRADER_DATABASE_URL"]
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample_scans"


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL, future=True)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db_session(engine):
    session_factory = sessionmaker(bind=engine, future=True)
    session = session_factory()
    seed_all(session)
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())


@pytest.fixture()
def sample_scan_paths() -> dict[str, Path]:
    from tests.fixtures.generate_samples import write_sample_set

    if not (FIXTURES_DIR / "pokemon_front.png").exists():
        write_sample_set(FIXTURES_DIR)
    return {
        "pokemon_front": FIXTURES_DIR / "pokemon_front.png",
        "pokemon_back": FIXTURES_DIR / "pokemon_back.png",
        "yugioh_front": FIXTURES_DIR / "yugioh_front.png",
        "yugioh_back": FIXTURES_DIR / "yugioh_back.png",
    }
