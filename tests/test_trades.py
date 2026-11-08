"""Domestic offers are proposed from one seat's hand and resolved before scoring."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.engine

catanatron = pytest.importorskip("catanatron")

import numpy as np  # noqa: E402
from catanatron.game import Game  # noqa: E402
from catanatron.models.actions import generate_playable_actions  # noqa: E402
from catanatron.models.enums import (  # noqa: E402
    SETTLEMENT,
    ActionPrompt,
    ActionType,
)
from catanatron.models.player import Color, SimplePlayer  # noqa: E402
from catanatron.state_functions import (  # noqa: E402
    get_player_freqdeck,
    player_freqdeck_add,
    player_key,
)

from catan_coach.domain.analysis import Contribution  # noqa: E402
from catan_coach.domain.search import Budget  # noqa: E402
from catan_coach.engine.features import index_of  # noqa: E402
from catan_coach.engine.model_player import WinProbabilityPlayer  # noqa: E402
from catan_coach.engine.position import EnginePosition  # noqa: E402
from catan_coach.engine.scoring import rank_resolved  # noqa: E402
from catan_coach.engine.search import refine_position  # noqa: E402
from catan_coach.engine.trades import OFFER_CAP, domestic_offers  # noqa: E402

COLORS = (Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE)


class _Need:
    """Ore matters once a seat is ahead; wheat matters while it is behind."""

    name = "need"

    def predict(self, features: np.ndarray) -> np.ndarray:
        vp = features[:, index_of("P0_ACTUAL_VPS", 4)]
        ore = features[:, index_of("P0_ORE_IN_HAND", 4)]
        wheat = features[:, index_of("P0_WHEAT_IN_HAND", 4)]
        liked = np.where(vp >= 5, ore, wheat)
        return np.clip(0.02 * vp + 0.1 * liked, 0.0, 1.0)

    def explain(self, features: np.ndarray) -> tuple[tuple[Contribution, ...], ...]:
        ore = features[:, index_of("P0_ORE_IN_HAND", 4)]
        wheat = features[:, index_of("P0_WHEAT_IN_HAND", 4)]
        return tuple(
            (Contribution(f"ore={int(row_ore)}, wheat={int(row_wheat)}", 0.1),)
            for row_ore, row_wheat in zip(ore, wheat, strict=True)
        )


def _game(players: list[SimplePlayer] | None = None) -> Game:
    seated = players if players is not None else [SimplePlayer(color) for color in COLORS]
    return Game(seated, seed=1)


def _main_turn(game: Game, color: Color, hand: list[int], vp: int, *, city: bool) -> None:
    state = game.state
    state.is_initial_build_phase = False
    state.current_prompt = ActionPrompt.PLAY_TURN
    index = state.colors.index(color)
    state.current_player_index = index
    state.current_turn_index = index
    key = player_key(state, color)
    state.player_state[f"{key}_HAS_ROLLED"] = True
    state.player_state[f"{key}_VICTORY_POINTS"] = vp
    state.player_state[f"{key}_ACTUAL_VICTORY_POINTS"] = vp
    for resource in ("WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"):
        state.player_state[f"{key}_{resource}_IN_HAND"] = 0
    player_freqdeck_add(state, color, hand)
    if city:
        node = next(iter(next(iter(state.board.map.land_tiles.values())).nodes.values()))
        state.buildings_by_color[color][SETTLEMENT].append(node)
    game.playable_actions = generate_playable_actions(state)


def test_offers_come_from_this_hand_and_stay_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    game = _game()
    color = game.state.current_color()
    _main_turn(game, color, [4, 4, 0, 0, 0], vp=2, city=True)
    seen: list[Color] = []

    def spy(state: object, asked: Color) -> list[int]:
        seen.append(asked)
        return [int(card) for card in get_player_freqdeck(state, asked)]

    monkeypatch.setattr("catan_coach.engine.trades.get_player_freqdeck", spy)

    offers = domestic_offers(game)

    assert offers
    assert len(offers) <= OFFER_CAP
    assert seen == [color]
    for offer in offers:
        freq = tuple(offer.value)
        assert sum(freq[:5]) in (1, 2)
        assert sum(freq[5:]) == 1
        assert not any(gave and asked for gave, asked in zip(freq[:5], freq[5:], strict=True))
    assert any("OFFER_TRADE" in action.label for action in EnginePosition(game).legal_actions())
    assert all(action.action_type != ActionType.OFFER_TRADE for action in game.playable_actions)


def test_a_helpful_trade_is_offered_accepted_and_confirmed() -> None:
    model = _Need()
    players = [WinProbabilityPlayer(color, model) for color in COLORS]
    game = Game(players, seed=2)
    proposer = game.state.current_color()
    _main_turn(game, proposer, [0, 0, 0, 3, 0], vp=6, city=True)
    for color in game.state.colors:
        if color == proposer:
            continue
        key = player_key(game.state, color)
        game.state.player_state[f"{key}_VICTORY_POINTS"] = 2
        game.state.player_state[f"{key}_ACTUAL_VICTORY_POINTS"] = 2
        for resource in ("WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"):
            game.state.player_state[f"{key}_{resource}_IN_HAND"] = 0
        player_freqdeck_add(game.state, color, [0, 0, 0, 0, 2])

    types: list[ActionType] = []
    for _ in range(8):
        actor = game.state.current_player()
        action = actor.decide(game, game.playable_actions)
        types.append(action.action_type)
        game.execute(action)
        if action.action_type == ActionType.CONFIRM_TRADE:
            break

    assert ActionType.OFFER_TRADE in types
    assert ActionType.ACCEPT_TRADE in types
    assert types[-1] == ActionType.CONFIRM_TRADE
    offer = next(
        record.action
        for record in game.state.action_records
        if record.action.action_type == ActionType.OFFER_TRADE
    )
    assert tuple(offer.value[:5])[3] == 1
    assert tuple(offer.value[5:10])[4] == 1


def test_a_trade_that_does_not_help_is_refused() -> None:
    model = _Need()
    players = [WinProbabilityPlayer(color, model) for color in COLORS]
    game = Game(players, seed=3)
    proposer = game.state.current_color()
    _main_turn(game, proposer, [0, 0, 0, 3, 0], vp=6, city=True)
    for color in game.state.colors:
        if color == proposer:
            continue
        key = player_key(game.state, color)
        game.state.player_state[f"{key}_VICTORY_POINTS"] = 6
        game.state.player_state[f"{key}_ACTUAL_VICTORY_POINTS"] = 6
        for resource in ("WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"):
            game.state.player_state[f"{key}_{resource}_IN_HAND"] = 0
        player_freqdeck_add(game.state, color, [0, 0, 0, 0, 2])

    types: list[ActionType] = []
    for _ in range(6):
        actor = game.state.current_player()
        action = actor.decide(game, game.playable_actions)
        types.append(action.action_type)
        game.execute(action)

    assert types.count(ActionType.OFFER_TRADE) == 1
    assert ActionType.REJECT_TRADE in types
    assert ActionType.CONFIRM_TRADE not in types


def test_search_ranks_a_resolved_offer() -> None:
    import random

    game = _game()
    color = game.state.current_color()
    _main_turn(game, color, [0, 0, 0, 3, 0], vp=6, city=True)
    snapshots = list(
        refine_position(
            game,
            _Need(),
            budget=Budget("immediate"),
            clock=lambda: 0.0,
            rng=random.Random(0),
            stop=lambda: False,
        )
    )

    assert snapshots[0].lines[0].action.startswith("OFFER_TRADE")


def test_an_offer_explanation_uses_the_resolved_hand() -> None:
    game = _game()
    color = game.state.current_color()
    _main_turn(game, color, [0, 0, 0, 3, 0], vp=6, city=True)

    analysis = rank_resolved(game, _Need())
    offer = next(
        row
        for row in analysis.ranked
        if row.action.label.startswith("OFFER_TRADE")
        and "(0, 0, 0, 1, 0, 0, 0, 0, 0, 1)" in row.action.label
    )

    assert offer.reasons[0].label == "ore=1, wheat=2"
