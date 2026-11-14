from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
import pytest

from catan_coach.domain.rating import (
    BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED,
    DISPLAY_SCALE,
    PENALTY_SD,
    GameObservation,
    HeadToHead,
    RatingFit,
    _interval_after_exclusions,
    _negative_log_posterior,
    _pack,
    _prepare,
    _reduced_gradient,
    _unpack,
    fit_ratings,
)

Strengths = dict[str, float]
SeatEffects = tuple[float, float, float, float]


def _rotation(names: tuple[str, str, str, str], rotation: int) -> tuple[str, str, str, str]:
    return (
        names[rotation % 4],
        names[(rotation + 1) % 4],
        names[(rotation + 2) % 4],
        names[(rotation + 3) % 4],
    )


def _games_from_model(
    names: tuple[str, str, str, str],
    strengths: Strengths,
    seat_effects: SeatEffects,
    n_blocks: int,
    seed: int,
) -> tuple[GameObservation, ...]:
    generator = np.random.default_rng(seed)
    seats = np.array(seat_effects, dtype=np.float64)
    games: list[GameObservation] = []
    for block in range(n_blocks):
        for rotation in range(4):
            entrants = _rotation(names, rotation)
            utility = np.array([strengths[name] for name in entrants], dtype=np.float64)
            utility = utility + seats
            utility -= utility.max()
            probabilities = np.exp(utility)
            probabilities /= probabilities.sum()
            winner = int(generator.choice(4, p=probabilities))
            games.append(GameObservation(block, entrants, winner))
    return tuple(games)


def _by_name(fit: RatingFit) -> dict[str, float]:
    return {row.name: row.rating for row in fit.entrants}


def _pair(fit: RatingFit, entrant: str, opponent: str) -> HeadToHead:
    for row in fit.head_to_head:
        if row.entrant == entrant and row.opponent == opponent:
            return row
    raise AssertionError(f"missing pair {entrant} vs {opponent}")


def test_penalized_gradient_matches_finite_differences() -> None:
    games = (
        GameObservation(0, ("ann", "bea", "cy", "dee"), 0),
        GameObservation(0, ("bea", "cy", "dee", "ann"), 1),
        GameObservation(1, ("cy", "dee", "ann", "bea"), "ann"),
        GameObservation(1, ("dee", "ann", "bea", "cy"), 3),
        GameObservation(2, ("ann", "cy", "bea", "dee"), "bea"),
    )
    prepared = _prepare(games)
    precision = 1.0 / (PENALTY_SD * PENALTY_SD)
    theta = np.array([0.3, -0.2, 0.05, 0.4, -0.1, 0.2], dtype=np.float64)
    weights = np.ones(prepared.entrants.shape[0], dtype=np.float64)
    analytic = _reduced_gradient(prepared, weights, theta, precision)
    numeric = np.empty_like(theta)
    step = 1e-6
    for index in range(theta.shape[0]):
        direction = np.zeros_like(theta)
        direction[index] = step
        higher_r, higher_s = _unpack(theta + direction, len(prepared.names))
        lower_r, lower_s = _unpack(theta - direction, len(prepared.names))
        numeric[index] = (
            _negative_log_posterior(prepared, weights, higher_r, higher_s, precision)
            - _negative_log_posterior(prepared, weights, lower_r, lower_s, precision)
        ) / (2 * step)

    assert analytic == pytest.approx(numeric, abs=1e-6)


def test_fit_is_a_stationary_point_of_the_penalized_objective() -> None:
    names = ("ann", "bea", "cy", "dee")
    games = _games_from_model(
        names,
        {"ann": 0.8, "bea": 0.2, "cy": -0.2, "dee": -0.8},
        (0.0, 0.0, 0.0, 0.0),
        n_blocks=12,
        seed=3,
    )
    fit = fit_ratings(games, n_replicates=8, seed=1)
    prepared = _prepare(games)
    ratings = np.array([_by_name(fit)[name] for name in prepared.names], dtype=np.float64)
    seats = np.array([row.effect for row in fit.seat_effects], dtype=np.float64)
    gradient = _reduced_gradient(
        prepared,
        np.ones(prepared.entrants.shape[0], dtype=np.float64),
        _pack(ratings, seats),
        1.0 / (PENALTY_SD * PENALTY_SD),
    )

    assert float(np.linalg.norm(gradient, ord=np.inf)) < 1e-7
    assert sum(row.rating for row in fit.entrants) == pytest.approx(0.0, abs=1e-8)
    assert sum(row.effect for row in fit.seat_effects) == pytest.approx(0.0, abs=1e-8)


def test_known_strengths_are_recovered_in_order_and_covered() -> None:
    names = ("ann", "bea", "cy", "dee")
    strengths = {"ann": 1.2, "bea": 0.4, "cy": -0.4, "dee": -1.2}
    games = _games_from_model(names, strengths, (0.0, 0.0, 0.0, 0.0), n_blocks=180, seed=1)
    fit = fit_ratings(games, n_replicates=100, seed=0)

    assert [row.name for row in fit.entrants] == ["ann", "bea", "cy", "dee"]
    for row in fit.entrants:
        assert row.interval.lower <= strengths[row.name] <= row.interval.upper
        assert row.display == pytest.approx(row.rating * DISPLAY_SCALE)
        assert row.expected_win_rate == pytest.approx(
            math.exp(row.rating) / (math.exp(row.rating) + 3.0)
        )
        assert row.interval.lower <= row.interval.upper


def test_equal_strengths_have_overlapping_intervals() -> None:
    names = ("ann", "bea", "cy", "dee")
    strengths = {"ann": 0.0, "bea": 0.0, "cy": 0.0, "dee": 0.0}
    games = _games_from_model(names, strengths, (0.0, 0.0, 0.0, 0.0), n_blocks=200, seed=5)
    fit = fit_ratings(games, n_replicates=80, seed=2)

    intervals = [row.interval for row in fit.entrants]
    for left in intervals:
        for right in intervals:
            assert left.lower <= right.upper
            assert right.lower <= left.upper


def test_seat_effects_are_recovered() -> None:
    names = ("ann", "bea", "cy", "dee")
    strengths = {"ann": 0.0, "bea": 0.0, "cy": 0.0, "dee": 0.0}
    seat_effects = (1.1, 0.4, -0.4, -1.1)
    games = _games_from_model(names, strengths, seat_effects, n_blocks=160, seed=9)
    fit = fit_ratings(games, n_replicates=80, seed=0)

    estimated = [row.effect for row in fit.seat_effects]
    assert estimated[0] > estimated[1] > estimated[2] > estimated[3]
    assert [row.seat for row in fit.seat_effects] == [0, 1, 2, 3]
    for row, truth in zip(fit.seat_effects, seat_effects, strict=True):
        assert row.interval.lower <= truth <= row.interval.upper
    assert sum(estimated) == pytest.approx(0.0, abs=1e-8)


def test_permuting_observation_order_does_not_change_the_fit() -> None:
    names = ("ann", "bea", "cy", "dee")
    games = _games_from_model(
        names,
        {"ann": 0.7, "bea": 0.2, "cy": -0.1, "dee": -0.8},
        (0.3, 0.0, -0.1, -0.2),
        n_blocks=20,
        seed=6,
    )
    original = fit_ratings(games, n_replicates=15, seed=4)
    generator = np.random.default_rng(1)
    order = generator.permutation(len(games))
    shuffled = tuple(games[int(index)] for index in order)
    reversed_games = tuple(reversed(games))

    assert _same_fit(original, fit_ratings(shuffled, n_replicates=15, seed=4))
    assert _same_fit(original, fit_ratings(reversed_games, n_replicates=15, seed=4))


def test_winner_name_matches_winner_seat() -> None:
    names = ("ann", "bea", "cy", "dee")
    by_seat = _games_from_model(
        names,
        {"ann": 0.5, "bea": 0.1, "cy": -0.1, "dee": -0.5},
        (0.2, 0.0, 0.0, -0.2),
        n_blocks=8,
        seed=2,
    )
    by_name = tuple(
        GameObservation(game.block_id, game.entrants, game.entrants[game.winner])
        for game in by_seat
        if isinstance(game.winner, int)
    )

    assert _same_fit(
        fit_ratings(by_seat, n_replicates=6, seed=3),
        fit_ratings(by_name, n_replicates=6, seed=3),
    )


def test_zero_win_entrant_stays_finite_in_every_replicate() -> None:
    names = ("alpha", "bravo", "charlie", "random")
    generator = np.random.default_rng(0)
    games: list[GameObservation] = []
    for block in range(24):
        for rotation in range(4):
            entrants = _rotation(names, rotation)
            choices = [seat for seat, name in enumerate(entrants) if name != "random"]
            winner = int(generator.choice(choices))
            games.append(GameObservation(block, entrants, winner))
    fit = fit_ratings(tuple(games), n_replicates=30, seed=0, collect_replicates=True)

    random_rating = _by_name(fit)["random"]
    assert math.isfinite(random_rating)
    assert random_rating < min(rating for name, rating in _by_name(fit).items() if name != "random")
    assert fit.rating_replicates is not None
    index = next(position for position, row in enumerate(fit.entrants) if row.name == "random")
    assert fit.rating_replicates
    for draw in fit.rating_replicates:
        assert math.isfinite(draw[index])
        assert sum(draw) == pytest.approx(0.0, abs=1e-8)
    assert fit.seat_effect_replicates is not None
    for draw in fit.seat_effect_replicates:
        assert all(math.isfinite(value) for value in draw)
        assert sum(draw) == pytest.approx(0.0, abs=1e-8)


def test_tighter_penalty_shrinks_a_zero_win_rating_toward_zero() -> None:
    games = _zero_win_games()
    loose = fit_ratings(games, n_replicates=4, seed=0, penalty_sd=4.0)
    tight = fit_ratings(games, n_replicates=4, seed=0, penalty_sd=1.0)

    assert _by_name(loose)["random"] < _by_name(tight)["random"] < 0.0
    assert math.isfinite(_by_name(tight)["random"])
    assert tight.penalty_sd == 1.0
    assert loose.penalty_sd == 4.0


def test_head_to_head_zero_denominator_and_exclusion_rule() -> None:
    never = _pair(
        fit_ratings(_disjoint_tables(), n_replicates=20, seed=0),
        "ann",
        "bea",
    )
    assert never.tables == 0
    assert never.wins == 0
    assert never.share is None
    assert never.interval is None
    assert never.replicates_excluded == 20

    rare = fit_ratings(_one_decisive_block(), n_replicates=100, seed=0)
    ann_bea = _pair(rare, "ann", "bea")
    assert ann_bea.tables == 1
    assert ann_bea.wins == 1
    assert ann_bea.share == pytest.approx(1.0)
    assert ann_bea.interval is None
    assert ann_bea.replicates_excluded > 1
    assert ann_bea.replicates_excluded < 100

    certain = fit_ratings(_always_ann_beats_bea(), n_replicates=25, seed=1)
    certain_pair = _pair(certain, "ann", "bea")
    assert certain_pair.share == pytest.approx(1.0)
    assert certain_pair.replicates_excluded == 0
    assert certain_pair.interval is not None
    assert certain_pair.interval.lower == pytest.approx(1.0)
    assert certain_pair.interval.upper == pytest.approx(1.0)
    reverse = _pair(certain, "bea", "ann")
    assert reverse.share == pytest.approx(0.0)
    assert certain_pair.share is not None and reverse.share is not None
    assert certain_pair.share + reverse.share == pytest.approx(1.0)


def test_interval_is_unavailable_only_when_more_than_one_percent_are_excluded() -> None:
    kept = np.full(99, 0.25, dtype=np.float64)
    wild = np.array([999.0], dtype=np.float64)
    samples = np.concatenate((kept, wild))
    counted = np.concatenate((np.ones(99, dtype=np.bool_), np.zeros(1, dtype=np.bool_)))
    interval, excluded = _interval_after_exclusions(samples, counted)
    assert excluded == 1
    assert interval is not None
    assert interval.lower == pytest.approx(0.25)
    assert interval.upper == pytest.approx(0.25)

    too_many = np.concatenate((np.ones(98, dtype=np.bool_), np.zeros(2, dtype=np.bool_)))
    missing, missing_count = _interval_after_exclusions(np.zeros(100), too_many)
    assert missing is None
    assert missing_count == 2

    none_counted = np.zeros(8, dtype=np.bool_)
    empty, empty_count = _interval_after_exclusions(np.ones(8), none_counted)
    assert empty is None
    assert empty_count == 8


def test_block_bootstrap_keeps_a_blocks_games_together() -> None:
    """Two blocks have three bootstrap compositions, not one per game."""

    ann_block = _won_by("ann", 0)
    bea_block = _won_by("bea", 1)
    fit = fit_ratings((*ann_block, *bea_block), n_replicates=60, seed=0, collect_replicates=True)

    assert fit.rating_replicates is not None
    unique = {tuple(round(value, 6) for value in draw) for draw in fit.rating_replicates}
    assert len(unique) == 3
    assert fit.n_replicates == 60
    assert fit.seed == 0
    assert fit.penalty_sd == PENALTY_SD


def test_reported_defaults_match_the_declared_penalty_and_bootstrap() -> None:
    assert BOOTSTRAP_REPLICATES == 10_000
    assert BOOTSTRAP_SEED == 0
    assert PENALTY_SD == 2.0
    assert pytest.approx(400.0 / math.log(10.0)) == DISPLAY_SCALE
    games = (GameObservation(0, ("ann", "bea", "cy", "dee"), 0),)
    fit = fit_ratings(games, n_replicates=5, seed=7)
    assert fit.n_replicates == 5
    assert fit.seed == 7
    assert fit.penalty_sd == 2.0
    assert len(fit.head_to_head) == 12
    assert fit.rating_replicates is None


@pytest.mark.parametrize(
    ("game", "match"),
    [
        (lambda: GameObservation(True, ("ann", "bea", "cy", "dee"), 0), "block_id"),
        (lambda: GameObservation(0, ("ann", "ann", "cy", "dee"), 0), "distinct"),
        (lambda: GameObservation(0, ("ann", "bea", "cy", "dee"), 4), "winner seat"),
        (lambda: GameObservation(0, ("ann", "bea", "cy", "dee"), "zoe"), "not seated"),
        (lambda: GameObservation(0, ("ann", "bea", "cy", ""), 0), "Entrant name"),
        (lambda: GameObservation(0, ("ann", "bea", "cy", "dee"), True), "winner"),
    ],
)
def test_observations_reject_bad_tables(game: Callable[[], GameObservation], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        game()


def test_fit_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="at least one"):
        fit_ratings(())


def _same_fit(left: RatingFit, right: RatingFit) -> bool:
    assert [row.name for row in left.entrants] == [row.name for row in right.entrants]
    for lhs, rhs in zip(left.entrants, right.entrants, strict=True):
        assert lhs.rating == pytest.approx(rhs.rating, abs=1e-10)
        assert lhs.interval.lower == pytest.approx(rhs.interval.lower, abs=1e-10)
        assert lhs.interval.upper == pytest.approx(rhs.interval.upper, abs=1e-10)
        assert lhs.expected_win_rate == pytest.approx(rhs.expected_win_rate, abs=1e-10)
    for left_seat, right_seat in zip(left.seat_effects, right.seat_effects, strict=True):
        assert left_seat.effect == pytest.approx(right_seat.effect, abs=1e-10)
        assert left_seat.interval.lower == pytest.approx(right_seat.interval.lower, abs=1e-10)
        assert left_seat.interval.upper == pytest.approx(right_seat.interval.upper, abs=1e-10)
    assert len(left.head_to_head) == len(right.head_to_head)
    for left_pair, right_pair in zip(left.head_to_head, right.head_to_head, strict=True):
        assert (left_pair.entrant, left_pair.opponent) == (right_pair.entrant, right_pair.opponent)
        if left_pair.share is None:
            assert right_pair.share is None
        else:
            assert right_pair.share is not None
            assert left_pair.share == pytest.approx(right_pair.share, abs=1e-10)
        if left_pair.interval is None or right_pair.interval is None:
            assert left_pair.interval is None and right_pair.interval is None
        else:
            assert left_pair.interval.lower == pytest.approx(right_pair.interval.lower, abs=1e-10)
            assert left_pair.interval.upper == pytest.approx(right_pair.interval.upper, abs=1e-10)
    return True


def _zero_win_games() -> tuple[GameObservation, ...]:
    names = ("alpha", "bravo", "charlie", "random")
    generator = np.random.default_rng(1)
    games: list[GameObservation] = []
    for block in range(16):
        for rotation in range(4):
            entrants = _rotation(names, rotation)
            choices = [seat for seat, name in enumerate(entrants) if name != "random"]
            games.append(GameObservation(block, entrants, int(generator.choice(choices))))
    return tuple(games)


def _disjoint_tables() -> tuple[GameObservation, ...]:
    ann_table = ("ann", "cy", "dee", "eve")
    bea_table = ("bea", "cy", "dee", "eve")
    return (
        *_won_by_fixed(ann_table, "ann", "ann-table"),
        *_won_by_fixed(bea_table, "bea", "bea-table"),
    )


def _one_decisive_block() -> tuple[GameObservation, ...]:
    entrants = ("ann", "bea", "cy", "dee")
    games = [GameObservation(block, entrants, "cy") for block in range(9)]
    games.append(GameObservation(9, entrants, "ann"))
    return tuple(games)


def _always_ann_beats_bea() -> tuple[GameObservation, ...]:
    return tuple(GameObservation(block, ("ann", "bea", "cy", "dee"), "ann") for block in range(6))


def _won_by(
    winner: str, block_id: int
) -> tuple[GameObservation, GameObservation, GameObservation, GameObservation]:
    names = ("ann", "bea", "cy", "dee")
    return (
        GameObservation(block_id, _rotation(names, 0), winner),
        GameObservation(block_id, _rotation(names, 1), winner),
        GameObservation(block_id, _rotation(names, 2), winner),
        GameObservation(block_id, _rotation(names, 3), winner),
    )


def _won_by_fixed(
    entrants: tuple[str, str, str, str], winner: str, block_id: str
) -> tuple[GameObservation, ...]:
    games: list[GameObservation] = []
    for rotation in range(4):
        seated = _rotation(entrants, rotation)
        games.append(GameObservation(block_id, seated, winner))
    return tuple(games)
