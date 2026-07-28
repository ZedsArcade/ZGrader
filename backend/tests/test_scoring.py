"""Front/back combination -- the one place the two sides become the single
number a customer sees."""

import pytest

from zgrader.analysis import scoring


def test_front_dominates_the_combined_score():
    """An unweighted mean let a pristine back hide a damaged front by exactly
    half. Front carries most of the weight instead."""
    assert scoring.combine_front_back(4.0, 10.0) == 5.8  # not 7.0
    assert scoring.combine_front_back(10.0, 4.0) == 8.2  # not 7.0


def test_a_damaged_front_cannot_be_averaged_away_by_a_clean_back():
    damaged_front = scoring.combine_front_back(2.0, 10.0)
    clean_front = scoring.combine_front_back(10.0, 2.0)
    assert damaged_front < clean_front
    assert damaged_front < 6.0, "a wrecked front must not land mid-scale"


def test_identical_sides_are_unchanged_by_weighting():
    for value in (0.0, 5.5, 10.0):
        assert scoring.combine_front_back(value, value) == value


def test_a_missing_back_leaves_the_front_score_alone():
    """A front-only 'partial check' is scored on what it has, not penalised
    for the absent side."""
    assert scoring.combine_front_back(8.4, None) == 8.4


def test_weights_sum_to_one():
    assert scoring.FRONT_WEIGHT + scoring.BACK_WEIGHT == pytest.approx(1.0)


def test_combine_sides_by_name_matches_the_positional_form():
    assert scoring.combine_sides_by_name({"front": 4.0, "back": 10.0}) == (
        scoring.combine_front_back(4.0, 10.0)
    )
    assert scoring.combine_sides_by_name({"front": 8.4}) == 8.4
    assert scoring.combine_sides_by_name({}) is None


def test_a_lone_back_is_not_weighted_down_to_a_third():
    """Back-only shouldn't occur (analysis requires a front scan), but if it
    ever did, returning 0.3x the value would be nonsense."""
    assert scoring.combine_sides_by_name({"back": 9.0}) == 9.0
