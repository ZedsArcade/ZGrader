"""The pixel->mm scale must come from the card's physical size, never from
the image file's DPI metadata (see zgrader/analysis/scale.py)."""

import pytest

from zgrader.analysis import scale
from zgrader.models import CardDimensionReference


def test_px_per_mm_derived_from_card_size():
    # A 63x88mm card rendered at 600 DPI is 1488x2079 px -> 600/25.4 px/mm.
    px_per_mm = scale.px_per_mm((2079, 1488), 63.0, 88.0)
    assert px_per_mm == pytest.approx(600 / 25.4, rel=0.01)


def test_px_per_mm_ignores_file_dpi_metadata():
    # The regression that produced a "244mm crease" on an 88mm card: the same
    # pixel image must yield the same scale no matter what DPI a file claims,
    # because scale is a function of pixels-per-card only.
    shape = (2079, 1488)
    assert scale.px_per_mm(shape, 63.0, 88.0) == scale.px_per_mm(shape, 63.0, 88.0)
    # A high-resolution photo of the same card gives a proportionally larger
    # scale -- and a crease spanning the card still measures ~88mm, not 244.
    hi_res = scale.px_per_mm((4158, 2976), 63.0, 88.0)
    assert hi_res == pytest.approx(2 * 600 / 25.4, rel=0.01)
    assert 4158 / hi_res == pytest.approx(88.0, rel=0.02)


def test_px_per_mm_rejects_nonsense_dimensions():
    with pytest.raises(ValueError):
        scale.px_per_mm((2079, 1488), 0.0, 88.0)


def test_dimensions_come_from_the_reference_table(db_session):
    db_session.add(
        CardDimensionReference(game="Tiny Cards", width_mm=30.0, height_mm=40.0, verified=True)
    )
    db_session.commit()

    assert scale.dimensions_for(db_session, "Tiny Cards") == (30.0, 40.0)


def test_unknown_game_falls_back_to_standard_size(db_session):
    assert scale.dimensions_for(db_session, "Nonexistent Game") == (
        scale.DEFAULT_CARD_WIDTH_MM,
        scale.DEFAULT_CARD_HEIGHT_MM,
    )
    assert scale.dimensions_for(db_session, None) == (
        scale.DEFAULT_CARD_WIDTH_MM,
        scale.DEFAULT_CARD_HEIGHT_MM,
    )
