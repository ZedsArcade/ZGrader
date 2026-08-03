"""Per-fixture metric drift for the analysis pipeline.

Every change under `analysis/` moves numbers. The question that matters is
*which* numbers, on *which* kind of card -- a retune that sharpens corner
detection on a bordered card while quietly wrecking full-art centering looks
like an improvement if you only watch the aggregate.

So: run every synthetic fixture through the detectors, compare against a
committed baseline, and print what moved and by how much.

    python scripts/fixture_drift.py            # report drift vs the baseline
    python scripts/fixture_drift.py --update   # accept current values
    python scripts/fixture_drift.py --json     # machine-readable

`--update` is the deliberate act that records "this change was intended". The
diff it produces in `tests/fixtures/drift_baseline.json` is the reviewable
artefact -- a phase that retunes a threshold should show exactly which
fixtures moved, and a reviewer should be able to object to any that shouldn't
have.

Real photographs in tests/fixtures/real_scans/ are measured too when present,
but never gain a baseline entry: their ground truth is unknown and their
numbers are for eyeballing, not asserting. See that directory's README.
"""

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import cv2  # noqa: E402

from tests.fixtures.generate_samples import (  # noqa: E402
    build_fixture,
    card_size_mm,
    fixture_names,
)
from zgrader.analysis.fixture_metrics import measure_image  # noqa: E402

BASELINE_PATH = BACKEND_ROOT / "tests" / "fixtures" / "drift_baseline.json"
REAL_SCANS_DIR = BACKEND_ROOT / "tests" / "fixtures" / "real_scans"

# Below this, treat a difference as numerical noise rather than drift. Metrics
# are already rounded to 3dp by fixture_metrics, so this only absorbs the last
# place -- a genuine retune moves scores far more than this.
TOLERANCE = 0.002

# Real photos have no ground truth, so their physical size has to be declared.
# Standard TCG stock unless a filename says otherwise.
_DEFAULT_CARD_MM = (63.0, 88.0)


def measure_all_synthetic() -> dict[str, dict[str, float]]:
    results = {}
    for name in fixture_names():
        width_mm, height_mm = card_size_mm(name)
        results[name] = measure_image(build_fixture(name), width_mm, height_mm)
    return results


def measure_real_scans() -> dict[str, dict[str, float]]:
    """Measure any real photographs that have been dropped in.

    Returns empty when the directory is absent or empty, which is the normal
    state for a fresh clone without git-LFS content pulled -- this must never
    be the reason the harness fails.
    """
    if not REAL_SCANS_DIR.is_dir():
        return {}
    results = {}
    for path in sorted(REAL_SCANS_DIR.iterdir()):
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
            continue
        image = cv2.imread(str(path))
        if image is None:
            print(f"  ! could not read {path.name}", file=sys.stderr)
            continue
        try:
            results[path.stem] = measure_image(image, *_DEFAULT_CARD_MM)
        except Exception as exc:  # noqa: BLE001 -- one bad photo must not stop the run
            print(f"  ! {path.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
    return results


def load_baseline() -> dict[str, dict[str, float]]:
    if not BASELINE_PATH.is_file():
        return {}
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def diff(
    baseline: dict[str, dict[str, float]], current: dict[str, dict[str, float]]
) -> list[tuple[str, str, float | None, float | None]]:
    """(fixture, metric, before, after) for everything that moved.

    A None on either side means the fixture or metric only exists on one --
    which is itself worth reporting, since it catches a fixture being renamed
    or a metric silently disappearing from the output.
    """
    changes = []
    for name in sorted(set(baseline) | set(current)):
        before_metrics = baseline.get(name)
        after_metrics = current.get(name)
        if before_metrics is None:
            changes.append((name, "<entire fixture>", None, 0.0))
            continue
        if after_metrics is None:
            changes.append((name, "<entire fixture>", 0.0, None))
            continue
        for metric in sorted(set(before_metrics) | set(after_metrics)):
            before = before_metrics.get(metric)
            after = after_metrics.get(metric)
            if before is None or after is None:
                changes.append((name, metric, before, after))
            elif abs(after - before) > TOLERANCE:
                changes.append((name, metric, before, after))
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="accept current values as baseline")
    parser.add_argument("--json", action="store_true", help="print current metrics as JSON")
    args = parser.parse_args()

    current = measure_all_synthetic()

    if args.json:
        print(json.dumps(current, indent=2, sort_keys=True))
        return 0

    if args.update:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(
            json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"baseline updated: {BASELINE_PATH} ({len(current)} fixtures)")
        return 0

    changes = diff(load_baseline(), current)

    real = measure_real_scans()
    if real:
        print(f"\nreal photographs measured (not baselined): {len(real)}")
        for name, metrics in real.items():
            print(
                f"  {name:28} centering {metrics['centering.raw_score']:5.2f}"
                f"  corners {metrics['corners.raw_score']:5.2f}"
                f"  edges {metrics['edges.raw_score']:5.2f}"
                f"  surface {metrics['surface.raw_score']:5.2f}"
                f"  ({metrics['px_per_mm']:.1f} px/mm)"
            )

    if not changes:
        print(f"\nno drift across {len(current)} fixtures.")
        return 0

    print(f"\ndrift in {len({c[0] for c in changes})} of {len(current)} fixtures:\n")
    current_fixture = None
    for name, metric, before, after in changes:
        if name != current_fixture:
            print(f"  {name}")
            current_fixture = name
        if before is None:
            print(f"    + {metric:44} {after}")
        elif after is None:
            print(f"    - {metric:44} (was {before})")
        else:
            print(f"    ~ {metric:44} {before:8.3f} -> {after:8.3f}  ({after - before:+.3f})")
    print("\nIf this was intended, record it: python scripts/fixture_drift.py --update")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
