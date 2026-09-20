"""Save a game and reload a Position at a chosen Ply."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from catan_coach.domain.analysis import analyze
from catan_coach.domain.position import Action, Seat
from catan_coach.engine.features import feature_vector
from catan_coach.engine.persist import position_at_ply, read_game, write_game
from catan_coach.engine.position import EnginePosition
from catan_coach.models.baselines import ConstantModel

pytestmark = pytest.mark.engine

catanatron = pytest.importorskip("catanatron")

from catanatron import Color, Game  # noqa: E402
from catanatron.players.value import ValueFunctionPlayer  # noqa: E402

COLORS = (Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE)
PERSPECTIVE = Color.RED
MIDGAME_PLY = 50


@dataclass(frozen=True, slots=True)
class RecordedPlay:
    game: Game
    seats: tuple[Seat, ...]
    legal_actions: tuple[tuple[Action, ...], ...]
    observations: tuple[np.ndarray, ...]


@pytest.fixture(scope="module")
def recorded() -> RecordedPlay:
    game = Game([ValueFunctionPlayer(c) for c in COLORS], seed=7)
    seats: list[Seat] = []
    legal_actions: list[tuple[Action, ...]] = []
    observations: list[np.ndarray] = []
    while game.winning_color() is None:
        position = EnginePosition(game)
        seats.append(position.seat_to_act)
        legal_actions.append(position.legal_actions())
        observations.append(position.observation())
        game.play_tick()
    return RecordedPlay(game, tuple(seats), tuple(legal_actions), tuple(observations))


def _load_at(recorded: RecordedPlay, tmp_path: Path, ply: int) -> EnginePosition:
    path = tmp_path / "game.json"
    write_game(recorded.game, path)
    return position_at_ply(read_game(path), ply)


class TestGameRoundTrip:
    def test_a_finished_game_round_trips_through_a_file(
        self, recorded: RecordedPlay, tmp_path: Path
    ) -> None:
        path = tmp_path / "game.json"
        write_game(recorded.game, path)
        restored = read_game(path)

        assert np.array_equal(
            feature_vector(restored, PERSPECTIVE),
            feature_vector(recorded.game, PERSPECTIVE),
        )
        assert restored.winning_color() == recorded.game.winning_color()


class TestPositionAtPly:
    def test_ply_zero_is_the_opening_position(self, recorded: RecordedPlay, tmp_path: Path) -> None:
        loaded = _load_at(recorded, tmp_path, 0)

        assert loaded.seat_to_act == recorded.seats[0]
        assert loaded.legal_actions() == recorded.legal_actions[0]
        assert np.array_equal(loaded.observation(), recorded.observations[0])

    def test_a_midgame_ply_matches_the_live_position(
        self, recorded: RecordedPlay, tmp_path: Path
    ) -> None:
        loaded = _load_at(recorded, tmp_path, MIDGAME_PLY)

        assert loaded.seat_to_act == recorded.seats[MIDGAME_PLY]
        assert loaded.legal_actions() == recorded.legal_actions[MIDGAME_PLY]
        assert np.array_equal(loaded.observation(), recorded.observations[MIDGAME_PLY])

    def test_the_final_ply_is_just_before_the_game_ended(
        self, recorded: RecordedPlay, tmp_path: Path
    ) -> None:
        last = len(recorded.seats) - 1
        loaded = _load_at(recorded, tmp_path, last)

        assert loaded.seat_to_act == recorded.seats[last]
        assert loaded.legal_actions() == recorded.legal_actions[last]
        assert np.array_equal(loaded.observation(), recorded.observations[last])

    def test_a_ply_beyond_the_end_names_the_valid_range(
        self, recorded: RecordedPlay, tmp_path: Path
    ) -> None:
        last = len(recorded.seats) - 1
        path = tmp_path / "game.json"
        write_game(recorded.game, path)
        restored = read_game(path)

        with pytest.raises(ValueError, match=rf"valid plies are 0 to {last}"):
            position_at_ply(restored, last + 1)

    def test_a_loaded_position_is_ready_to_analyze(
        self, recorded: RecordedPlay, tmp_path: Path
    ) -> None:
        loaded = _load_at(recorded, tmp_path, MIDGAME_PLY)
        analysis = analyze(loaded, ConstantModel(len(COLORS)))

        assert analysis.seat == loaded.seat_to_act
        assert {row.action for row in analysis.ranked} == set(loaded.legal_actions())

    def test_the_same_ply_replays_identically(self, recorded: RecordedPlay, tmp_path: Path) -> None:
        ply = next(
            i
            for i, actions in enumerate(recorded.legal_actions)
            if i > 0 and any(action.label == "ROLL" for action in actions)
        )
        first = _load_at(recorded, tmp_path, ply)
        second = _load_at(recorded, tmp_path, ply)
        roll = next(action for action in first.legal_actions() if action.label == "ROLL")

        assert np.array_equal(first.observation(), second.observation())
        assert np.array_equal(first.observation_after(roll), second.observation_after(roll))
