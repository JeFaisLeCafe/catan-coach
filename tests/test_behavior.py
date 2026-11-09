from __future__ import annotations

import pytest
from catanatron.game import Game
from catanatron.models.enums import Action, ActionRecord, ActionType
from catanatron.models.player import Color, SimplePlayer

from catan_coach.engine.behavior import BehaviorTracker, node_touches_port, opening_pips

pytestmark = pytest.mark.engine

_COLORS = (Color.RED, Color.BLUE, Color.ORANGE, Color.WHITE)
_RECORD = ActionRecord(Action(Color.RED, ActionType.END_TURN, None), None)


def _game() -> Game:
    return Game([SimplePlayer(color) for color in _COLORS], seed=1)


def _step(game: Game, tracker: BehaviorTracker) -> None:
    initial = game.state.is_initial_build_phase
    action = game.state.current_player().decide(game, game.playable_actions)
    record = game.execute(action)
    tracker.observe(initial, action, record, game)


def test_setup_builds_are_excluded_and_pips_count_each_settlement() -> None:
    game = _game()
    tracker = BehaviorTracker.start(game)
    nodes: dict[int, list[int]] = {index: [] for index in range(4)}
    while game.state.is_initial_build_phase:
        action = game.playable_actions[0]
        if action.action_type == ActionType.BUILD_SETTLEMENT:
            nodes[game.state.color_to_index[action.color]].append(int(action.value))
        _step(game, tracker)

    profiles = tracker.finish_partial(game)
    for index, profile in enumerate(profiles):
        assert profile.counts.settlements == 0
        assert profile.counts.roads == 0
        assert profile.counts.initial_pips == sum(opening_pips(game, node) for node in nodes[index])
        assert profile.counts.initial_resources == len(
            {
                tile.resource
                for node in nodes[index]
                for tile in game.state.board.map.adjacent_tiles[node]
                if tile.resource is not None
            }
        )
        assert profile.counts.adjacent_port is any(
            node_touches_port(game, node) for node in nodes[index]
        )


def test_post_setup_actions_are_counted_independently() -> None:
    game = _game()
    tracker = BehaviorTracker.start(game)
    red = Color.RED
    events = (
        (ActionType.BUILD_SETTLEMENT, "settlements"),
        (ActionType.BUILD_CITY, "cities"),
        (ActionType.BUILD_ROAD, "roads"),
        (ActionType.BUY_DEVELOPMENT_CARD, "development_cards"),
        (ActionType.PLAY_KNIGHT_CARD, "knights"),
        (ActionType.OFFER_TRADE, "offers"),
        (ActionType.ACCEPT_TRADE, "acceptances"),
        (ActionType.CONFIRM_TRADE, "completed_trades"),
        (ActionType.MARITIME_TRADE, "maritime_trades"),
    )
    for action_type, _name in events:
        tracker.observe(False, Action(red, action_type, 0), _RECORD, game)
    again = BehaviorTracker.start(game)
    for action_type, _name in events:
        again.observe(False, Action(red, action_type, 0), _RECORD, game)

    profile = tracker.finish_partial(game)[game.state.color_to_index[red]]
    assert profile.counts.settlements == 1
    assert profile.counts.cities == 1
    assert profile.counts.roads == 1
    assert profile.counts.development_cards == 1
    assert profile.counts.knights == 1
    assert profile.counts.offers == 1
    assert profile.counts.acceptances == 1
    assert profile.counts.completed_trades == 1
    assert profile.counts.maritime_trades == 1
    assert profile.counts.first_build == "settlement"
    assert tracker.finish_partial(game) == again.finish_partial(game)


def test_port_adjacency_is_limited_to_setup_and_actual_ports() -> None:
    game = _game()
    ports = {node for nodes in game.state.board.map.port_nodes.values() for node in nodes}
    inland = next(
        node
        for node in game.state.board.map.adjacent_tiles
        if node not in ports and opening_pips(game, node)
    )
    port = next(iter(ports))
    tracker = BehaviorTracker.start(game)
    tracker.observe(True, Action(Color.BLUE, ActionType.BUILD_SETTLEMENT, port), _RECORD, game)
    tracker.observe(True, Action(Color.BLUE, ActionType.BUILD_SETTLEMENT, inland), _RECORD, game)
    tracker.observe(False, Action(Color.RED, ActionType.BUILD_SETTLEMENT, port), _RECORD, game)

    profiles = tracker.finish_partial(game)
    blue = profiles[game.state.color_to_index[Color.BLUE]]
    red = profiles[game.state.color_to_index[Color.RED]]
    assert blue.counts.adjacent_port
    assert red.counts.adjacent_port is False
    assert red.counts.settlements == 1


def test_a_short_game_records_one_winner_and_hidden_points() -> None:
    game = Game([SimplePlayer(color) for color in _COLORS], seed=2, vps_to_win=4)
    tracker = BehaviorTracker.start(game)
    while game.winning_color() is None and game.state.num_turns < 40:
        _step(game, tracker)
    if game.winning_color() is None:
        key = "P0_ACTUAL_VICTORY_POINTS"
        game.state.player_state[key] = game.state.player_state["P0_VICTORY_POINTS"] + 1
        partial = tracker.finish_partial(game)
        assert partial[0].actual_victory_points == partial[0].public_victory_points + 1
        return
    profiles = tracker.finish(game)
    assert sum(profile.won for profile in profiles) == 1
