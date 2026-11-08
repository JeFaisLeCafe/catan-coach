"""Corpus boards shuffle numbers and keep a 6 off an 8."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.engine

catanatron = pytest.importorskip("catanatron")

import pandas as pd  # noqa: E402
from catanatron.game import Game  # noqa: E402
from catanatron.models.player import Color  # noqa: E402
from catanatron.players.value import ValueFunctionPlayer  # noqa: E402

from catan_coach.engine.board import corpus_map  # noqa: E402
from catan_coach.engine.corpus import generate_corpus  # noqa: E402
from catan_coach.engine.position import action_label  # noqa: E402


def _six_touches_eight(board: object) -> bool:
    reds = [tile for tile in board.land_tiles.values() if tile.number in (6, 8)]  # type: ignore[attr-defined]
    for index, left in enumerate(reds):
        left_nodes = set(left.nodes.values())
        for right in reds[index + 1 :]:
            if {left.number, right.number} != {6, 8}:
                continue
            if len(left_nodes & set(right.nodes.values())) >= 2:
                return True
    return False


def test_shuffled_numbers_keep_reds_apart() -> None:
    layouts = []
    for seed in range(12):
        board = corpus_map(seed)
        layouts.append(tuple(tile.number for tile in board.land_tiles.values()))
        assert not _six_touches_eight(board)
    assert len(set(layouts)) > 1


def test_the_same_seed_replays_and_is_recorded(tmp_path: Path) -> None:
    colors = (Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE)

    def labels(seed: int) -> list[str]:
        game = Game(
            [ValueFunctionPlayer(color) for color in colors],
            seed=seed,
            catan_map=corpus_map(seed),
        )
        played: list[str] = []
        for _ in range(12):
            game.play_tick()
            played.append(action_label(game.state.action_records[-1].action))
        return played

    assert labels(4) == labels(4)

    generate_corpus(tmp_path, n_games=1, ply_stride=10_000, seed=4, workers=1)
    frame = pd.read_parquet(next((tmp_path / "games").glob("*.parquet")))
    assert set(frame["seed"].tolist()) == {4}
