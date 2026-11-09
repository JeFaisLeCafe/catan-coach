"""Action-selection deltas. These never replace a model's Win Probability."""

from __future__ import annotations

from catanatron.game import Game
from catanatron.models.enums import Action, ActionType

from catan_coach.domain.experiment import PolicyPreference, PreferenceCategory
from catan_coach.engine.behavior import node_touches_port


def selection_delta(game: Game, action: Action, preferences: tuple[PolicyPreference, ...]) -> float:
    initial = game.state.is_initial_build_phase
    return sum(
        preference.delta
        for preference in preferences
        if _matches(game, action, preference.category, initial_build=initial)
    )


def _matches(
    game: Game,
    action: Action,
    category: PreferenceCategory,
    *,
    initial_build: bool,
) -> bool:
    if category == "settlement":
        return bool(action.action_type == ActionType.BUILD_SETTLEMENT)
    if category == "city":
        return bool(action.action_type == ActionType.BUILD_CITY)
    if category == "road":
        return bool(action.action_type == ActionType.BUILD_ROAD)
    if category == "development_card":
        return bool(action.action_type == ActionType.BUY_DEVELOPMENT_CARD)
    if category == "port":
        return bool(
            initial_build
            and action.action_type == ActionType.BUILD_SETTLEMENT
            and node_touches_port(game, int(action.value))
        )
    return False
