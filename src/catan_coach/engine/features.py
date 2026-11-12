"""Adapter over catanatron's feature extraction.

The only place that knows how a Position becomes numbers. Keeping the name to
index resolution here is what lets the models stay pure.

The vector is a legitimate player-perspective Observation: opponents expose
only played dev cards and hand *counts*, never which cards they hold. Public
production, reachability, expansion, and port distance follow that prefix.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import lru_cache
from typing import cast

import numpy as np
from catanatron import Color, Game
from catanatron.features import (
    build_production_features,
    create_sample_vector,
    expansion_features,
    get_feature_ordering,
    port_distance_features,
    reachability_features,
)
from catanatron.models.player import SimplePlayer

from catan_coach.domain.prediction import FeatureMatrix

# Where the turn is, not who is winning. "{i}" expands to each seat.
PHASE_FEATURES = (
    "IS_DISCARDING",
    "IS_MOVING_ROBBER",
    "P{i}_HAS_ROLLED",
    "P0_HAS_PLAYED_DEVELOPMENT_CARD_IN_TURN",
)

_PROBE_COLORS = (Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE)
_EFFECTIVE_PRODUCTION = build_production_features(True)
_Extractor = Callable[[Game, Color], Mapping[str, object]]


def _production(game: Game, color: Color) -> Mapping[str, object]:
    return cast(Mapping[str, object], _EFFECTIVE_PRODUCTION(game, color))


def _reachability(game: Game, color: Color) -> Mapping[str, object]:
    return cast(Mapping[str, object], reachability_features(game, color, 2))


_EXTRACTORS: tuple[_Extractor, ...] = (
    _production,
    _reachability,
    expansion_features,
    port_distance_features,
)


@lru_cache(maxsize=8)
def feature_names(num_players: int) -> tuple[str, ...]:
    public = tuple(name for group in _public_name_groups(num_players) for name in group)
    return tuple(get_feature_ordering(num_players)) + public


def base_width(num_players: int) -> int:
    return len(get_feature_ordering(num_players))


def index_of(name: str, num_players: int) -> int:
    try:
        return feature_names(num_players).index(name)
    except ValueError as error:
        raise KeyError(f"no feature named {name!r} for {num_players} players") from error


def indices_of(names: Sequence[str], num_players: int) -> tuple[int, ...]:
    return tuple(index_of(name, num_players) for name in names)


def public_vp_indices(num_players: int) -> tuple[int, ...]:
    """Perspective player first, then opponents."""
    return indices_of([f"P{i}_PUBLIC_VPS" for i in range(num_players)], num_players)


def phase_indices(num_players: int) -> tuple[int, ...]:
    """Columns that say where the turn is, not who is winning."""
    return indices_of(_phase_names(num_players), num_players)


def feature_vector(game: Game, color: Color) -> np.ndarray:
    base = np.asarray(create_sample_vector(game, color), dtype=np.float64)
    public = np.asarray(_public_values(game, color), dtype=np.float64)
    return np.concatenate((base, public))


def feature_matrix(games: Sequence[tuple[Game, Color]]) -> FeatureMatrix:
    if not games:
        raise ValueError("need at least one (game, color) pair")
    return np.vstack([feature_vector(game, color) for game, color in games])


@lru_cache(maxsize=8)
def _public_name_groups(num_players: int) -> tuple[tuple[str, ...], ...]:
    """Key order for one player count, taken from a fresh game and then fixed."""
    players = [SimplePlayer(color) for color in _PROBE_COLORS[:num_players]]
    game = Game(players)
    color = players[0].color
    return tuple(tuple(extractor(game, color)) for extractor in _EXTRACTORS)


def _phase_names(num_players: int) -> tuple[str, ...]:
    names: list[str] = []
    for template in PHASE_FEATURES:
        if "{i}" in template:
            names.extend(template.format(i=seat) for seat in range(num_players))
        else:
            names.append(template)
    return tuple(names)


def _public_values(game: Game, color: Color) -> list[float]:
    values: list[float] = []
    groups = _public_name_groups(len(game.state.colors))
    for extractor, keys in zip(_EXTRACTORS, groups, strict=True):
        sample = extractor(game, color)
        for key in keys:
            values.append(_as_float(sample[key]))
    return values


def _as_float(value: object) -> float:
    # bool is an int, so it has to be mapped before the numeric branch.
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return float(value)
    raise TypeError(f"public feature value must be numeric, got {type(value).__name__}")
