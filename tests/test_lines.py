import numpy as np
import pytest
from catanatron.game import Game
from catanatron.models.map import number_probability
from catanatron.models.player import Color, SimplePlayer

from catan_coach.engine.features import public_vp_indices
from catan_coach.engine.lines import position_lines
from catan_coach.engine.position import action_label
from catan_coach.models.baselines import VictoryPointShareModel


class _IncreasingModel:
    name = "increasing"

    def predict(self, features: np.ndarray) -> np.ndarray:
        count = features.shape[0]
        return np.linspace(0.1, 0.9, count)


def _spot_score(game: Game, node_id: int) -> float:
    tiles = [
        tile for tile in game.state.board.map.adjacent_tiles[node_id] if tile.resource is not None
    ]
    pips = float(sum(number_probability(tile.number) for tile in tiles))
    return pips + len({tile.resource for tile in tiles}) * 4 * 2.778 / 100


def _opening() -> Game:
    colors = [Color.RED, Color.BLUE, Color.ORANGE]
    return Game([SimplePlayer(color) for color in colors], seed=1)


@pytest.mark.engine
def test_opening_lines_are_the_five_strongest_placements() -> None:
    game = _opening()
    result = position_lines(game, VictoryPointShareModel(public_vp_indices(3)))

    assert result["ordering"] == "tiles"
    assert result["played"] is None
    lines = result["lines"]
    assert isinstance(lines, list)
    assert len(lines) == 5
    nodes = [int(str(line["action"]).rsplit(" ", 1)[1]) for line in lines]
    every = [action.value for action in game.playable_actions]
    ranked = sorted((_spot_score(game, node) for node in every), reverse=True)
    assert _spot_score(game, nodes[0]) == pytest.approx(ranked[0])
    assert _spot_score(game, nodes[-1]) == pytest.approx(ranked[4])
    assert all("then road toward" in str(line["summary"]) for line in lines)
    assert all(line["loss"] == 0 for line in lines)


@pytest.mark.engine
def test_a_road_that_adds_no_hex_is_listed_last() -> None:
    game = _opening()
    settlement = next(action for action in game.playable_actions if action.value == 8)
    game.execute(settlement)
    result = position_lines(game, VictoryPointShareModel(public_vp_indices(3)))

    lines = result["lines"]
    assert isinstance(lines, list)
    staying = next(line for line in lines if line["action"] == "BUILD_ROAD (8, 27)")
    assert str(staying["summary"]).startswith("staying on ")
    assert lines[-1]["action"] == "BUILD_ROAD (8, 27)"
    assert all(str(line["summary"]).startswith("toward ") for line in lines[:-1])


@pytest.mark.engine
def test_a_model_that_separates_actions_keeps_its_order() -> None:
    game = _opening()
    result = position_lines(game, _IncreasingModel())

    assert result["ordering"] == "win_probability"
    lines = result["lines"]
    assert isinstance(lines, list)
    assert lines[0]["action"] == action_label(game.playable_actions[-1])
    assert lines[0]["win_probability"] > lines[1]["win_probability"]


@pytest.mark.engine
def test_the_played_action_stays_visible_outside_the_first_five() -> None:
    game = _opening()
    weakest = min(
        game.playable_actions,
        key=lambda action: (_spot_score(game, action.value), -action.value),
    )
    result = position_lines(
        game,
        VictoryPointShareModel(public_vp_indices(3)),
        played=action_label(weakest),
    )

    lines = result["lines"]
    assert isinstance(lines, list)
    assert result["played"] == action_label(weakest)
    assert lines[-1]["action"] == action_label(weakest)
    assert len(lines) == 6
