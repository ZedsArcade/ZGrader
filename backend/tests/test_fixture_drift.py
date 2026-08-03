"""The analysis pipeline's numbers must not move without someone saying so.

`scripts/fixture_drift.py` reports drift; this makes it bite. A harness nobody
remembers to run is a harness that reports the regression six phases later,
when it is no longer obvious which change caused it.

When this fails legitimately -- a phase deliberately retunes something -- the
fix is to inspect the reported deltas, satisfy yourself they are the ones you
intended, and run:

    python scripts/fixture_drift.py --update

The resulting diff in drift_baseline.json is the reviewable record of what a
change actually did to each kind of card.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fixture_drift import (  # noqa: E402
    BASELINE_PATH,
    TOLERANCE,
    diff,
    measure_all_synthetic,
)

from tests.fixtures.generate_samples import build_fixture, fixture_names  # noqa: E402


@pytest.fixture(scope="module")
def current_metrics() -> dict[str, dict[str, float]]:
    """Measured once; every assertion below reads the same run."""
    return measure_all_synthetic()


@pytest.fixture(scope="module")
def baseline() -> dict[str, dict[str, float]]:
    assert BASELINE_PATH.is_file(), (
        f"No drift baseline at {BASELINE_PATH}. Create one with: "
        "python scripts/fixture_drift.py --update"
    )
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", fixture_names())
def test_fixture_is_deterministic(name):
    """The baseline is only meaningful if a fixture is the same every time.

    A fixture that varied between runs would report drift that isn't there,
    and the first thing anyone would do is stop trusting the alarm.
    """
    assert np.array_equal(build_fixture(name), build_fixture(name))


def test_baseline_covers_every_fixture(current_metrics, baseline):
    """A new fixture without a baseline entry is invisible to the check, which
    is the quiet way this stops working."""
    missing = sorted(set(current_metrics) - set(baseline))
    stale = sorted(set(baseline) - set(current_metrics))
    assert not missing, (
        f"Fixtures with no baseline entry: {missing}. "
        "Run: python scripts/fixture_drift.py --update"
    )
    assert not stale, (
        f"Baseline entries for fixtures that no longer exist: {stale}. "
        "Run: python scripts/fixture_drift.py --update"
    )


@pytest.mark.parametrize("name", fixture_names())
def test_no_metric_drift(name, current_metrics, baseline):
    """Parametrised per fixture so a failure names the card type that moved,
    not just 'the pipeline changed'."""
    changes = diff({name: baseline.get(name, {})}, {name: current_metrics[name]})
    assert not changes, "\n".join(
        f"{metric}: {before} -> {after}" for _f, metric, before, after in changes
    )


def test_tolerance_is_tight_enough_to_be_useful():
    """Guards the guard. A tolerance loose enough to swallow a real retune
    would leave every other test here passing while measuring nothing --
    0.002 on a 0-10 score is a hundredth of the smallest change worth
    shipping."""
    assert TOLERANCE <= 0.01
