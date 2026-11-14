"""Penalized Plackett-Luce ratings for an Arena.

Each completed game is one observation: the winning Entrant out of the four
at the table. Strength and Seat enter as

    P(i wins) = exp(r_i + s_seat(i)) / sum_j exp(r_j + s_seat(j)).

Ratings sum to zero and Seat effects sum to zero. Those two sums are free
directions of the likelihood (a constant added to every rating, or to every
Seat effect, cancels in the softmax), so the fit never estimates them.
Parameters are the first n-1 centered ratings and the first three centered
Seat effects; the last rating and the last Seat effect are minus the sum of
the others. The Gaussian penalty is the quadratic
``(1 / (2 sigma^2)) * (sum r_i^2 + sum s_k^2)`` on that centered vector,
including the two dependent components: the same penalty as ``N(0, sigma^2)``
on every reported rating and every Seat effect, not a penalty on an
unidentified shift.

Intervals are 95% percentile intervals from a block bootstrap: block ids are
resampled with replacement, and every game that shares a block id stays
together. Replicate fits start from the full-sample estimate.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
from numpy.typing import NDArray

PENALTY_SD = 2.0
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 0
DISPLAY_SCALE = 400.0 / math.log(10.0)
N_SEATS = 4

_GRADIENT_TOLERANCE = 1e-8
_MAX_NEWTON_STEPS = 50
# More than 1% of replicates: excluded * 100 > n_replicates.
_EXCLUSION_PERCENT = 100


@dataclass(frozen=True, slots=True)
class GameObservation:
    """One completed game: four Entrants by Seat, and who won.

    ``entrants`` is indexed by Seat, from 0 through 3. ``winner`` is that
    Seat, or the winning Entrant's name. ``block_id`` groups games that share
    a board; the bootstrap resamples those groups, not single games.
    """

    block_id: int | str
    entrants: tuple[str, str, str, str]
    winner: int | str

    def __post_init__(self) -> None:
        if isinstance(self.block_id, bool) or not isinstance(self.block_id, int | str):
            raise ValueError("block_id must be an int or a str")
        for seat, name in enumerate(self.entrants):
            if not isinstance(name, str) or name == "":
                raise ValueError(f"seat {seat} needs an Entrant name")
        if len(set(self.entrants)) != N_SEATS:
            raise ValueError("the four Entrants at a table are distinct")
        if isinstance(self.winner, bool) or not isinstance(self.winner, int | str):
            raise ValueError("winner must be a seat 0..3 or an Entrant name")
        if isinstance(self.winner, int):
            if self.winner not in (0, 1, 2, 3):
                raise ValueError("winner seat must be 0, 1, 2, or 3")
        elif self.winner not in self.entrants:
            raise ValueError(f"winner {self.winner} is not seated at this table")


@dataclass(frozen=True, slots=True)
class PercentileInterval:
    lower: float
    upper: float


@dataclass(frozen=True, slots=True)
class EntrantRating:
    """One Entrant's sum-to-zero rating, display scale, and 95% interval.

    ``display`` is ``rating * 400 / ln(10)``. ``expected_win_rate`` is the
    chance of winning against three average Entrants (rating 0, average Seat):
    ``exp(rating) / (exp(rating) + 3)``. ``interval`` is on the same scale as
    ``rating``; multiply by ``DISPLAY_SCALE`` for the display scale. Percentiles
    commute with that positive scale factor.
    """

    name: str
    rating: float
    display: float
    expected_win_rate: float
    interval: PercentileInterval


@dataclass(frozen=True, slots=True)
class SeatEffect:
    seat: int
    effect: float
    interval: PercentileInterval


@dataclass(frozen=True, slots=True)
class HeadToHead:
    """Share of decisive shared tables won by ``entrant``.

    A table counts when both Entrants sat and one of them won. ``share`` is
    ``None`` when that count is zero. The interval drops bootstrap replicates
    with a zero count; if more than 1% of replicates are dropped, ``interval``
    is ``None`` and ``replicates_excluded`` still records how many.
    """

    entrant: str
    opponent: str
    wins: int
    tables: int
    share: float | None
    interval: PercentileInterval | None
    replicates_excluded: int


@dataclass(frozen=True, slots=True)
class RatingFit:
    """Penalized ratings, Seat effects, and head-to-head shares.

    ``entrants`` is ordered by descending rating, then by name.
    ``rating_replicates[draw][i]`` is the rating of ``entrants[i]`` on that
    bootstrap draw, and only present when requested. Seat replicates follow
    seat 0..3.
    """

    entrants: tuple[EntrantRating, ...]
    seat_effects: tuple[SeatEffect, ...]
    head_to_head: tuple[HeadToHead, ...]
    penalty_sd: float
    n_replicates: int
    seed: int
    rating_replicates: tuple[tuple[float, ...], ...] | None = None
    seat_effect_replicates: tuple[tuple[float, ...], ...] | None = None


class _Design(NamedTuple):
    size: int
    rating_rating: NDArray[np.intp]
    rating_seat: NDArray[np.intp]
    seat_rating: NDArray[np.intp]
    entrant_index: NDArray[np.intp]


class _Prepared(NamedTuple):
    names: tuple[str, ...]
    entrants: NDArray[np.intp]
    winners: NDArray[np.intp]
    blocks: NDArray[np.intp]
    n_blocks: int
    design: _Design
    jacobian: NDArray[np.float64]


def fit_ratings(
    games: Sequence[GameObservation],
    *,
    n_replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
    penalty_sd: float = PENALTY_SD,
    collect_replicates: bool = False,
) -> RatingFit:
    """Fit sum-to-zero ratings and Seat effects, with a block bootstrap.

    Blocks are resampled with replacement from ``seed``. Every game with the
    same ``block_id`` is kept together, so the four same-seed rotations of a
    league block stay in one draw. Replicates are warm-started from the
    full-sample fit.
    """

    _check_fit_arguments(n_replicates, seed, penalty_sd)
    prepared = _prepare(games)
    precision = 1.0 / (penalty_sd * penalty_sd)
    ones = np.ones(prepared.entrants.shape[0], dtype=np.float64)
    origin_r = np.zeros(len(prepared.names), dtype=np.float64)
    origin_s = np.zeros(N_SEATS, dtype=np.float64)
    ratings, seats = _fit(prepared, ones, precision, origin_r, origin_s)
    counts = _block_counts(prepared.n_blocks, n_replicates, seed)
    rating_draws, seat_draws = _bootstrap(prepared, counts, precision, ratings, seats)
    return _assemble(
        prepared,
        ratings,
        seats,
        rating_draws,
        seat_draws,
        counts,
        penalty_sd=penalty_sd,
        n_replicates=n_replicates,
        seed=seed,
        collect_replicates=collect_replicates,
    )


def _check_fit_arguments(n_replicates: int, seed: int, penalty_sd: float) -> None:
    if isinstance(n_replicates, bool) or not isinstance(n_replicates, int) or n_replicates < 1:
        raise ValueError("n_replicates must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if isinstance(penalty_sd, bool) or not isinstance(penalty_sd, int | float):
        raise ValueError("penalty_sd must be a positive number")
    if not math.isfinite(float(penalty_sd)) or float(penalty_sd) <= 0.0:
        raise ValueError("penalty_sd must be a positive number")


def _prepare(games: Sequence[GameObservation]) -> _Prepared:
    if len(games) == 0:
        raise ValueError("rating fit needs at least one completed game")
    for game in games:
        if not isinstance(game, GameObservation):
            raise TypeError("games must be GameObservation values")
    names = tuple(sorted({name for game in games for name in game.entrants}))
    name_index = {name: index for index, name in enumerate(names)}
    block_ids = tuple(sorted({game.block_id for game in games}, key=_block_sort_key))
    block_index = {block_id: index for index, block_id in enumerate(block_ids)}
    ordered = sorted(
        games,
        key=lambda game: (
            _block_sort_key(game.block_id),
            game.entrants,
            _winner_seat(game),
        ),
    )
    n_games = len(ordered)
    entrants = np.empty((n_games, N_SEATS), dtype=np.intp)
    winners = np.empty(n_games, dtype=np.intp)
    blocks = np.empty(n_games, dtype=np.intp)
    for row, game in enumerate(ordered):
        entrants[row] = [name_index[name] for name in game.entrants]
        winners[row] = _winner_seat(game)
        blocks[row] = block_index[game.block_id]
    n_entrants = len(names)
    return _Prepared(
        names,
        entrants,
        winners,
        blocks,
        len(block_ids),
        _design_codes(entrants, n_entrants),
        _sum_to_zero_jacobian(n_entrants),
    )


def _block_sort_key(block_id: int | str) -> tuple[int, int | str]:
    if isinstance(block_id, int):
        return (0, block_id)
    return (1, block_id)


def _winner_seat(game: GameObservation) -> int:
    winner = game.winner
    if isinstance(winner, int):
        return winner
    return game.entrants.index(winner)


def _design_codes(entrants: NDArray[np.intp], n_entrants: int) -> _Design:
    size = n_entrants + N_SEATS
    seat = np.arange(N_SEATS, dtype=np.intp)[np.newaxis, np.newaxis, :]
    rating_rating = (entrants[:, :, np.newaxis] * size + entrants[:, np.newaxis, :]).ravel()
    rating_seat = (entrants[:, :, np.newaxis] * size + (n_entrants + seat)).ravel()
    seat_rating = ((n_entrants + seat) * size + entrants[:, :, np.newaxis]).ravel()
    return _Design(size, rating_rating, rating_seat, seat_rating, entrants.ravel())


def _sum_to_zero_jacobian(n_entrants: int) -> NDArray[np.float64]:
    n_free = (n_entrants - 1) + (N_SEATS - 1)
    jacobian = np.zeros((n_entrants + N_SEATS, n_free), dtype=np.float64)
    for index in range(n_entrants - 1):
        jacobian[index, index] = 1.0
        jacobian[n_entrants - 1, index] = -1.0
    seat_column = n_entrants - 1
    for seat in range(N_SEATS - 1):
        jacobian[n_entrants + seat, seat_column + seat] = 1.0
        jacobian[n_entrants + N_SEATS - 1, seat_column + seat] = -1.0
    return jacobian


def _pack(ratings: NDArray[np.float64], seats: NDArray[np.float64]) -> NDArray[np.float64]:
    centered_ratings = ratings - ratings.mean()
    centered_seats = seats - seats.mean()
    return np.concatenate((centered_ratings[:-1], centered_seats[:-1]))


def _unpack(
    theta: NDArray[np.float64], n_entrants: int
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    ratings = np.empty(n_entrants, dtype=np.float64)
    ratings[:-1] = theta[: n_entrants - 1]
    ratings[-1] = -float(ratings[:-1].sum())
    seats = np.empty(N_SEATS, dtype=np.float64)
    seats[:-1] = theta[n_entrants - 1 :]
    seats[-1] = -float(seats[:-1].sum())
    return ratings, seats


def _fit(
    prepared: _Prepared,
    weights: NDArray[np.float64],
    penalty_precision: float,
    warm_ratings: NDArray[np.float64],
    warm_seats: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    n_entrants = warm_ratings.shape[0]
    theta = _pack(warm_ratings, warm_seats)
    gradient_norm = math.inf
    for _ in range(_MAX_NEWTON_STEPS):
        ratings, seats = _unpack(theta, n_entrants)
        gradient, hessian = _gradient_and_hessian(
            prepared, weights, ratings, seats, penalty_precision
        )
        reduced_gradient = prepared.jacobian.T @ gradient
        gradient_norm = float(np.linalg.norm(reduced_gradient, ord=np.inf))
        if gradient_norm < _GRADIENT_TOLERANCE:
            return ratings, seats
        reduced_hessian = prepared.jacobian.T @ hessian @ prepared.jacobian
        try:
            step = np.linalg.solve(reduced_hessian, reduced_gradient)
        except np.linalg.LinAlgError as exc:
            raise RuntimeError("rating Hessian is singular") from exc
        theta = theta - step
    ratings, seats = _unpack(theta, n_entrants)
    gradient, _hessian = _gradient_and_hessian(prepared, weights, ratings, seats, penalty_precision)
    gradient_norm = float(np.linalg.norm(prepared.jacobian.T @ gradient, ord=np.inf))
    if gradient_norm < _GRADIENT_TOLERANCE:
        return ratings, seats
    raise RuntimeError(f"rating fit did not converge (gradient {gradient_norm:.3e})")


def _gradient_and_hessian(
    prepared: _Prepared,
    weights: NDArray[np.float64],
    ratings: NDArray[np.float64],
    seats: NDArray[np.float64],
    penalty_precision: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    entrants = prepared.entrants
    n_games = entrants.shape[0]
    n_entrants = ratings.shape[0]
    utilities = ratings[entrants] + seats
    shifted = utilities - utilities.max(axis=1, keepdims=True)
    exp_utilities = np.exp(shifted)
    probabilities = exp_utilities / exp_utilities.sum(axis=1, keepdims=True)

    residual = probabilities.copy()
    game_index = np.arange(n_games)
    residual[game_index, prepared.winners] -= 1.0
    residual *= weights[:, np.newaxis]

    design = prepared.design
    gradient_rating = np.bincount(
        design.entrant_index, residual.ravel(), minlength=n_entrants
    ).astype(np.float64, copy=False)
    gradient_seat = residual.sum(axis=0)
    gradient_rating += penalty_precision * ratings
    gradient_seat += penalty_precision * seats

    curvature = -probabilities[:, :, np.newaxis] * probabilities[:, np.newaxis, :]
    diagonal = np.arange(N_SEATS)
    curvature[:, diagonal, diagonal] += probabilities
    curvature *= weights[:, np.newaxis, np.newaxis]
    flat = curvature.ravel()
    size = design.size
    hessian = np.bincount(design.rating_rating, flat, minlength=size * size).astype(
        np.float64, copy=False
    )
    hessian += np.bincount(design.rating_seat, flat, minlength=size * size)
    hessian += np.bincount(design.seat_rating, flat, minlength=size * size)
    hessian_matrix = hessian.reshape((size, size))
    hessian_matrix[n_entrants:, n_entrants:] += curvature.sum(axis=0)
    hessian_matrix[np.arange(size), np.arange(size)] += penalty_precision
    symmetric = 0.5 * (hessian_matrix + hessian_matrix.T)
    return np.concatenate((gradient_rating, gradient_seat)), symmetric


def _negative_log_posterior(
    prepared: _Prepared,
    weights: NDArray[np.float64],
    ratings: NDArray[np.float64],
    seats: NDArray[np.float64],
    penalty_precision: float,
) -> float:
    utilities = ratings[prepared.entrants] + seats
    peak = utilities.max(axis=1, keepdims=True)
    log_sum = peak.ravel() + np.log(np.exp(utilities - peak).sum(axis=1))
    chosen = utilities[np.arange(prepared.winners.shape[0]), prepared.winners]
    likelihood = -float(np.dot(weights, chosen - log_sum))
    penalty = 0.5 * penalty_precision * (float(ratings @ ratings) + float(seats @ seats))
    return likelihood + penalty


def _reduced_gradient(
    prepared: _Prepared,
    weights: NDArray[np.float64],
    theta: NDArray[np.float64],
    penalty_precision: float,
) -> NDArray[np.float64]:
    ratings, seats = _unpack(theta, len(prepared.names))
    gradient, _hessian = _gradient_and_hessian(prepared, weights, ratings, seats, penalty_precision)
    return prepared.jacobian.T @ gradient


def _block_counts(n_blocks: int, n_replicates: int, seed: int) -> NDArray[np.int64]:
    generator = np.random.Generator(np.random.PCG64(seed))
    drawn = generator.choice(n_blocks, size=(n_replicates, n_blocks), replace=True)
    coded = drawn.astype(np.int64, copy=False)
    coded = coded + np.arange(n_replicates, dtype=np.int64)[:, np.newaxis] * n_blocks
    counts = np.bincount(coded.ravel(), minlength=n_replicates * n_blocks)
    return counts.reshape((n_replicates, n_blocks))


def _bootstrap(
    prepared: _Prepared,
    counts: NDArray[np.int64],
    penalty_precision: float,
    ratings: NDArray[np.float64],
    seats: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    n_replicates = counts.shape[0]
    n_entrants = len(prepared.names)
    rating_draws = np.empty((n_replicates, n_entrants), dtype=np.float64)
    seat_draws = np.empty((n_replicates, N_SEATS), dtype=np.float64)
    for replicate, block_count in enumerate(counts):
        weights = block_count[prepared.blocks].astype(np.float64, copy=False)
        draw_ratings, draw_seats = _fit(prepared, weights, penalty_precision, ratings, seats)
        rating_draws[replicate] = draw_ratings
        seat_draws[replicate] = draw_seats
    if not np.isfinite(rating_draws).all() or not np.isfinite(seat_draws).all():
        raise RuntimeError("a bootstrap replicate produced a non-finite rating")
    return rating_draws, seat_draws


def _percentile_interval(samples: NDArray[np.float64]) -> PercentileInterval:
    quantiles = np.quantile(samples, (0.025, 0.975), method="linear")
    return PercentileInterval(float(quantiles[0]), float(quantiles[1]))


def _interval_after_exclusions(
    samples: NDArray[np.float64], counted: NDArray[np.bool_]
) -> tuple[PercentileInterval | None, int]:
    n_replicates = int(counted.shape[0])
    excluded = n_replicates - int(np.count_nonzero(counted))
    if excluded * _EXCLUSION_PERCENT > n_replicates or not counted.any():
        return None, excluded
    return _percentile_interval(samples[counted]), excluded


def _expected_win_rate(rating: float) -> float:
    # exp(r) / (exp(r) + 3), stable at both tails.
    if rating < 0.0:
        scaled = math.exp(rating)
        return scaled / (scaled + 3.0)
    return 1.0 / (1.0 + 3.0 * math.exp(-rating))


def _pair_tables(
    prepared: _Prepared,
) -> tuple[list[tuple[int, int]], NDArray[np.int64], NDArray[np.int64]]:
    n_entrants = len(prepared.names)
    pairs = [
        (left, right) for left in range(n_entrants) for right in range(n_entrants) if left != right
    ]
    pair_index = {pair: index for index, pair in enumerate(pairs)}
    wins = np.zeros((prepared.n_blocks, len(pairs)), dtype=np.int64)
    tables = np.zeros((prepared.n_blocks, len(pairs)), dtype=np.int64)
    for game in range(prepared.entrants.shape[0]):
        seated = prepared.entrants[game]
        winner = int(seated[int(prepared.winners[game])])
        block = int(prepared.blocks[game])
        for seat in range(N_SEATS):
            other = int(seated[seat])
            if other == winner:
                continue
            pair = pair_index[winner, other]
            wins[block, pair] += 1
            tables[block, pair] += 1
            tables[block, pair_index[other, winner]] += 1
    return pairs, wins, tables


def _assemble(
    prepared: _Prepared,
    ratings: NDArray[np.float64],
    seats: NDArray[np.float64],
    rating_draws: NDArray[np.float64],
    seat_draws: NDArray[np.float64],
    counts: NDArray[np.int64],
    *,
    penalty_sd: float,
    n_replicates: int,
    seed: int,
    collect_replicates: bool,
) -> RatingFit:
    names = prepared.names
    order = tuple(
        sorted(range(len(names)), key=lambda index: (-float(ratings[index]), names[index]))
    )
    entrants = tuple(
        EntrantRating(
            name=names[index],
            rating=float(ratings[index]),
            display=float(ratings[index]) * DISPLAY_SCALE,
            expected_win_rate=_expected_win_rate(float(ratings[index])),
            interval=_percentile_interval(rating_draws[:, index]),
        )
        for index in order
    )
    seat_effects = tuple(
        SeatEffect(
            seat=seat,
            effect=float(seats[seat]),
            interval=_percentile_interval(seat_draws[:, seat]),
        )
        for seat in range(N_SEATS)
    )
    head_to_head = _head_to_head(prepared, counts, order)
    rating_replicates: tuple[tuple[float, ...], ...] | None = None
    seat_replicates: tuple[tuple[float, ...], ...] | None = None
    if collect_replicates:
        ordered_draws = rating_draws[:, order]
        rating_replicates = tuple(tuple(float(value) for value in row) for row in ordered_draws)
        seat_replicates = tuple(tuple(float(value) for value in row) for row in seat_draws)
    return RatingFit(
        entrants,
        seat_effects,
        head_to_head,
        penalty_sd,
        n_replicates,
        seed,
        rating_replicates,
        seat_replicates,
    )


def _head_to_head(
    prepared: _Prepared,
    counts: NDArray[np.int64],
    order: tuple[int, ...],
) -> tuple[HeadToHead, ...]:
    pairs, block_wins, block_tables = _pair_tables(prepared)
    pair_index = {pair: index for index, pair in enumerate(pairs)}
    point_wins = block_wins.sum(axis=0)
    point_tables = block_tables.sum(axis=0)
    boot_wins = counts @ block_wins
    boot_tables = counts @ block_tables
    shares = np.divide(
        boot_wins,
        boot_tables,
        out=np.zeros(boot_wins.shape, dtype=np.float64),
        where=boot_tables > 0,
    )
    rows: list[HeadToHead] = []
    names = prepared.names
    for entrant in order:
        for opponent in order:
            if entrant == opponent:
                continue
            column = pair_index[entrant, opponent]
            tables = int(point_tables[column])
            wins = int(point_wins[column])
            interval, excluded = _interval_after_exclusions(
                shares[:, column], boot_tables[:, column] > 0
            )
            share = None if tables == 0 else wins / tables
            if tables == 0:
                interval = None
            rows.append(
                HeadToHead(
                    entrant=names[entrant],
                    opponent=names[opponent],
                    wins=wins,
                    tables=tables,
                    share=share,
                    interval=interval,
                    replicates_excluded=excluded,
                )
            )
    return tuple(rows)
