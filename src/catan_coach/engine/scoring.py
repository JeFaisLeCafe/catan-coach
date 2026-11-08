"""Win Probabilities for Actions, with domestic trades scored after they resolve.

An offer does not change either hand until it is confirmed, and the Observation
has no pending-trade fields. Two offers therefore look alike after one ply.
The proposer is scored on the hand it would hold if the trade completed. It
does not read opponent hands. The responder, on their own turn, is scored on
the exchange of both hands.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from catanatron.game import Game
from catanatron.models.enums import ActionPrompt, ActionType
from catanatron.models.player import Color
from catanatron.state_functions import player_freqdeck_add, player_freqdeck_subtract

from catan_coach.domain.analysis import (
    Analysis,
    Contribution,
    ExplainingModel,
    RankedAction,
    analyze,
)
from catan_coach.domain.position import Action
from catan_coach.domain.prediction import WinProbabilityModel
from catan_coach.engine.features import feature_vector
from catan_coach.engine.position import EnginePosition, _copy_without_sharing_rng, action_label
from catan_coach.engine.trades import domestic_offers


def rank_resolved(game: Game, model: WinProbabilityModel) -> Analysis:
    """One-ply Analysis, with offers and replies scored on the resolved hands."""
    base = analyze(EnginePosition(game), model)
    win_probabilities = {row.action.label: row.win_probability for row in base.ranked}
    reasons = {row.action.label: row.reasons for row in base.ranked}
    color = game.state.current_color()
    offers = domestic_offers(game)
    if offers:
        matrix = np.vstack(
            [
                feature_vector(
                    _with_own_exchange(game, color, offer.value[:5], offer.value[5:10]),
                    color,
                )
                for offer in offers
            ]
        )
        explanations = _explain(model, matrix)
        for offer, probability, explanation in zip(
            offers, model.predict(matrix), explanations, strict=True
        ):
            label = action_label(offer)
            win_probabilities[label] = float(probability)
            reasons[label] = explanation
    if game.state.current_prompt == ActionPrompt.DECIDE_TRADE:
        _score_reply(game, model, color, win_probabilities, reasons)
    best = max(win_probabilities.values())
    ranked = tuple(
        sorted(
            (
                RankedAction(
                    Action(label),
                    probability,
                    best - probability,
                    reasons.get(label, ()),
                )
                for label, probability in win_probabilities.items()
            ),
            key=lambda row: (-row.win_probability, row.action.label),
        )
    )
    return Analysis(seat=base.seat, ranked=tuple(ranked))


def reply_helps(game: Game, model: WinProbabilityModel) -> bool:
    """True when accepting the pending trade raises this seat's Win Probability."""
    state = game.state
    if state.current_prompt != ActionPrompt.DECIDE_TRADE or state.current_trade is None:
        return False
    color = state.current_color()
    current = _probability(game, model, color)
    proposer = state.colors[state.current_turn_index]
    trade = state.current_trade
    resolved = _with_exchange(game, proposer, trade[:5], color, trade[5:10])
    return _probability(resolved, model, color) > current


def _score_reply(
    game: Game,
    model: WinProbabilityModel,
    color: Color,
    win_probabilities: dict[str, float],
    reasons: dict[str, tuple[Contribution, ...]],
) -> None:
    accept_label = None
    reject_label = None
    for label in win_probabilities:
        if label.startswith(ActionType.ACCEPT_TRADE.name):
            accept_label = label
        elif label.startswith(ActionType.REJECT_TRADE.name):
            reject_label = label
    if accept_label is None or reject_label is None or game.state.current_trade is None:
        return
    current = win_probabilities[reject_label]
    proposer = game.state.colors[game.state.current_turn_index]
    trade = game.state.current_trade
    resolved, explanation = _evaluation(
        _with_exchange(game, proposer, trade[:5], color, trade[5:10]), model, color
    )
    reasons[accept_label] = explanation
    if resolved > current:
        win_probabilities[accept_label] = resolved
        return
    # A tie is not an improvement. Keep reject strictly ahead of accept.
    win_probabilities[accept_label] = min(win_probabilities[accept_label], current)
    win_probabilities[reject_label] = win_probabilities[accept_label] + 1e-9


def _probability(game: Game, model: WinProbabilityModel, color: Color) -> float:
    probability, _ = _evaluation(game, model, color)
    return probability


def _evaluation(
    game: Game,
    model: WinProbabilityModel,
    color: Color,
) -> tuple[float, tuple[Contribution, ...]]:
    matrix = feature_vector(game, color).reshape(1, -1)
    return float(model.predict(matrix)[0]), _explain(model, matrix)[0]


def _explain(
    model: WinProbabilityModel, matrix: np.ndarray
) -> tuple[tuple[Contribution, ...], ...]:
    if isinstance(model, ExplainingModel):
        explanations = model.explain(matrix)
        if len(explanations) != matrix.shape[0]:
            raise ValueError("explain() must return one reason list per Action")
        return explanations
    return tuple(() for _ in range(matrix.shape[0]))


def _with_own_exchange(
    game: Game,
    color: Color,
    offering: Sequence[int],
    asking: Sequence[int],
) -> Game:
    clone = _copy_without_sharing_rng(game)
    player_freqdeck_subtract(clone.state, color, list(offering))
    player_freqdeck_add(clone.state, color, list(asking))
    return clone


def _with_exchange(
    game: Game,
    proposer: Color,
    offering: Sequence[int],
    responder: Color,
    asking: Sequence[int],
) -> Game:
    clone = _with_own_exchange(game, proposer, offering, asking)
    player_freqdeck_subtract(clone.state, responder, list(asking))
    player_freqdeck_add(clone.state, responder, list(offering))
    return clone
