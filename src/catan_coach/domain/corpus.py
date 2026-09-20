"""Train/validation assignment and the on-disk Corpus shape."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

Split = Literal["train", "validation"]

TRAIN: Split = "train"
VALIDATION: Split = "validation"

DEFAULT_VALIDATION_FRACTION = 0.2


@dataclass(frozen=True, slots=True)
class Corpus:
    """Rows from self-play: one Observation per Seat per sampled Position."""

    game_ids: NDArray[np.int64]
    plies: NDArray[np.int32]
    seats: NDArray[np.str_]
    splits: NDArray[np.str_]
    won: NDArray[np.float64]
    observations: NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class CorpusSummary:
    games_played: int
    games_dropped: int
    rows_written: int
    win_rate_by_seat: dict[str, float]


def format_summary(summary: CorpusSummary) -> str:
    rates = "  ".join(
        f"{seat} {rate:.2f}" for seat, rate in sorted(summary.win_rate_by_seat.items())
    )
    return "\n".join(
        [
            f"Games played: {summary.games_played}",
            f"Games dropped: {summary.games_dropped}",
            f"Rows written: {summary.rows_written}",
            f"Win rate: {rates}",
        ]
    )


def split_for_game(
    game_id: int,
    *,
    seed: int,
    validation_fraction: float = DEFAULT_VALIDATION_FRACTION,
) -> Split:
    """Assign a whole game to train or validation. Independent of other games."""
    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("validation_fraction must be between 0 and 1, exclusive")
    rng = random.Random(f"{seed}:{game_id}")
    if rng.random() < validation_fraction:
        return VALIDATION
    return TRAIN
