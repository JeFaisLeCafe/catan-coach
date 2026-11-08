"""Domestic offers the engine never puts on the move list.

Catanatron accepts OFFER_TRADE, but generate_playable_actions only lists
maritime trades. A bounded set is added here so Corpus play, the analyzer,
and search all see the same Actions. The proposer looks at its own hand
only; opponent hands stay hidden until a responder decides.
"""

from __future__ import annotations

from collections.abc import Sequence

from catanatron.game import Game
from catanatron.models.decks import (
    CITY_COST_FREQDECK,
    DEVELOPMENT_CARD_COST_FREQDECK,
    ROAD_COST_FREQDECK,
    SETTLEMENT_COST_FREQDECK,
)
from catanatron.models.enums import SETTLEMENT, Action, ActionPrompt, ActionRecord, ActionType
from catanatron.state import State
from catanatron.state_functions import (
    get_player_freqdeck,
    player_has_rolled,
    player_key,
)

OFFER_CAP = 10
_RESOURCE_NAMES = ("wood", "brick", "sheep", "wheat", "ore")
_TARGETS: tuple[tuple[str, list[int]], ...] = (
    ("city", list(CITY_COST_FREQDECK)),
    ("settlement", list(SETTLEMENT_COST_FREQDECK)),
    ("road", list(ROAD_COST_FREQDECK)),
    ("development", list(DEVELOPMENT_CARD_COST_FREQDECK)),
)


def listed_actions(game: Game) -> list[Action]:
    """Engine moves, plus domestic offers when this seat may propose one."""
    from catan_coach.engine.position import action_label

    actions = list(game.playable_actions)
    known = {action_label(action) for action in actions}
    for offer in domestic_offers(game):
        label = action_label(offer)
        if label not in known:
            actions.append(offer)
            known.add(label)
    return actions


def domestic_offers(game: Game) -> list[Action]:
    state = game.state
    if state.current_prompt != ActionPrompt.PLAY_TURN or state.is_road_building:
        return []
    color = state.current_color()
    if not player_has_rolled(state, color) or _already_offered(game):
        return []
    hand = list(get_player_freqdeck(state, color))
    ranked: list[tuple[int, int, int, int, tuple[int, ...]]] = []
    for name, cost in _TARGETS:
        if not _target_available(game, name):
            continue
        missing = [index for index in range(5) if hand[index] < cost[index]]
        if not missing:
            continue
        surplus = [index for index in range(5) if hand[index] > cost[index]]
        shortfall = sum(cost[index] - hand[index] for index in missing)
        for asked in missing:
            for given in surplus:
                extra = hand[given] - cost[given]
                if extra >= 1:
                    ranked.append((shortfall, 1, asked, given, _offer(given, 1, asked)))
                if extra >= 2:
                    ranked.append((shortfall, 2, asked, given, _offer(given, 2, asked)))
    ranked.sort()
    offers: list[Action] = []
    seen: set[tuple[int, ...]] = set()
    for _, _, _, _, freq in ranked:
        if freq in seen:
            continue
        seen.add(freq)
        offers.append(Action(color, ActionType.OFFER_TRADE, freq))
        if len(offers) == OFFER_CAP:
            break
    return offers


def describe_offer(value: Sequence[int]) -> str:
    return f"offer {_phrase(value[:5])} for {_phrase(value[5:10])}"


def _already_offered(game: Game) -> bool:
    """One domestic proposal per turn, so a refusal cannot be asked again."""
    color = game.state.current_color()
    for record in reversed(game.state.action_records):
        action = record.action
        if action.action_type == ActionType.END_TURN:
            return False
        if action.action_type == ActionType.ROLL and action.color == color:
            return False
        if action.action_type == ActionType.OFFER_TRADE and action.color == color:
            return True
    return False


def _target_available(game: Game, name: str) -> bool:
    state = game.state
    color = state.current_color()
    key = player_key(state, color)
    if name == "city":
        return int(state.player_state[f"{key}_CITIES_AVAILABLE"]) > 0 and bool(
            state.buildings_by_color[color][SETTLEMENT]
        )
    if name == "settlement":
        return int(state.player_state[f"{key}_SETTLEMENTS_AVAILABLE"]) > 0
    if name == "road":
        return int(state.player_state[f"{key}_ROADS_AVAILABLE"]) > 0
    return len(state.development_listdeck) > 0


def _offer(given: int, give_count: int, asked: int) -> tuple[int, ...]:
    freq = [0] * 10
    freq[given] = give_count
    freq[5 + asked] = 1
    return tuple(freq)


def _phrase(freq: Sequence[int]) -> str:
    parts = [f"{count} {name}" for count, name in zip(freq, _RESOURCE_NAMES, strict=True) if count]
    return " ".join(parts)


_REPLIES_INSTALLED = False


def install_trade_replies() -> None:
    """A refused offer keeps moving around the table.

    The search treats an action it does not know as a crash, so a bot that can
    accept or refuse never answers and the browser is left with no buttons.
    A reply has one outcome. The next seat is the next other player: the
    proposer does not sit down to answer their own offer.
    """
    global _REPLIES_INSTALLED
    if _REPLIES_INSTALLED:
        return
    import catanatron.apply_action as apply_action
    from catanatron.players.tree_search_utils import DETERMINISTIC_ACTIONS

    DETERMINISTIC_ACTIONS.update(
        {
            ActionType.OFFER_TRADE,
            ActionType.ACCEPT_TRADE,
            ActionType.REJECT_TRADE,
            ActionType.CONFIRM_TRADE,
            ActionType.CANCEL_TRADE,
        }
    )
    apply_action.apply_accept_trade = _accept_trade
    apply_action.apply_reject_trade = _reject_trade
    _REPLIES_INSTALLED = True


def _next_other_seat(state: State) -> int | None:
    offerer = state.colors[state.current_turn_index]
    for index, color in enumerate(state.colors):
        if index > state.current_player_index and color != offerer:
            return index
    return None


def _accept_trade(state: State, action: Action) -> ActionRecord:
    index = state.colors.index(action.color)
    accepted = list(state.acceptees)
    accepted[index] = True
    state.acceptees = tuple(accepted)
    nxt = _next_other_seat(state)
    if nxt is None:
        state.current_player_index = state.current_turn_index
        state.current_prompt = ActionPrompt.DECIDE_ACCEPTEES
    else:
        state.current_player_index = nxt
    return ActionRecord(action=action, result=None)


def _reject_trade(state: State, action: Action) -> ActionRecord:
    import catanatron.apply_action as apply_action

    nxt = _next_other_seat(state)
    if nxt is not None:
        state.current_player_index = nxt
        return ActionRecord(action=action, result=None)
    if sum(state.acceptees) == 0:
        apply_action.reset_trading_state(state)
        state.current_player_index = state.current_turn_index
        state.current_prompt = ActionPrompt.PLAY_TURN
    else:
        state.current_player_index = state.current_turn_index
        state.current_prompt = ActionPrompt.DECIDE_ACCEPTEES
    return ActionRecord(action=action, result=None)
