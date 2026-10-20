"""Search reads a real game and leaves it unchanged."""

from __future__ import annotations

import json
import random
import time

import pytest

pytestmark = pytest.mark.engine

catanatron = pytest.importorskip("catanatron")

from catanatron.game import Game  # noqa: E402
from catanatron.models.player import Color, SimplePlayer  # noqa: E402
from catanatron.serialization import state_to_json  # noqa: E402

from catan_coach.domain.search import Budget, SearchCache  # noqa: E402
from catan_coach.engine.features import public_vp_indices  # noqa: E402
from catan_coach.engine.search import refine_position  # noqa: E402
from catan_coach.models.baselines import VictoryPointShareModel  # noqa: E402


def _game() -> Game:
    colors = [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
    return Game([SimplePlayer(color) for color in colors], seed=3)


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


def test_extra_time_looks_further_than_four_plies() -> None:
    snapshots = list(
        refine_position(
            _game(),
            VictoryPointShareModel(public_vp_indices(4)),
            budget=Budget("timed", 2.0),
            clock=time.perf_counter,
            rng=random.Random(1),
            stop=lambda: False,
            batch_size=4,
            max_depth=24,
            policy_width=3,
        )
    )

    last = snapshots[-1]
    assert last.horizon >= 10
    assert last.horizon > snapshots[0].horizon
    assert last.simulations > 1
