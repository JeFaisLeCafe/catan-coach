from __future__ import annotations

import pytest

from catan_coach.domain.dice import EXTREME_TWELVE_TAIL, summarize_rolls, twelve_upper_tail


def test_the_extreme_tail_threshold_is_one_percent() -> None:
    assert EXTREME_TWELVE_TAIL == 0.01


def test_ten_twelves_in_120_rolls_is_an_extreme_tail() -> None:
    tail = twelve_upper_tail(10, 120)

    assert tail == pytest.approx(0.001979190190, abs=1e-12)
    assert tail <= EXTREME_TWELVE_TAIL
    summary = summarize_rolls((12,) * 10 + (6,) * 110)

    assert summary.rolls == 120
    assert summary.twelves == 10
    assert summary.expected_twelves == pytest.approx(120 / 36)
    assert summary.extreme_twelves is True
    assert summary.count(12) == 10
    assert summary.count(6) == 110


def test_the_threshold_flags_nine_twelves_and_not_eight() -> None:
    assert twelve_upper_tail(9, 120) <= EXTREME_TWELVE_TAIL
    assert twelve_upper_tail(8, 120) > EXTREME_TWELVE_TAIL
    assert summarize_rolls((12,) * 9 + (7,) * 111).extreme_twelves is True
    assert summarize_rolls((12,) * 8 + (7,) * 112).extreme_twelves is False


def test_a_typical_twelve_count_is_not_extreme() -> None:
    near_the_mean = summarize_rolls((12,) * 3 + (8,) * 117)
    exactly_the_mean = summarize_rolls((12,) + (5,) * 35)

    assert near_the_mean.expected_twelves == pytest.approx(120 / 36)
    assert near_the_mean.extreme_twelves is False
    assert exactly_the_mean.expected_twelves == pytest.approx(1)
    assert exactly_the_mean.twelves == 1
    assert exactly_the_mean.extreme_twelves is False


def test_counts_cover_every_face_and_an_empty_sequence_is_quiet() -> None:
    summary = summarize_rolls((2, 2, 12))

    assert summary.counts == (2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1)
    assert summary.expected_twelves == pytest.approx(3 / 36)
    assert summary.extreme_twelves is False

    empty = summarize_rolls(())
    assert empty.rolls == 0
    assert empty.expected_twelves == 0
    assert empty.extreme_twelves is False
    assert empty.counts == (0,) * 11


def test_a_roll_outside_two_through_twelve_is_rejected() -> None:
    with pytest.raises(ValueError, match="2 to 12"):
        summarize_rolls((1,))
    with pytest.raises(ValueError, match="2 to 12"):
        summarize_rolls((13,))
    with pytest.raises(ValueError, match="2 to 12"):
        summarize_rolls((True,))
