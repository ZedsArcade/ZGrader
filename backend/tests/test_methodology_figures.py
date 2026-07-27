"""The published /methodology figures must keep demonstrating what the page
says they demonstrate.

These aren't decorative screenshots -- the page points at them and makes
specific claims about the detector's behaviour. If a threshold is tuned and
the figures stop showing what the copy describes, that's a page telling
customers something untrue, which is the exact opposite of why it exists.
So the claims are asserted here rather than trusted to memory.
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from generate_methodology_figures import (  # noqa: E402
    FIGURE_NAMES,
    build_demo_scan,
    generate,
)


@pytest.fixture(scope="module")
def generated(tmp_path_factory) -> tuple[Path, dict]:
    out = tmp_path_factory.mktemp("methodology")
    analysis = generate(out)
    return out, analysis


def test_every_figure_the_page_references_is_written(generated):
    out, _ = generated
    for name in FIGURE_NAMES:
        path = out / name
        assert path.exists(), f"{name} was not generated"
        # A PNG header plus something worth looking at. Catches a figure that
        # silently wrote an empty or single-colour image.
        assert path.stat().st_size > 2000, f"{name} is suspiciously small"


def test_demo_card_is_deterministic():
    """Committed figures must not churn on every regeneration."""
    assert np.array_equal(build_demo_scan(), build_demo_scan())


def test_printed_text_is_detected_and_then_mostly_rejected(generated):
    """The page's central claim, in two halves.

    The raw variance pass sees printed text (that's the honest limitation),
    and the stroke-thickness filter then rejects most of it (that's what
    makes the category usable at all). If either half stops being true the
    surface figures are lying.
    """
    _, analysis = generated
    mask = analysis["anomaly_mask"]

    raw_blob_count, _, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    # Label 0 is the background.
    raw_blobs = raw_blob_count - 1
    kept = len(analysis["surface_regions"])

    assert raw_blobs > 10, "the raw pass should be seeing the body text"
    assert kept >= 1, "the filter should not be rejecting everything"
    assert kept < raw_blobs / 2, (
        f"the filter kept {kept} of {raw_blobs} blobs -- it is no longer "
        "rejecting text, so the surface figures no longer show what the "
        "methodology page claims"
    )


def test_a_crease_is_detected_for_the_crease_figure(generated):
    _, analysis = generated
    assert analysis["creases"], "crease.png would have nothing drawn on it"


def test_every_category_has_something_to_show(generated):
    """Each figure needs a finding in it, or it illustrates nothing.

    The demonstration card carries an off-centre cut, a whitened corner and a
    whitened edge run on purpose; a perfect score anywhere here means that
    feature stopped being detected.
    """
    _, analysis = generated
    assert analysis["centering"]["measurements"]["worse_side_pct"] > 52, "cut looks centred"
    assert analysis["corners"]["raw_score"] < 9.5, "corner whitening not detected"
    assert analysis["edges"]["raw_score"] < 9.5, "edge whitening not detected"
    assert analysis["surface"]["raw_score"] < 9.5, "surface findings not detected"
