"""A Seat that plays the Action with the highest Win Probability.

An initial settlement is the exception: production pips choose it. The
installed model's opening ranking does not depend on the board.
"""

from __future__ import annotations

import random
from collections.abc import Callable

from catanatron.game import Game
from catanatron.models.enums import Action, ActionPrompt, ActionType
from catanatron.models.player import Color, Player

from catan_coach.domain.policy import choose_opening_settlement
from catan_coach.domain.prediction import WinProbabilityModel
from catan_coach.domain.review import choose_near_tie
from catan_coach.domain.search import Budget
from catan_coach.engine.behavior import opening_pips
from catan_coach.engine.position import action_label
from catan_coach.engine.scoring import rank_resolved, reply_helps
from catan_coach.engine.search import refine_position
from catan_coach.engine.trades import listed_actions

# Corpus games look this far ahead. A count, not a clock, so a seed replays.
CORPUS_SEARCH_SIMULATIONS = 4
CORPUS_SEARCH_DEPTH = 16

PreferenceAdjuster = Callable[[Game, Action], float]


class WinProbabilityPlayer(Player):  # type: ignore[misc]
    """Chooses by the model. Exact ties break on Action label, matching Analysis.

    Initial settlements are chosen by production pips. Corpus games set
    `explore` so a near-tie is sampled from the game's own random stream.
    `search_simulations` looks ahead that many simulations, including on a
    trade reply. A single legal Action is never searched.
    """

    def __init__(
        self,
        color: Color,
        model: WinProbabilityModel,
        *,
        explore: bool = False,
        search_simulations: int = 0,
        preferences: PreferenceAdjuster | None = None,
    ) -> None:
        if preferences is not None and search_simulations > 0:
            raise ValueError("preferences require zero search simulations")
        super().__init__(color)
        self._model = model
        self._explore = explore
        self._search_simulations = search_simulations
        self._preferences = preferences

    def decide(self, game: Game, playable_actions: list[Action]) -> Action:
        actions = _choices(game, playable_actions)
        if len(actions) == 1:
            return actions[0]
        opening = _opening_settlement(game, actions)
        if opening is not None:
            return opening
        if self._search_simulations > 0:
            probabilities = _search_probabilities(game, self._model, self._search_simulations)
            return _choose(
                actions, probabilities, game, explore=self._explore, adjust=self._preferences
            )
        if game.state.current_prompt == ActionPrompt.DECIDE_TRADE:
            return _reply(game, playable_actions, reply_helps(game, self._model))
        ranked = rank_resolved(game, self._model)
        probabilities = {row.action.label: row.win_probability for row in ranked.ranked}
        return _choose(
            actions, probabilities, game, explore=self._explore, adjust=self._preferences
        )


def _opening_settlement(game: Game, actions: list[Action]) -> Action | None:
    if not game.state.is_initial_build_phase:
        return None
    if not actions or any(action.action_type != ActionType.BUILD_SETTLEMENT for action in actions):
        return None
    label = choose_opening_settlement(
        (action_label(action), opening_pips(game, int(action.value))) for action in actions
    )
    for action in actions:
        if action_label(action) == label:
            return action
    raise ValueError(f"opening settlement {label} is not playable")


def _choices(game: Game, playable_actions: list[Action]) -> list[Action]:
    if game.state.current_prompt == ActionPrompt.DECIDE_TRADE:
        return list(playable_actions)
    return listed_actions(game)


def _search_probabilities(
    game: Game, model: WinProbabilityModel, simulations: int
) -> dict[str, float]:
    # Derived from the game seed and the ply, so the game's own stream stays
    # free for dice and for the near-tie sample. The same seed replays.
    child = random.Random(int(game.seed) * 1_000_003 + len(game.state.action_records))
    snapshots = list(
        refine_position(
            game,
            model,
            budget=Budget("simulations", simulations=simulations),
            clock=lambda: 0.0,
            rng=child,
            stop=lambda: False,
            batch_size=1,
            max_depth=CORPUS_SEARCH_DEPTH,
        )
    )
    return {line.action: line.win_probability for line in snapshots[-1].lines}


def _choose(
    actions: list[Action],
    probabilities: dict[str, float],
    game: Game,
    *,
    explore: bool,
    adjust: PreferenceAdjuster | None = None,
) -> Action:
    ranked: list[tuple[str, float]] = []
    for action in actions:
        label = action_label(action)
        if label not in probabilities:
            continue
        utility = probabilities[label]
        if adjust is not None:
            utility += adjust(game, action)
        ranked.append((label, utility))
    if not ranked:
        raise ValueError("no scored Action is legal")
    label = choose_near_tie(
        ranked,
        explore=explore,
        pick=game.state.random.randrange,
    )
    for action in actions:
        if action_label(action) == label:
            return action
    raise ValueError(f"best Action {label} is not playable")


def _reply(game: Game, playable_actions: list[Action], accept: bool) -> Action:
    chosen_type = ActionType.ACCEPT_TRADE if accept else ActionType.REJECT_TRADE
    for action in playable_actions:
        if action.action_type == chosen_type:
            return action
    for action in playable_actions:
        if action.action_type == ActionType.REJECT_TRADE:
            return action
    raise ValueError("no reply to the pending trade")
