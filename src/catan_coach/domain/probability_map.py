"""A monotone map from a raw Win Probability to one that matches outcomes.

Fit on one set of games and judged on another. Pool-adjacent-violators keeps
the map from decreasing: a higher raw probability never becomes a lower one.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from catan_coach.domain.calibration import _as_arrays

Probabilities = NDArray[np.float64]
Half = Literal["fit", "report"]


@dataclass(frozen=True, slots=True)
class ProbabilityMap:
    """Knots of (raw probability, calibrated probability), increasing in both."""

    knots: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        if len(self.knots) < 2:
            raise ValueError("a probability map needs at least two knots")
        previous_x = -1.0
        previous_y = -1.0
        for raw, calibrated in self.knots:
            if raw < previous_x or calibrated < previous_y - 1e-12:
                raise ValueError("probability map knots must be increasing")
            previous_x = raw
            previous_y = calibrated

    def apply(self, predicted: ArrayLike) -> Probabilities:
        raw = np.asarray(predicted, dtype=np.float64)
        xs = np.array([knot[0] for knot in self.knots], dtype=np.float64)
        ys = np.array([knot[1] for knot in self.knots], dtype=np.float64)
        return np.clip(np.interp(raw, xs, ys), 0.0, 1.0)

    def to_json_knots(self) -> list[list[float]]:
        return [[raw, calibrated] for raw, calibrated in self.knots]

    @classmethod
    def from_json_knots(cls, knots: list[list[float]]) -> ProbabilityMap:
        return cls(tuple((float(raw), float(calibrated)) for raw, calibrated in knots))


def fit_probability_map(predicted: ArrayLike, outcomes: ArrayLike) -> ProbabilityMap:
    raw, won = _as_arrays(predicted, outcomes)
    order = np.argsort(raw, kind="mergesort")
    raw = raw[order]
    won = won[order]
    unique, starts, counts = np.unique(raw, return_index=True, return_counts=True)
    outcome_sums = np.add.reduceat(won, starts)
    fitted = _pool_adjacent_violators(outcome_sums, counts)
    return ProbabilityMap(_knots(unique, fitted))


def calibration_half(game_id: int, *, seed: int, source: int = 0) -> Half:
    """Assign a whole game to the map fit or to the untouched report.

    `source` keeps the same game id in two Corpora from landing in one half
    together. Every row of one game shares the assignment.
    """
    rng = random.Random(f"{seed}:{source}:{game_id}:calibrate")
    if rng.random() < 0.5:
        return "fit"
    return "report"


def _pool_adjacent_violators(
    outcome_sums: NDArray[np.float64], counts: NDArray[np.intp]
) -> NDArray[np.float64]:
    blocks: list[list[float]] = []
    widths: list[int] = []
    for outcome_sum, count in zip(outcome_sums, counts, strict=True):
        blocks.append([float(outcome_sum), float(count)])
        widths.append(1)
        while len(blocks) >= 2 and _mean(blocks[-2]) > _mean(blocks[-1]):
            weight_sum, count = blocks.pop()
            blocks[-1][0] += weight_sum
            blocks[-1][1] += count
            merged_width = widths.pop()
            widths[-1] += merged_width
    fitted: list[float] = []
    for (weight_sum, count), width in zip(blocks, widths, strict=True):
        fitted.extend([weight_sum / count] * width)
    return np.asarray(fitted, dtype=np.float64)


def _mean(block: list[float]) -> float:
    return block[0] / block[1]


def _knots(
    raw: NDArray[np.float64], fitted: NDArray[np.float64]
) -> tuple[tuple[float, float], ...]:
    knots: list[tuple[float, float]] = []
    start = 0
    for index in range(1, len(fitted) + 1):
        if index < len(fitted) and abs(fitted[index] - fitted[start]) <= 1e-12:
            continue
        knots.append((float(raw[index - 1]), float(fitted[start])))
        start = index
    deduped: list[tuple[float, float]] = []
    for raw_value, calibrated in knots:
        if deduped and abs(deduped[-1][0] - raw_value) <= 1e-15:
            deduped[-1] = (raw_value, calibrated)
            continue
        deduped.append((raw_value, calibrated))
    if len(deduped) == 1:
        calibrated = deduped[0][1]
        return ((0.0, calibrated), (1.0, calibrated))
    if deduped[0][0] > 0.0:
        deduped.insert(0, (0.0, deduped[0][1]))
    if deduped[-1][0] < 1.0:
        deduped.append((1.0, deduped[-1][1]))
    return tuple(deduped)
