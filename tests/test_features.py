"""Public production columns follow the catanatron sample, in a fixed order."""

from __future__ import annotations

import numpy as np
import pytest

pytestmark = pytest.mark.engine

catanatron = pytest.importorskip("catanatron")

from catanatron import Color, Game  # noqa: E402
from catanatron.features import (  # noqa: E402
    build_production_features,
    create_sample_vector,
    expansion_features,
    get_feature_ordering,
    port_distance_features,
    reachability_features,
)
from catanatron.players.value import ValueFunctionPlayer  # noqa: E402

from catan_coach.engine import features as features_module  # noqa: E402
from catan_coach.engine.board import corpus_map  # noqa: E402
from catan_coach.engine.features import (  # noqa: E402
    base_width,
    feature_names,
    feature_vector,
    phase_indices,
)

NUM_PLAYERS = 4
PERSPECTIVE = Color.RED
PUBLIC_WIDTH = 188
_TICKS = 150


@pytest.fixture(scope="module")
def mid_game() -> Game:
    colors = (Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE)
    game = Game(
        [ValueFunctionPlayer(color) for color in colors],
        seed=5,
        catan_map=corpus_map(5),
    )
    for _ in range(_TICKS):
        assert game.winning_color() is None
        game.play_tick()
    return game


def _public_samples(game: Game, color: Color) -> tuple[dict[str, object], ...]:
    return (
        dict(build_production_features(True)(game, color)),
        dict(reachability_features(game, color, 2)),
        dict(expansion_features(game, color)),
        dict(port_distance_features(game, color)),
    )


def _number(value: object) -> float:
    if isinstance(value, bool | int | float):
        return float(value)
    raise AssertionError(f"expected a number, got {type(value).__name__}")


def test_four_players_add_188_public_columns() -> None:
    assert base_width(NUM_PLAYERS) == len(get_feature_ordering(NUM_PLAYERS))
    assert len(feature_names(NUM_PLAYERS)) == base_width(NUM_PLAYERS) + PUBLIC_WIDTH


def test_the_base_prefix_matches_create_sample_vector(mid_game: Game) -> None:
    vector = feature_vector(mid_game, PERSPECTIVE)
    base = np.asarray(create_sample_vector(mid_game, PERSPECTIVE), dtype=np.float64)
    width = base_width(NUM_PLAYERS)

    assert vector.dtype == np.float64
    assert base.shape == (width,)
    assert np.array_equal(vector[:width], base)
    assert vector.shape == (width + PUBLIC_WIDTH,)


def test_names_match_the_vector_and_stay_unique(mid_game: Game) -> None:
    names = feature_names(NUM_PLAYERS)
    vector = feature_vector(mid_game, PERSPECTIVE)

    assert len(names) == vector.shape[0]
    assert len(set(names)) == len(names)
    assert names[: base_width(NUM_PLAYERS)] == tuple(get_feature_ordering(NUM_PLAYERS))


def test_public_columns_follow_the_extractor_order(mid_game: Game) -> None:
    samples = _public_samples(mid_game, PERSPECTIVE)
    assert tuple(len(sample) for sample in samples) == (20, 60, 60, 48)

    width = base_width(NUM_PLAYERS)
    names = feature_names(NUM_PLAYERS)
    assert names[width:] == tuple(key for sample in samples for key in sample)

    expected = np.asarray(
        [_number(value) for sample in samples for value in sample.values()],
        dtype=np.float64,
    )
    assert np.array_equal(feature_vector(mid_game, PERSPECTIVE)[width:], expected)


def test_phase_indices_point_at_turn_position_features() -> None:
    expected = (
        "IS_DISCARDING",
        "IS_MOVING_ROBBER",
        *(f"P{seat}_HAS_ROLLED" for seat in range(NUM_PLAYERS)),
        "P0_HAS_PLAYED_DEVELOPMENT_CARD_IN_TURN",
    )
    names = feature_names(NUM_PLAYERS)
    ordering = tuple(get_feature_ordering(NUM_PLAYERS))
    indices = phase_indices(NUM_PLAYERS)

    assert tuple(names[index] for index in indices) == expected
    assert indices == tuple(ordering.index(name) for name in expected)

    two_player = (
        "IS_DISCARDING",
        "IS_MOVING_ROBBER",
        "P0_HAS_ROLLED",
        "P1_HAS_ROLLED",
        "P0_HAS_PLAYED_DEVELOPMENT_CARD_IN_TURN",
    )
    two_names = feature_names(2)
    assert tuple(two_names[index] for index in phase_indices(2)) == two_player


def test_two_calls_on_the_same_game_match(mid_game: Game) -> None:
    assert np.array_equal(
        feature_vector(mid_game, PERSPECTIVE),
        feature_vector(mid_game, PERSPECTIVE),
    )


def test_a_missing_public_key_raises(mid_game: Game, monkeypatch: pytest.MonkeyPatch) -> None:
    def drop_first_key(game: Game, color: Color) -> dict[str, object]:
        sample = dict(build_production_features(True)(game, color))
        del sample[next(iter(sample))]
        return sample

    monkeypatch.setattr(
        features_module,
        "_EXTRACTORS",
        (drop_first_key, *features_module._EXTRACTORS[1:]),
    )
    with pytest.raises(KeyError):
        feature_vector(mid_game, PERSPECTIVE)
