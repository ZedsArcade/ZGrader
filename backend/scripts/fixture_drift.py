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
import zlib
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from tests.fixtures.generate_samples import (  # noqa: E402
    build_fixture,
    card_size_mm,
    fixture_names,
)
from zgrader.analysis import preprocessing  # noqa: E402
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

#: A "<name>_traced.png" is a copy of its photo with a crop drawn on it by hand
#: -- an input to `traced_crop`, not another photograph to measure.
_TRACED_SUFFIX = "_traced"


def measure_all_synthetic() -> dict[str, dict[str, float]]:
    results = {}
    for name in fixture_names():
        width_mm, height_mm = card_size_mm(name)
        results[name] = measure_image(build_fixture(name), width_mm, height_mm)
    return results


def crop_like_a_customer(image: np.ndarray) -> np.ndarray:
    """The four points a customer's crop would carry: the card's own corners
    from an uncropped run -- fitted apexes when the fit held, the coarse quad
    when it fell back. rectify records either as `apexes`."""
    rectified = preprocessing.rectify(image, *_DEFAULT_CARD_MM)
    return np.array(rectified.geometry["apexes"], dtype=np.float64)


def suggested_crop(image: np.ndarray) -> np.ndarray:
    """The box a crop producer actually sends -- `suggest_crop`,
    `snap_points_to_boundary` and the watcher's registration all call
    `detect_boundary` directly on the raw upload, not `rectify`'s fitted
    apexes. `crop_like_a_customer` above is the *fit's* own corners, which
    can never contain the disagreement those three call sites used to ship:
    called without the card's `expected_aspect`, `detect_boundary` can lock
    onto a different contour than the one `rectify` finds inside the region
    of interest with it -- the desk rather than the card, on two real
    photographs, 13-35mm outside the fit. This is the crop that ships."""
    expected_aspect = min(_DEFAULT_CARD_MM) / max(_DEFAULT_CARD_MM)
    box, _info = preprocessing.detect_boundary(image, expected_aspect=expected_aspect)
    return np.array(box, dtype=np.float64)


def traced_crop(path: Path) -> np.ndarray | None:
    """The crop a person traced around this card, from `<stem>.crop.json`.

    The harness's own `crop_like_a_customer` is the *fit's* own apexes, so it
    can never contain a crop that corrects the fit -- which is the only case
    the crop-guided refit exists for. A traced crop is the missing input, and
    it stays out of git with the photographs it belongs to.
    """
    sidecar = path.with_suffix(".crop.json")
    if not sidecar.is_file():
        return None
    points = json.loads(sidecar.read_text(encoding="utf-8"))["points"]
    return np.array(points, dtype=np.float64).reshape(4, 2)


def sloppy_crop(quad: np.ndarray, px_per_mm: float, seed: int) -> np.ndarray:
    """`quad` with each side pushed in or out by 1-2mm, deterministically.

    A crop traced by finger on a phone is never on the edge to the millimetre,
    and the refit must not pull a good fit off its edge when the crop is merely
    imprecise. Each *side* is moved along its own outward normal and the
    corners are re-intersected, so every side really does move by its drawn
    amount -- moving the corners instead attenuates the displacement by the
    diagonal's cosine and lets two draws cancel on the side they share.
    """
    ordered = np.asarray(quad, dtype=np.float64).reshape(4, 2)
    rng = np.random.default_rng(seed)
    centre = ordered.mean(axis=0)
    # Ordered corners are top-left, top-right, bottom-right, bottom-left.
    side_corners = {"top": (0, 1), "right": (1, 2), "bottom": (3, 2), "left": (0, 3)}

    lines = {}
    for name, (i, j) in side_corners.items():
        direction = ordered[j] - ordered[i]
        length = float(np.hypot(*direction))
        if length < 1e-6:
            return ordered
        normal = np.array([-direction[1], direction[0]]) / length
        offset = float(normal @ ordered[i])
        if (centre @ normal - offset) > 0:  # point the normal outward
            normal, offset = -normal, -offset
        shift = float(rng.uniform(1.0, 2.0) * px_per_mm * rng.choice([-1.0, 1.0]))
        lines[name] = (normal, offset + shift)

    def _corner(a: str, b: str) -> np.ndarray:
        (na, oa), (nb, ob) = lines[a], lines[b]
        matrix = np.stack([na, nb])
        if abs(float(np.linalg.det(matrix))) < 1e-9:
            return ordered[0]
        return np.linalg.solve(matrix, np.array([oa, ob]))

    return np.array(
        [_corner("top", "left"), _corner("top", "right"),
         _corner("bottom", "right"), _corner("bottom", "left")],
        dtype=np.float64,
    )


def measure_real_scans(sloppy: bool = False) -> dict[str, dict[str, dict[str, float]]]:
    """Measure any real photographs that have been dropped in: without a crop,
    with the harness's own crop, with a hand-traced crop where one exists, and
    -- under --sloppy -- with that crop deliberately misplaced by 1-2mm.

    Returns empty when the directory is absent or empty, which is the normal
    state for a fresh clone -- this must never be the reason the harness fails.
    """
    if not REAL_SCANS_DIR.is_dir():
        return {}
    results = {}
    for path in sorted(REAL_SCANS_DIR.iterdir()):
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
            continue
        if path.stem.endswith(_TRACED_SUFFIX):
            print(f"  - skipped {path.name} (traced overlay)", file=sys.stderr)
            continue
        image = cv2.imread(str(path))
        if image is None:
            print(f"  ! could not read {path.name}", file=sys.stderr)
            continue
        try:
            crop = crop_like_a_customer(image)
            measurements = {
                "uncropped": measure_image(image, *_DEFAULT_CARD_MM),
                "cropped": measure_image(image, *_DEFAULT_CARD_MM, roi_quad=crop),
                "suggested": measure_image(
                    image, *_DEFAULT_CARD_MM, roi_quad=suggested_crop(image)
                ),
            }
            try:
                traced = traced_crop(path)
            except Exception as exc:  # noqa: BLE001 -- a malformed sidecar must not drop this photo
                print(f"  ! {path.name}: bad crop.json: {type(exc).__name__}: {exc}", file=sys.stderr)
                traced = None
            if traced is not None:
                measurements["traced"] = measure_image(
                    image, *_DEFAULT_CARD_MM, roi_quad=traced
                )
            if sloppy:
                px_per_mm = measurements["cropped"].get("px_per_mm") or 1.0
                measurements["sloppy"] = measure_image(
                    image,
                    *_DEFAULT_CARD_MM,
                    roi_quad=sloppy_crop(crop, px_per_mm, seed=zlib.crc32(path.stem.encode())),
                )
            results[path.stem] = measurements
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
    parser.add_argument(
        "--sloppy",
        action="store_true",
        help="also measure each real photo with its crop misplaced by 1-2mm per side",
    )
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

    real = measure_real_scans(sloppy=args.sloppy)
    if real:
        print(f"\nreal photographs measured (not baselined): {len(real)}")
        for name, paths in real.items():
            for label, metrics in paths.items():
                # "--" where a category declined to score. The first real card that
                # produced an unmeasurable centering crashed this line with a
                # KeyError, because it assumed every category always yields a
                # number -- which is exactly the assumption the nullable score was
                # introduced to remove, still living in the reporting.
                def _score(key: str) -> str:
                    value = metrics.get(key)
                    return f"{value:5.2f}" if value is not None else "   --"

                tag = name if label == "uncropped" else f"  ({label})"
                print(
                    f"  {tag:28} cen {_score('centering.raw_score')}"
                    f"  cor {_score('corners.raw_score')}"
                    f"  edg {_score('edges.raw_score')}"
                    f"  sur {_score('surface.raw_score')}"
                    f"  ({metrics['px_per_mm']:.1f} px/mm)"
                )
        for label in ("uncropped", "cropped", "suggested"):
            scored = sum("corners.raw_score" in paths[label] for paths in real.values())
            print(f"  corners scored, {label}: {scored}/{len(real)}")
        for label in ("traced", "sloppy"):
            present = [p for p in real.values() if label in p]
            if not present:
                continue
            # px/mm is the raster's own scale, so a shift in it means the fitted
            # card changed size -- a cheap summary of "did this crop move the
            # geometry". The millimetre displacement of each apex is measured
            # directly in the plan's final task; these metrics do not carry it.
            shift = [
                abs(p[label].get("px_per_mm", 0.0) - p["cropped"].get("px_per_mm", 0.0))
                for p in present
            ]
            print(f"  {label}: {len(present)} photo(s), max px/mm shift {max(shift):.2f}")

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
