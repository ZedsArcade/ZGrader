import os
from pathlib import Path

# Must happen before any `zgrader.*` import: zgrader.db creates its engine
# from zgrader.config at import time, so the test DB URL has to be in the
# environment before that first import anywhere in the process.
os.environ["ZGRADER_DATABASE_URL"] = "postgresql+psycopg://zgrader:zgrader@localhost:5432/zgrader_test"
os.environ.setdefault("ZGRADER_REPORTS_DIR", "/tmp/zgrader-test/reports")
os.environ.setdefault("ZGRADER_SCANS_DIR", "/tmp/zgrader-test/scans")

import shutil  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import zgrader.models  # noqa: E402,F401  (registers all tables on Base.metadata)
from zgrader.config import config  # noqa: E402
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
        # Submission codes are DB-count-based and so get reused across
        # tests once the DB rows above are wiped -- without also clearing
        # the filesystem dirs, a later test reusing e.g. SUB-00001 would
        # see scan/report files left behind by an earlier, unrelated test
        # that happened to get the same code.
        shutil.rmtree(config.scans_dir, ignore_errors=True)
        shutil.rmtree(config.reports_dir, ignore_errors=True)


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


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Clear the rate limiter between tests.

    Its counters are process-global by design (one uvicorn worker in
    production), so without this the sixth test to log in would get a 429
    from attempts made by earlier tests.
    """
    from zgrader.api import ratelimit

    ratelimit.reset()
    yield
    ratelimit.reset()


def register_and_verify(client, email: str, password: str = "hunter2pass") -> str:
    """Register a client account, confirm the email, and return a token.

    Registration now issues an unverified account, and creating submissions
    or uploading scans requires verification -- so almost every test needs
    the confirmed state rather than the raw one.
    """
    from zgrader.db import SessionLocal
    from zgrader.models import User

    client.post(
        "/auth/register",
        json={"email": email, "password": password, "accept_terms": True},
    )
    with SessionLocal() as session:
        user = session.query(User).filter(User.email == email.strip().lower()).one()
        token = user.verification_token
    if token:
        client.post(f"/auth/verify/{token}")
    resp = client.post("/auth/login", data={"username": email, "password": password})
    return resp.json()["access_token"]
