"""Validation games are read one game at a time."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from catan_coach.domain.corpus import TRAIN, VALIDATION
from catan_coach.engine.mixture import iter_validation_games, player_count


def _write(directory: Path, name: str, game_id: int, split: str) -> None:
    games = directory / "games"
    games.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "game_id": [game_id, game_id],
            "split": [split, split],
            "seat": ["RED", "BLUE"],
            "won": [1.0, 0.0],
            "observation": [[0.0, 1.0], [1.0, 0.0]],
        }
    ).to_parquet(games / name)


def test_validation_games_are_yielded_and_train_games_are_not(tmp_path: Path) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    _write(first, "00000.parquet", 7, TRAIN)
    _write(first, "00001.parquet", 8, VALIDATION)
    _write(second, "00000.parquet", 8, VALIDATION)

    games = list(iter_validation_games([first, second]))

    assert [(game.corpus_index, game.game_id) for game in games] == [(0, 8), (1, 8)]
    assert games[0].features.shape == (2, 2)
    assert player_count([first]) == 2
