"""A Seat that plays the Action with the highest Win Probability."""

from __future__ import annotations

from catanatron.game import Game
from catanatron.models.enums import Action
from catanatron.models.player import Color, Player

from catan_coach.domain.analysis import analyze
from catan_coach.domain.prediction import WinProbabilityModel
from catan_coach.engine.position import EnginePosition, action_label


class WinProbabilityPlayer(Player):  # type: ignore[misc]
    """Chooses by the model. Ties break on Action label, matching Analysis."""

    def __init__(self, color: Color, model: WinProbabilityModel) -> None:
        super().__init__(color)
        self._model = model

    def decide(self, game: Game, playable_actions: list[Action]) -> Action:
        if len(playable_actions) == 1:
            return playable_actions[0]
        best = analyze(EnginePosition(game), self._model).ranked[0].action.label
        for action in playable_actions:
            if action_label(action) == best:
                return action
        raise ValueError(f"best Action {best} is not playable")
