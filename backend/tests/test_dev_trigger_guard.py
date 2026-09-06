"""The dev entrypoint must not be able to write to production.

conftest.py refuses to run the suite unless the database name ends in
'_test', for the same reason: on the development machine 127.0.0.1:5432 is an
SSH tunnel to the deployed Postgres, so a mistyped URL is not a local mistake.
dev_trigger.py had no equivalent guard at all.
"""

import pytest

from zgrader.dev_trigger import refuse_unsafe_database


def test_a_production_looking_url_is_refused():
    with pytest.raises(RuntimeError, match="refusing"):
        refuse_unsafe_database("postgresql+psycopg://zgrader:pw@localhost:5432/zgrader")


def test_a_test_database_is_allowed():
    refuse_unsafe_database("postgresql+psycopg://zgrader:pw@localhost:5432/zgrader_test")


def test_a_dev_database_is_allowed():
    refuse_unsafe_database("postgresql+psycopg://zgrader:pw@localhost:5432/zgrader_dev")
