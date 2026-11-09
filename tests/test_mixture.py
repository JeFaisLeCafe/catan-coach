"""Validation games are read one game at a time."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from catan_coach.domain.corpus import TRAIN, VALIDATION
from catan_coach.domain.manifest import MANIFEST_NAME, CorpusManifest
from catan_coach.engine.mixture import iter_validation_games, player_count


def _manifest(directory: Path, *, games: int, dropped: int = 0) -> None:
    finished = games
    total = finished + dropped
    manifest = CorpusManifest(
        player_kind="value",
        model_sha256="",
        search_simulations=0,
        exploration=False,
        ply_stride=12,
        base_seed=0,
        requested_games=max(total, 1),
        validation_fraction=0.2,
        max_turns=1000,
        git_revision="unknown",
        dirty_tree=False,
        games_finished=finished,
        games_dropped=dropped,
        drop_rate=0.0 if total == 0 else dropped / total,
    )
    (directory / MANIFEST_NAME).write_text(manifest.to_json(), encoding="utf-8")


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
    _manifest(first, games=2)
    _manifest(second, games=1)

    games = list(iter_validation_games([first, second]))

    assert [(game.corpus_index, game.game_id) for game in games] == [(0, 8), (1, 8)]
    assert games[0].features.shape == (2, 2)
    assert player_count([first]) == 2


def test_training_refuses_a_missing_manifest(tmp_path: Path) -> None:
    _write(tmp_path, "00000.parquet", 1, VALIDATION)

    with pytest.raises(ValueError, match="manifest is missing"):
        list(iter_validation_games([tmp_path]))


def test_training_refuses_a_drop_rate_above_one_percent(tmp_path: Path) -> None:
    _write(tmp_path, "00000.parquet", 1, VALIDATION)
    _manifest(tmp_path, games=2792, dropped=208)

    with pytest.raises(ValueError, match="above 1%"):
        list(iter_validation_games([tmp_path]))
