"""Reduce a Catanatron game to the Strategy Lab's Behavior Profiles.

Counts are facts about Actions and the final board. They do not infer intent,
affordability, or whether a trade was good.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from catanatron.game import Game
from catanatron.models.enums import Action, ActionRecord, ActionType
from catanatron.models.map import number_probability
from catanatron.state_functions import (
    get_actual_victory_points,
    get_largest_army,
    get_longest_road_color,
    get_visible_victory_points,
)

from catan_coach.domain.experiment import (
    BehaviorCounts,
    BehaviorProfile,
    BuildCategory,
    PartialBehaviorProfile,
)

_BUILD: dict[ActionType, BuildCategory] = {
    ActionType.BUILD_SETTLEMENT: "settlement",
    ActionType.BUILD_CITY: "city",
    ActionType.BUILD_ROAD: "road",
    ActionType.BUY_DEVELOPMENT_CARD: "development_card",
}


@dataclass
class _Seat:
    setup_nodes: list[int] = field(default_factory=list)
    settlements: int = 0
    cities: int = 0
    roads: int = 0
    development_cards: int = 0
    knights: int = 0
    offers: int = 0
    acceptances: int = 0
    completed_trades: int = 0
    maritime_trades: int = 0
    first_build: BuildCategory | None = None


class BehaviorTracker:
    """One tracker follows one game. Reuse the definitions; do not copy them."""

    def __init__(self, seats: dict[int, _Seat]) -> None:
        self._seats = seats

    @classmethod
    def start(cls, game: Game) -> BehaviorTracker:
        return cls({index: _Seat() for index in range(len(game.state.colors))})

    def observe(
        self,
        before_initial_build: bool,
        action: Action,
        _record: ActionRecord,
        game: Game,
    ) -> None:
        seat = game.state.color_to_index[action.color]
        counts = self._seats[seat]
        if before_initial_build and action.action_type == ActionType.BUILD_SETTLEMENT:
            counts.setup_nodes.append(int(action.value))
            return
        if before_initial_build:
            return
        category = _BUILD.get(action.action_type)
        if category == "settlement":
            counts.settlements += 1
        elif category == "city":
            counts.cities += 1
        elif category == "road":
            counts.roads += 1
        elif category == "development_card":
            counts.development_cards += 1
        if category is not None and counts.first_build is None:
            counts.first_build = category
        if action.action_type == ActionType.PLAY_KNIGHT_CARD:
            counts.knights += 1
        elif action.action_type == ActionType.OFFER_TRADE:
            counts.offers += 1
        elif action.action_type == ActionType.ACCEPT_TRADE:
            counts.acceptances += 1
        elif action.action_type == ActionType.CONFIRM_TRADE:
            counts.completed_trades += 1
        elif action.action_type == ActionType.MARITIME_TRADE:
            counts.maritime_trades += 1

    def finish(self, game: Game) -> tuple[BehaviorProfile, ...]:
        winner = game.winning_color()
        return tuple(
            BehaviorProfile(
                counts=_counts(game, index, seat),
                public_victory_points=get_visible_victory_points(game.state, color),
                actual_victory_points=get_actual_victory_points(game.state, color),
                won=color == winner,
                longest_road=get_longest_road_color(game.state) == color,
                largest_army=get_largest_army(game.state)[0] == color,
            )
            for index, (color, seat) in enumerate(
                zip(game.state.colors, _ordered(self), strict=True)
            )
        )

    def finish_partial(self, game: Game) -> tuple[PartialBehaviorProfile, ...]:
        return tuple(
            PartialBehaviorProfile(
                counts=_counts(game, index, seat),
                public_victory_points=get_visible_victory_points(game.state, color),
                actual_victory_points=get_actual_victory_points(game.state, color),
                longest_road=get_longest_road_color(game.state) == color,
                largest_army=get_largest_army(game.state)[0] == color,
            )
            for index, (color, seat) in enumerate(
                zip(game.state.colors, _ordered(self), strict=True)
            )
        )


def _ordered(tracker: BehaviorTracker) -> tuple[_Seat, ...]:
    return tuple(tracker._seats[index] for index in range(len(tracker._seats)))


def _counts(game: Game, seat: int, counts: _Seat) -> BehaviorCounts:
    resources: set[str] = set()
    pips = 0
    port = False
    ports = {node for nodes in game.state.board.map.port_nodes.values() for node in nodes}
    for node in counts.setup_nodes:
        if node in ports:
            port = True
        for tile in game.state.board.map.adjacent_tiles[node]:
            if tile.resource is None or tile.number is None:
                continue
            resources.add(str(tile.resource))
            pips += round(number_probability(tile.number) * 36)
    return BehaviorCounts(
        initial_resources=len(resources),
        initial_pips=pips,
        adjacent_port=port,
        settlements=counts.settlements,
        cities=counts.cities,
        roads=counts.roads,
        development_cards=counts.development_cards,
        knights=counts.knights,
        offers=counts.offers,
        acceptances=counts.acceptances,
        completed_trades=counts.completed_trades,
        maritime_trades=counts.maritime_trades,
        first_build=counts.first_build,
    )


def opening_pips(game: Game, node_id: int) -> int:
    """Integer dice pips of one settlement, for tests and preference checks."""
    total = 0
    for tile in game.state.board.map.adjacent_tiles[node_id]:
        if tile.resource is None or tile.number is None:
            continue
        total += round(number_probability(tile.number) * 36)
    return total


def node_touches_port(game: Game, node_id: int) -> bool:
    return any(node_id in nodes for nodes in game.state.board.map.port_nodes.values())
