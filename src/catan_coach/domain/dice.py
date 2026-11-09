"""Count two-d6 sums and flag an extreme number of twelves.

Flagged games stay in the win rate. The flag is a description of the dice,
not a reason to delete a game after seeing who won.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

# One-sided binomial tail under a fair two-d6. Fixed before any audit game
# is read. Flag when P(X >= observed twelves) <= this value.
EXTREME_TWELVE_TAIL = 0.01

_TWELVE_PROBABILITY = 1 / 36
_FACE_COUNT = 11


@dataclass(frozen=True, slots=True)
class DiceSummary:
    """``counts[face - 2]`` is how many rolls showed that face, for faces 2..12."""

    counts: tuple[int, ...]
    rolls: int
    twelves: int
    expected_twelves: float
    extreme_twelves: bool

    def __post_init__(self) -> None:
        if len(self.counts) != _FACE_COUNT:
            raise ValueError("counts cover the eleven faces from 2 through 12")

    def count(self, face: int) -> int:
        if face < 2 or face > 12:
            raise ValueError("a production roll is an integer from 2 to 12")
        return self.counts[face - 2]


def summarize_rolls(rolls: Sequence[int]) -> DiceSummary:
    """Count rolls and compare the number of twelves with a fair die.

    Expected twelves are ``n / 36``. ``extreme_twelves`` is true when the
    one-sided upper tail ``P(X >= observed)`` for ``X ~ Binomial(n, 1/36)``
    is at most ``EXTREME_TWELVE_TAIL`` (0.01). Ten twelves in 120 rolls have
    a tail near 0.002 and flag. A count near ``n / 36`` does not. An empty
    sequence is not extreme.
    """
    counts = [0] * _FACE_COUNT
    for roll in rolls:
        _check_roll(roll)
        counts[roll - 2] += 1
    observed = counts[10]
    return DiceSummary(
        counts=tuple(counts),
        rolls=len(rolls),
        twelves=observed,
        expected_twelves=len(rolls) / 36,
        extreme_twelves=_is_extreme(observed, len(rolls)),
    )


def twelve_upper_tail(twelves: int, rolls: int) -> float:
    """``P(X >= twelves)`` for ``X ~ Binomial(rolls, 1/36)``."""
    if isinstance(twelves, bool) or isinstance(rolls, bool):
        raise ValueError("twelves and rolls must be integers")
    if not isinstance(twelves, int) or not isinstance(rolls, int):
        raise ValueError("twelves and rolls must be integers")
    if rolls < 0 or twelves < 0:
        raise ValueError("twelves and rolls must be non-negative")
    if twelves > rolls:
        return 0.0
    if twelves == 0:
        return 1.0
    log_p = math.log(_TWELVE_PROBABILITY)
    log_q = math.log(1.0 - _TWELVE_PROBABILITY)
    logs = [
        math.lgamma(rolls + 1)
        - math.lgamma(successes + 1)
        - math.lgamma(rolls - successes + 1)
        + successes * log_p
        + (rolls - successes) * log_q
        for successes in range(twelves, rolls + 1)
    ]
    peak = max(logs)
    return math.exp(peak) * sum(math.exp(term - peak) for term in logs)


def _is_extreme(twelves: int, rolls: int) -> bool:
    if rolls == 0 or twelves == 0:
        return False
    return twelve_upper_tail(twelves, rolls) <= EXTREME_TWELVE_TAIL


def _check_roll(roll: object) -> None:
    if isinstance(roll, bool) or not isinstance(roll, int) or roll < 2 or roll > 12:
        raise ValueError(f"a production roll must be an integer from 2 to 12, got {roll!r}")
