"""The few Actions worth showing for the Position on screen.

A chess review lists a handful of lines. Here a line is the next Action, plus
the road that would follow an opening settlement. Win Probability still ranks
them. Placements that grant the same victory points tie, so those ties are
listed by the hexes they touch instead of by Action label.
"""

from __future__ import annotations

from catanatron.game import Game
from catanatron.models.enums import CITY, SETTLEMENT, Action, ActionPrompt, ActionType
from catanatron.models.map import LandTile, number_probability

from catan_coach.domain.analysis import RankedAction
from catan_coach.domain.prediction import WinProbabilityModel
from catan_coach.domain.review import NEAR_TIE_LOSS
from catan_coach.engine.position import _copy_without_sharing_rng, action_label
from catan_coach.engine.review import match_played_label
from catan_coach.engine.scoring import rank_resolved
from catan_coach.engine.trades import describe_offer, listed_actions

LINE_COUNT = 5
# A new resource is worth about as much as a weak number. Same ratio the
# engine's value function uses when it scores production.
_RESOURCE_VARIETY = 4 * 2.778 / 100


def action_summaries(game: Game) -> dict[str, str]:
    """A short reading of every legal Action, using the same wording as position lines."""
    return {action_label(action): _view(game, action)[1] for action in listed_actions(game)}


def position_lines(
    game: Game,
    model: WinProbabilityModel,
    *,
    played: str | None = None,
) -> dict[str, object]:
    """Rank the Position and keep the first five lines.

    `played` is the Action recorded from this Position, when the game continued.
    It stays in the list even if it is outside the first five.
    """
    seat = game.state.current_color().name
    if not game.playable_actions:
        return {
            "seat": seat,
            "forced": False,
            "ordering": "win_probability",
            "win_probability": None,
            "played": None,
            "lines": [],
        }

    views = {action_label(action): _view(game, action) for action in listed_actions(game)}
    analysis = rank_resolved(game, model)
    best = analysis.ranked[0].win_probability
    contenders = [row for row in analysis.ranked if best - row.win_probability <= NEAR_TIE_LOSS]
    others = [row for row in analysis.ranked if best - row.win_probability > NEAR_TIE_LOSS]
    ordering = "win_probability"
    if _scores_differ(contenders, views):
        contenders = sorted(
            contenders,
            key=lambda row: (-views[row.action.label][0], row.action.label),
        )
        ordering = "tiles"
    chosen = contenders[:LINE_COUNT]
    if len(chosen) < LINE_COUNT:
        chosen = [*chosen, *others[: LINE_COUNT - len(chosen)]]

    matched = _played_label(played, [row.action.label for row in analysis.ranked])
    if matched is not None and all(row.action.label != matched for row in chosen):
        chosen = [
            *chosen,
            next(row for row in analysis.ranked if row.action.label == matched),
        ]
    return {
        "seat": analysis.seat.name,
        "forced": analysis.is_forced,
        "ordering": ordering,
        "win_probability": best,
        "played": matched,
        "lines": [_payload(row, views[row.action.label][1]) for row in chosen],
    }


def _played_label(played: str | None, legal: list[str]) -> str | None:
    if played is None:
        return None
    try:
        return match_played_label(played, legal)
    except ValueError:
        return None


def _scores_differ(
    rows: list[RankedAction],
    views: dict[str, tuple[float, str]],
) -> bool:
    scores = {round(views[row.action.label][0], 6) for row in rows}
    return len(scores) > 1


def _payload(row: RankedAction, summary: str) -> dict[str, object]:
    return {
        "action": row.action.label,
        "summary": summary,
        "win_probability": row.win_probability,
        "loss": row.loss,
        "reasons": [{"label": reason.label, "delta": reason.delta} for reason in row.reasons],
    }


def _view(game: Game, action: Action) -> tuple[float, str]:
    value = action.value
    if action.action_type == ActionType.BUILD_SETTLEMENT and isinstance(value, int):
        if game.state.current_prompt == ActionPrompt.BUILD_INITIAL_SETTLEMENT:
            return _opening_settlement(game, action, value)
        return _node_pips(game, value), _describe_node(game, value)
    if action.action_type == ActionType.BUILD_CITY and isinstance(value, int):
        return _node_pips(game, value), _describe_node(game, value)
    if action.action_type == ActionType.BUILD_ROAD:
        return _road_view(game, _edge(value))
    if action.action_type == ActionType.OFFER_TRADE and isinstance(value, tuple):
        return 0.0, describe_offer(value)
    return 0.0, ""


def _opening_settlement(game: Game, action: Action, node_id: int) -> tuple[float, str]:
    spot = _describe_node(game, node_id)
    clone = _copy_without_sharing_rng(game)
    clone.execute(action)
    roads = [
        candidate
        for candidate in clone.playable_actions
        if candidate.action_type == ActionType.BUILD_ROAD
    ]
    if not roads:
        return _node_pips(game, node_id), spot
    best = max(roads, key=lambda road: _road_view(clone, _edge(road.value))[0])
    road_score, road_summary = _road_view(clone, _edge(best.value))
    return _node_pips(game, node_id) + road_score * 0.001, f"{spot}, then road {road_summary}"


def _road_view(game: Game, edge: tuple[int, int]) -> tuple[float, str]:
    far = _direction_node(game, edge)
    near = edge[0] if edge[1] == far else edge[1]
    fresh = _producing_except(game, far, near)
    if fresh:
        already = {tile.resource for tile in _producing(game, near)}
        added = {tile.resource for tile in fresh if tile.resource not in already}
        return _pip_sum(fresh) + len(added) * _RESOURCE_VARIETY, f"toward {_format_tiles(fresh)}"
    staying = _producing(game, far)
    text = _format_tiles(staying) if staying else "the coast"
    return 0.0, f"staying on {text}"


def _direction_node(game: Game, edge: tuple[int, int]) -> int:
    color = game.state.current_color()
    buildings = game.state.buildings_by_color[color]
    occupied = set(buildings[SETTLEMENT]) | set(buildings[CITY])
    start, end = edge
    if start in occupied and end not in occupied:
        return end
    if end in occupied and start not in occupied:
        return start
    return max(edge, key=lambda node: _node_pips(game, node))


def _describe_node(game: Game, node_id: int) -> str:
    tiles = _producing(game, node_id)
    return _format_tiles(tiles) if tiles else "desert"


def _node_pips(game: Game, node_id: int) -> float:
    tiles = _producing(game, node_id)
    resources = {tile.resource for tile in tiles}
    return _pip_sum(tiles) + len(resources) * _RESOURCE_VARIETY


def _producing(game: Game, node_id: int) -> list[LandTile]:
    return [
        tile for tile in game.state.board.map.adjacent_tiles[node_id] if tile.resource is not None
    ]


def _producing_except(game: Game, node_id: int, other_node: int) -> list[LandTile]:
    shared = {tile.id for tile in _producing(game, other_node)}
    return [tile for tile in _producing(game, node_id) if tile.id not in shared]


def _pip_sum(tiles: list[LandTile]) -> float:
    return float(sum(number_probability(tile.number) for tile in tiles))


def _format_tiles(tiles: list[LandTile]) -> str:
    ordered = sorted(
        tiles,
        key=lambda tile: (-number_probability(tile.number), str(tile.resource)),
    )
    return " · ".join(f"{tile.number} {str(tile.resource).lower()}" for tile in ordered)


def _edge(value: object) -> tuple[int, int]:
    if (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], int)
        and isinstance(value[1], int)
    ):
        return (value[0], value[1])
    raise TypeError(f"expected a road edge, got {value!r}")
