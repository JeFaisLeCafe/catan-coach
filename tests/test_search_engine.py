"""Search reads a real game and leaves it unchanged."""

from __future__ import annotations

import json
import random

import pytest

pytestmark = pytest.mark.engine

catanatron = pytest.importorskip("catanatron")

from catanatron.game import Game  # noqa: E402
from catanatron.models.enums import ActionType  # noqa: E402
from catanatron.models.player import Color, SimplePlayer  # noqa: E402
from catanatron.serialization import state_to_json  # noqa: E402

from catan_coach.domain.search import Budget, SearchCache  # noqa: E402
from catan_coach.engine.features import public_vp_indices  # noqa: E402
from catan_coach.engine.search import refine_position  # noqa: E402
from catan_coach.engine.search_session import _SEARCH_SECONDS, _running_budget  # noqa: E402
from catan_coach.models.baselines import VictoryPointShareModel  # noqa: E402


def _game() -> Game:
    colors = [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
    return Game([SimplePlayer(color) for color in colors], seed=3)


def test_a_page_search_is_cut_off_at_ten_minutes() -> None:
    assert _SEARCH_SECONDS == 10 * 60
    assert _running_budget(Budget("continuous")) == Budget("timed", 600)
    assert _running_budget(Budget("timed", 30)) == Budget("timed", 30)


def test_search_does_not_change_the_game_or_its_random_stream() -> None:
    game = _game()
    before = json.dumps(state_to_json(game))
    random_state = game.state.random.getstate()
    model = VictoryPointShareModel(public_vp_indices(4))
    seen = {"n": 0}

    def stop() -> bool:
        return seen["n"] >= 2

    snapshots = []
    for snapshot in refine_position(
        game,
        model,
        budget=Budget("continuous"),
        clock=lambda: 0.0,
        rng=random.Random(1),
        stop=stop,
        batch_size=1,
        max_depth=1,
    ):
        seen["n"] += 1
        snapshots.append(snapshot)

    assert snapshots[0].source == "immediate"
    assert snapshots[-1].simulations >= 1
    assert json.dumps(state_to_json(game)) == before
    assert game.state.random.getstate() == random_state


def test_a_real_position_records_work_per_second() -> None:
    calls = {"n": 0.0}

    def clock() -> float:
        calls["n"] += 0.01
        return calls["n"]

    snapshots = list(
        refine_position(
            _game(),
            VictoryPointShareModel(public_vp_indices(4)),
            budget=Budget("timed", 0.05),
            clock=clock,
            rng=random.Random(1),
            stop=lambda: False,
            batch_size=1,
            max_depth=1,
        )
    )
    last = snapshots[-1]
    assert last.simulations > 0
    assert last.elapsed > 0
    assert last.nodes >= last.simulations
    work_per_second = last.simulations / last.elapsed
    assert work_per_second > 0


def test_the_same_position_reuses_a_finished_search() -> None:
    model = VictoryPointShareModel(public_vp_indices(4))
    cache = SearchCache()
    budget = Budget("immediate")
    first = list(
        refine_position(
            _game(),
            model,
            budget=budget,
            clock=lambda: 0.0,
            rng=random.Random(1),
            stop=lambda: False,
            cache=cache,
            position_id="game-1:0",
        )
    )
    second = list(
        refine_position(
            _game(),
            model,
            budget=budget,
            clock=lambda: 0.0,
            rng=random.Random(1),
            stop=lambda: False,
            cache=cache,
            position_id="game-1:0",
        )
    )

    assert second == [first[-1]]


def _until_roll() -> Game:
    game = _game()
    seats = {color: SimplePlayer(color) for color in game.state.colors}
    for _ in range(80):
        if any(action.action_type == ActionType.ROLL for action in game.playable_actions):
            return game
        color = game.state.current_color()
        game.execute(seats[color].decide(game, game.playable_actions))
    raise AssertionError("never rolled")


def test_repeated_rolls_cover_each_dice_total_before_repeating_one() -> None:
    game = _until_roll()
    assert [action.action_type for action in game.playable_actions] == [ActionType.ROLL]
    model = VictoryPointShareModel(public_vp_indices(4))

    def search(seed: int, snapshots: int) -> tuple[float, int, int]:
        seen = {"n": 0}
        last = None
        for snapshot in refine_position(
            game,
            model,
            budget=Budget("continuous"),
            clock=lambda: 0.0,
            rng=random.Random(seed),
            stop=lambda: seen["n"] >= snapshots,
            batch_size=1,
            max_depth=1,
            policy_width=1,
        ):
            seen["n"] += 1
            last = snapshot
        assert last is not None
        return last.lines[0].win_probability, last.nodes, last.simulations

    first_probability, first_nodes, _first_sims = search(1, 2)
    second_probability, _second_nodes, _second_sims = search(2, 2)
    _covered_probability, covered_nodes, covered_sims = search(1, 12)
    _later_probability, later_nodes, later_sims = search(1, 40)

    assert first_nodes == 1
    assert first_probability == pytest.approx(second_probability)
    assert covered_nodes == 11
    assert covered_sims == 11
    assert later_nodes == 11
    assert later_sims == 11
