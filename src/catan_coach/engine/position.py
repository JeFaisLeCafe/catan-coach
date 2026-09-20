"""Catanatron adapter for the Position port."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from catanatron import Game
from catanatron.models.enums import Action as EngineAction

from catan_coach.domain.position import Action, Observation, Seat
from catan_coach.engine.features import feature_vector


def action_label(action: EngineAction) -> str:
    name = str(action.action_type.name)
    if action.value is None:
        return name
    return f"{name} {action.value}"


def _copy_without_sharing_rng(game: Game) -> Game:
    clone = game.copy()
    rng = deepcopy(game.state.random)
    clone.random = rng
    clone.state.random = rng
    return clone


class EnginePosition:
    def __init__(self, game: Game) -> None:
        self._game = game
        self._engine_actions = {action_label(action): action for action in game.playable_actions}
        if len(self._engine_actions) != len(game.playable_actions):
            raise ValueError("duplicate Action labels in Position")

    @property
    def seat_to_act(self) -> Seat:
        return Seat(self._game.state.current_color().name)

    def legal_actions(self) -> tuple[Action, ...]:
        return tuple(Action(label) for label in self._engine_actions)

    @property
    def num_players(self) -> int:
        return len(self._game.state.colors)

    def observation(self) -> Observation:
        return feature_vector(self._game, self._game.state.current_color())

    def observation_after(self, action: Action) -> Observation:
        actor = self._game.state.current_color()
        clone = _copy_without_sharing_rng(self._game)
        clone.execute(self._engine_actions[action.label])
        return feature_vector(clone, actor)

    def write_png(self, path: Path) -> Path:
        from catan_coach.engine.render import write_position_png

        return write_position_png(self._game, path)
