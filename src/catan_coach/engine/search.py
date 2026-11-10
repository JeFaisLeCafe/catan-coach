"""Run Progressive Analysis on a Catanatron game without touching it."""

from __future__ import annotations

import random
from collections.abc import Callable, Iterator

from catanatron.game import Game
from catanatron.models.enums import ActionRecord, ActionType
from catanatron.models.player import Color

from catan_coach.domain.prediction import WinProbabilityModel
from catan_coach.domain.search import (
    Budget,
    SearchCache,
    Snapshot,
    progressive_search,
)
from catan_coach.engine.features import feature_vector
from catan_coach.engine.position import _copy_without_sharing_rng, action_label
from catan_coach.engine.scoring import rank_resolved
from catan_coach.engine.trades import listed_actions

_DICE_WAYS = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}


class _EngineState:
    def __init__(self, game: Game, model: WinProbabilityModel) -> None:
        self._game = game
        self._model = model
        self._actions = {action_label(action): action for action in listed_actions(game)}

    def seat(self) -> str:
        return str(self._game.state.current_color().name)

    def actions(self) -> tuple[str, ...]:
        # Engine trade/dev-card choices can come from sets. Seeded sampling
        # needs the same ordering in every interpreter process.
        return tuple(sorted(self._actions))

    def outcomes(self, action: str) -> tuple[tuple[str, float], ...] | None:
        engine_action = self._actions.get(action)
        if engine_action is None or engine_action.action_type != ActionType.ROLL:
            return None
        return tuple((str(total), ways / 36) for total, ways in _DICE_WAYS.items())

    def step(self, action: str, rng: random.Random, outcome: str | None = None) -> _EngineState:
        clone = _copy_without_sharing_rng(self._game)
        rolled = random.Random(rng.randrange(1 << 30))
        clone.random = rolled
        clone.state.random = rolled
        engine_action = self._actions[action]
        record = None
        if outcome is not None:
            total = int(outcome)
            low = min(6, max(1, total - 6))
            record = ActionRecord(engine_action, (low, total - low))
        clone.execute(engine_action, action_record=record)
        return _EngineState(clone, self._model)

    def winner(self) -> str | None:
        color = self._game.winning_color()
        return None if color is None else str(color.name)

    def value(self, seat: str) -> float:
        features = feature_vector(self._game, Color[seat]).reshape(1, -1)
        return float(self._model.predict(features)[0])


def refine_position(
    game: Game,
    model: WinProbabilityModel,
    *,
    budget: Budget,
    clock: Callable[[], float],
    rng: random.Random,
    stop: Callable[[], bool],
    cache: SearchCache | None = None,
    position_id: str = "",
    batch_size: int = 4,
    max_depth: int = 200,
    max_nodes: int = 800_000,
    policy_width: int = 3,
) -> Iterator[Snapshot]:
    """Copy `game`, rank it with the model, then play forward.

    The caller's game and its random stream are not used again after the copy.
    A timed or immediate run stores its last snapshot. A stopped run does not,
    because that snapshot belongs to a Position that was cancelled.
    """
    key = None if cache is None else cache.key(position_id, model.name, budget)
    if key is not None and cache is not None:
        cached = cache.get(key)
        if cached is not None:
            yield cached
            return

    clone = _copy_without_sharing_rng(game)
    analysis = rank_resolved(clone, model)
    prior = tuple((row.action.label, row.win_probability) for row in analysis.ranked)
    last: Snapshot | None = None
    for snapshot in progressive_search(
        _EngineState(clone, model),
        root_seat=analysis.seat.name,
        prior=prior,
        budget=budget,
        clock=clock,
        rng=rng,
        stop=stop,
        batch_size=batch_size,
        max_depth=max_depth,
        max_nodes=max_nodes,
        policy_width=policy_width,
    ):
        last = snapshot
        yield snapshot
    if (
        key is not None
        and cache is not None
        and last is not None
        and not stop()
        and budget.mode != "continuous"
    ):
        cache.put(key, last)
