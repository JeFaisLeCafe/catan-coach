"""Adapter over catanatron's feature extraction.

The only place that knows how a Position becomes numbers. Keeping the name to
index resolution here is what lets the models stay pure.

The vector is a legitimate player-perspective Observation: opponents expose
only played dev cards and hand *counts*, never which cards they hold.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

import numpy as np
from catanatron import Color, Game
from catanatron.features import create_sample_vector, get_feature_ordering

from catan_coach.domain.prediction import FeatureMatrix


@lru_cache(maxsize=8)
def feature_names(num_players: int) -> tuple[str, ...]:
    return tuple(get_feature_ordering(num_players))


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


def feature_vector(game: Game, color: Color) -> np.ndarray:
    return np.asarray(create_sample_vector(game, color), dtype=np.float64)


def feature_matrix(games: Sequence[tuple[Game, Color]]) -> FeatureMatrix:
    if not games:
        raise ValueError("need at least one (game, color) pair")
    return np.vstack([feature_vector(game, color) for game, color in games])
