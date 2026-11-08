"""Train/validation assignment and the on-disk Corpus shape."""

from __future__ import annotations

import random
from collections.abc import Sequence
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

    @property
    def n_games(self) -> int:
        return int(np.unique(self.game_ids).size)


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


def combine_corpora(parts: Sequence[Corpus]) -> Corpus:
    """Stack Corpora and shift game ids so two files cannot share an id.

    Each row keeps the split it was written with, so a held-out game stays
    held out. Ids are shifted because every Corpus numbers its games from the
    same seed.
    """
    if not parts:
        raise ValueError("need at least one Corpus")
    width = int(parts[0].observations.shape[1])
    game_ids: list[NDArray[np.int64]] = []
    plies: list[NDArray[np.int32]] = []
    seats: list[NDArray[np.str_]] = []
    splits: list[NDArray[np.str_]] = []
    won: list[NDArray[np.float64]] = []
    observations: list[NDArray[np.float64]] = []
    shift = 0
    for part in parts:
        if part.observations.shape[1] != width:
            raise ValueError("Corpora have different Observation widths")
        ids = np.asarray(part.game_ids, dtype=np.int64) + shift
        shift = int(ids.max()) + 1
        game_ids.append(ids)
        plies.append(np.asarray(part.plies, dtype=np.int32))
        seats.append(np.asarray(part.seats, dtype=np.str_))
        splits.append(np.asarray(part.splits, dtype=np.str_))
        won.append(np.asarray(part.won, dtype=np.float64))
        observations.append(np.asarray(part.observations, dtype=np.float64))
    return Corpus(
        game_ids=np.concatenate(game_ids),
        plies=np.concatenate(plies),
        seats=np.concatenate(seats),
        splits=np.concatenate(splits),
        won=np.concatenate(won),
        observations=np.vstack(observations),
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
