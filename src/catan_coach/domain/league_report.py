"""League report: the Strategy Report's input contract.

``summarize_league`` reads a finished or partial league and returns one
``LeagueReport``. ``league_report_to_json`` turns that report into
JSON-ready values. The document the Strategy Report reads is exactly::

    json.dumps(league_report_to_json(report), sort_keys=True, indent=2) + "\\n"

Sorted keys, two-space indent, and a trailing newline. Markdown is rendered
from the same report object. The same inputs produce the same bytes.

``provenance.plan_hash`` is the SHA-256 hex digest of the canonical plan
JSON, ``canonical_plan_json``: ``plan.to_json()`` encoded with
``json.dumps(..., sort_keys=True, separators=(",", ":"))`` as UTF-8. The
hash covers the plan only, not the source provenance.

Ratings use completed games only. Each completed game is one observation
whose block id is ``c{cycle}-b{block}``, so the four same-seed rotations
stay together. The Rating fit, the head-to-head matrix, and the Behavior
Profile bootstrap all resample those blocks with the rating module's
fixed-seed generator.

JSON object:

- ``schema``: ``1``.
- ``provenance``: ``name``, ``plan_hash``, ``source_commit``, ``source_dirty``,
  ``source_dirty_diff_hash`` (null when the tree was clean), ``penalty_sd``,
  ``bootstrap_replicates``, ``bootstrap_seed``.
- ``attrition``: ``scheduled``, ``completed``, ``dropped``,
  ``terminal_failures``, ``missing``, ``drop_rate`` (dropped / scheduled),
  ``valid``. ``valid`` is the Strategy Lab strength-claim rule: no terminal
  failure (a stored attempt 2 with no result), drop rate at most 1% of
  scheduled games, no scheduled game missing a result, and a non-empty
  schedule.
- ``ladder``: Entrants ordered by descending model Rating, then by name.
  ``rating`` is the sum-to-zero model scale. ``display`` is
  ``rating * 400 / ln(10)``. ``interval.lower`` and ``interval.upper`` are
  the 95% block-bootstrap percentile interval on the display scale.
  ``expected_win_rate`` is the chance of winning against three average
  Entrants.
- ``seat_effects``: one row per Seat, 0 through 3. ``effect`` is the
  sum-to-zero model scale. ``display`` and ``interval`` are the display
  scale; the interval is the 95% block-bootstrap percentile.
- ``head_to_head``: one cell per ordered pair, in ladder order. ``share``
  is the fraction of shared tables, among those one of the two won, that
  ``entrant`` won. ``share`` is null when that count is zero. ``interval``
  is the 95% block-bootstrap percentile of the share, or null when the
  share is null or more than 1% of replicates have a zero denominator.
  ``replicates_excluded`` counts those replicates. A null share or interval
  is unavailable; it is never filled in. This interval is a share, not a
  display-scale Rating.
- ``behavior``: one row per ladder Entrant, in ladder order. ``wins`` and
  ``losses`` each have ``games`` and ``means``, a list of
  ``[field, estimate]`` in Strategy Lab behavior-field order:
  ``settlements``, ``cities``, ``roads``, ``development_cards``, ``knights``,
  ``offers``, ``acceptances``, ``completed_trades``, ``maritime_trades``,
  ``initial_pips``, ``longest_road_rate``, ``largest_army_rate``,
  ``initial_resources``, ``adjacent_port_rate``, ``public_victory_points``,
  ``actual_victory_points``, ``first_build_settlement``, ``first_build_city``,
  ``first_build_road``, ``first_build_development_card``, ``first_build_none``.
  An estimate is ``mean``, ``interval`` (``lower`` and ``upper``, or null),
  and ``replicates_excluded``. Means are the Strategy Lab behavior aggregate;
  first-build entries are that aggregate's category counts divided by games.
  Intervals resample the same blocks as the Rating fit. A split with no
  games has a null mean and a null interval. ``turns_in_won_games`` is the
  same kind of estimate for ``CompletedGame.turns`` on games this Entrant won.
- ``warnings``: the Strategy Lab lines for missing results, terminal
  failures, and a drop rate above 1%.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from catan_coach.domain.experiment import (
    BehaviorProfile,
    CompletedGame,
    DroppedGame,
    SourceProvenance,
    TechnicalFailure,
)
from catan_coach.domain.experiment_report import (
    _BEHAVIOR_FIELDS,
    _DROP_LIMIT,
    BehaviorAggregate,
    Outcome,
    _aggregate,
    _behavior_vector,
    _jsonable,
)
from catan_coach.domain.league import LeagueGame, LeaguePlan
from catan_coach.domain.rating import (
    BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED,
    DISPLAY_SCALE,
    PENALTY_SD,
    EntrantRating,
    GameObservation,
    HeadToHead,
    PercentileInterval,
    SeatEffect,
    _block_counts,
    _block_sort_key,
    _interval_after_exclusions,
    fit_ratings,
)

SCHEMA = 1


@dataclass(frozen=True, slots=True)
class LadderRow:
    name: str
    rating: float
    display: float
    interval: PercentileInterval
    expected_win_rate: float


@dataclass(frozen=True, slots=True)
class SeatEffectRow:
    seat: int
    effect: float
    display: float
    interval: PercentileInterval


@dataclass(frozen=True, slots=True)
class Attrition:
    scheduled: int
    completed: int
    dropped: int
    terminal_failures: int
    missing: int
    drop_rate: float
    valid: bool


@dataclass(frozen=True, slots=True)
class Provenance:
    name: str
    plan_hash: str
    source_commit: str
    source_dirty: bool
    source_dirty_diff_hash: str | None
    penalty_sd: float
    bootstrap_replicates: int
    bootstrap_seed: int


@dataclass(frozen=True, slots=True)
class BehaviorEstimate:
    mean: float | None
    interval: PercentileInterval | None
    replicates_excluded: int


@dataclass(frozen=True, slots=True)
class BehaviorSplit:
    games: int
    means: tuple[tuple[str, BehaviorEstimate], ...]


@dataclass(frozen=True, slots=True)
class EntrantBehavior:
    name: str
    wins: BehaviorSplit
    losses: BehaviorSplit
    turns_in_won_games: BehaviorEstimate


@dataclass(frozen=True, slots=True)
class LeagueReport:
    schema: int
    provenance: Provenance
    attrition: Attrition
    ladder: tuple[LadderRow, ...]
    seat_effects: tuple[SeatEffectRow, ...]
    head_to_head: tuple[HeadToHead, ...]
    behavior: tuple[EntrantBehavior, ...]
    warnings: tuple[str, ...]


def canonical_plan_json(plan: LeaguePlan) -> str:
    """The plan JSON whose UTF-8 bytes are hashed into ``plan_hash``."""
    if not isinstance(plan, LeaguePlan):
        raise TypeError("plan must be a league plan")
    return json.dumps(plan.to_json(), sort_keys=True, separators=(",", ":"))


def plan_hash(plan: LeaguePlan) -> str:
    """SHA-256 hex digest of :func:`canonical_plan_json`."""
    return hashlib.sha256(canonical_plan_json(plan).encode("utf-8")).hexdigest()


def summarize_league(
    plan: LeaguePlan,
    source: SourceProvenance,
    scheduled: Sequence[LeagueGame],
    outcomes: Sequence[Outcome],
    failures: Sequence[TechnicalFailure],
    *,
    n_replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
    penalty_sd: float = PENALTY_SD,
) -> LeagueReport:
    """Fit the league and describe how each Entrant played.

    Behavior intervals use the same block ids, replicate count, and seed as
    the Rating bootstrap.
    """
    if not isinstance(plan, LeaguePlan):
        raise TypeError("plan must be a league plan")
    if not isinstance(source, SourceProvenance):
        raise TypeError("source must be source provenance")
    by_id = _index_scheduled(scheduled)
    finished = _index_outcomes(outcomes, by_id)
    attempts = _index_failures(failures, by_id)
    completed = _completed(by_id, finished)
    if not completed:
        raise ValueError("league report needs at least one completed game")
    dropped = sum(isinstance(game, DroppedGame) for game in finished.values())
    terminal = {
        key
        for key, tries in attempts.items()
        if any(failure.attempt == 2 for failure in tries) and key not in finished
    }
    missing = [key for key in by_id if key not in finished]
    scheduled_count = len(by_id)
    drop_rate = dropped / scheduled_count if scheduled_count else 1.0
    warnings = _warnings(missing, terminal, drop_rate)
    valid = not terminal and drop_rate <= _DROP_LIMIT and not missing and scheduled_count > 0
    observations = _observations(completed)
    fit = fit_ratings(
        observations,
        n_replicates=n_replicates,
        seed=seed,
        penalty_sd=penalty_sd,
    )
    block_ids = tuple(sorted({_block_id(game) for game, _result in completed}, key=_block_sort_key))
    draws = _block_counts(len(block_ids), fit.n_replicates, fit.seed)
    return LeagueReport(
        schema=SCHEMA,
        provenance=Provenance(
            name=plan.name,
            plan_hash=plan_hash(plan),
            source_commit=source.commit,
            source_dirty=source.dirty,
            source_dirty_diff_hash=source.dirty_diff_hash,
            penalty_sd=fit.penalty_sd,
            bootstrap_replicates=fit.n_replicates,
            bootstrap_seed=fit.seed,
        ),
        attrition=Attrition(
            scheduled=scheduled_count,
            completed=len(completed),
            dropped=dropped,
            terminal_failures=len(terminal),
            missing=len(missing),
            drop_rate=drop_rate,
            valid=valid,
        ),
        ladder=_ladder(fit.entrants),
        seat_effects=_seats(fit.seat_effects),
        head_to_head=fit.head_to_head,
        behavior=_behavior(completed, block_ids, fit.entrants, draws),
        warnings=tuple(warnings),
    )


def league_report_to_json(report: LeagueReport) -> dict[str, object]:
    """JSON-ready values. Dump them with sorted keys, indent 2, and a newline."""
    if not isinstance(report, LeagueReport):
        raise TypeError("report must be a league report")
    payload = _jsonable(report)
    if not isinstance(payload, dict):
        raise TypeError("league report JSON must be an object")
    return payload


def format_league_report(report: LeagueReport) -> str:
    """Markdown for the same report ``league_report_to_json`` serializes."""
    if not isinstance(report, LeagueReport):
        raise TypeError("report must be a league report")
    provenance = report.provenance
    attrition = report.attrition
    diff = provenance.source_dirty_diff_hash
    lines = [
        f"# {provenance.name}",
        "",
        (
            "Ratings use completed games only. The ladder is ordered by the model "
            "Rating. The number shown is the display scale, 400/ln(10) per model "
            "unit, with its 95% block-bootstrap interval. A gap inside the intervals "
            "is not a ranking."
        ),
        "Expected win rate is against three average Entrants.",
        "",
        "## Ladder",
        "| Entrant | Rating | 95% interval | Expected win rate |",
        "| --- | --- | --- | --- |",
    ]
    for row in report.ladder:
        lines.append(
            f"| {row.name} | {row.display:.1f} | "
            f"{row.interval.lower:.1f} to {row.interval.upper:.1f} | "
            f"{_percent(row.expected_win_rate)} |"
        )
    lines.extend(
        [
            "",
            "## Head-to-head",
            (
                "Share of shared tables, among those one of the two won, that the row "
                "Entrant won. Unavailable when neither won a shared table, or when the "
                "interval drops more than 1% of bootstrap replicates."
            ),
            "",
            *_head_to_head_table(report),
            "",
            "## Seat effects",
            "Seat effects are on the display scale and sum to zero on the model scale.",
        ]
    )
    lines.extend(
        f"- Seat {row.seat}: {row.display:.1f} "
        f"(95% {row.interval.lower:.1f} to {row.interval.upper:.1f})"
        for row in report.seat_effects
    )
    lines.extend(
        [
            "",
            "## Attrition",
            (
                f"{attrition.scheduled} scheduled, {attrition.completed} completed, "
                f"{attrition.dropped} dropped, {attrition.terminal_failures} terminal "
                f"failures, {attrition.missing} missing."
            ),
            f"Drop rate {_percent(attrition.drop_rate)}.",
            "Valid for a rating." if attrition.valid else "Not valid for a rating.",
            "",
            "## Provenance",
            f"Plan hash {provenance.plan_hash}",
            (
                f"Source {provenance.source_commit} "
                f"dirty={str(provenance.source_dirty).lower()} "
                f"diff={diff if diff is not None else 'none'}"
            ),
            f"Rating penalty sd {provenance.penalty_sd:g}",
            (
                f"Block bootstrap {provenance.bootstrap_replicates} replicates, "
                f"seed {provenance.bootstrap_seed}"
            ),
            "",
            "## Behavior",
            "Descriptive association only; this does not show that the behavior caused wins.",
        ]
    )
    for entrant in report.behavior:
        lines.extend(
            [
                "",
                f"### {entrant.name}",
                f"Wins ({entrant.wins.games} games):",
                *_split_lines(entrant.wins),
                f"Turns in won games: {_estimate_text(entrant.turns_in_won_games)}",
                f"Losses ({entrant.losses.games} games):",
                *_split_lines(entrant.losses),
            ]
        )
    if report.warnings:
        lines.extend(["", "## Warnings", *[f"- {warning}" for warning in report.warnings]])
    return "\n".join(lines) + "\n"


def _index_scheduled(scheduled: Sequence[LeagueGame]) -> dict[str, LeagueGame]:
    indexed: dict[str, LeagueGame] = {}
    for game in scheduled:
        if not isinstance(game, LeagueGame):
            raise TypeError("scheduled games must be league games")
        if game.game_id in indexed:
            raise ValueError(f"duplicate scheduled game {game.game_id}")
        indexed[game.game_id] = game
    return indexed


def _index_outcomes(
    outcomes: Sequence[Outcome], scheduled: Mapping[str, LeagueGame]
) -> dict[str, Outcome]:
    indexed: dict[str, Outcome] = {}
    for game in outcomes:
        if not isinstance(game, (CompletedGame, DroppedGame)):
            raise TypeError("outcomes must be completed or dropped games")
        planned = scheduled.get(game.result_key)
        if planned is None:
            raise ValueError(f"result {game.result_key} is not in the schedule")
        if game.result_key in indexed:
            raise ValueError(f"duplicate result {game.result_key}")
        if game.pairing_key != planned.pairing_key:
            raise ValueError(f"result {game.result_key} does not match its scheduled game")
        names = tuple(entrant.name for entrant in planned.entrants)
        if tuple(policy.name for policy in game.policies) != names:
            raise ValueError(f"result {game.result_key} does not match its Entrants")
        if _seat_names(game) != names:
            raise ValueError(f"result {game.result_key} does not match its Entrants")
        indexed[game.result_key] = game
    return indexed


def _seat_names(game: Outcome) -> tuple[str, ...]:
    if isinstance(game, CompletedGame):
        return tuple(seat.policy_name for seat in game.seats)
    return tuple(seat.policy_name for seat in game.seats)


def _index_failures(
    failures: Sequence[TechnicalFailure], scheduled: Mapping[str, LeagueGame]
) -> dict[str, tuple[TechnicalFailure, ...]]:
    grouped: dict[str, list[TechnicalFailure]] = {}
    for failure in failures:
        if not isinstance(failure, TechnicalFailure):
            raise TypeError("failures must be technical failures")
        planned = scheduled.get(failure.result_key)
        if planned is None:
            raise ValueError(f"failure {failure.result_key} is not in the schedule")
        if failure.pairing_key != planned.pairing_key:
            raise ValueError(f"failure {failure.result_key} does not match its pairing key")
        grouped.setdefault(failure.result_key, []).append(failure)
    indexed: dict[str, tuple[TechnicalFailure, ...]] = {}
    for key, attempts in grouped.items():
        numbers = [failure.attempt for failure in attempts]
        if len(numbers) != len(set(numbers)) or numbers != list(range(1, len(numbers) + 1)):
            raise ValueError(f"failure attempts for {key} are duplicated or out of order")
        indexed[key] = tuple(attempts)
    return indexed


def _completed(
    scheduled: Mapping[str, LeagueGame], finished: Mapping[str, Outcome]
) -> tuple[tuple[LeagueGame, CompletedGame], ...]:
    rows: list[tuple[LeagueGame, CompletedGame]] = []
    for game_id, game in scheduled.items():
        outcome = finished.get(game_id)
        if isinstance(outcome, CompletedGame):
            rows.append((game, outcome))
    return tuple(rows)


def _warnings(missing: Sequence[str], terminal: set[str], drop_rate: float) -> list[str]:
    warnings: list[str] = []
    if missing:
        warnings.append(f"{len(missing)} scheduled games have no result")
    if terminal:
        warnings.append(f"{len(terminal)} games failed on both attempts")
    if drop_rate > _DROP_LIMIT:
        warnings.append("dropped games exceed 1% of the schedule")
    return warnings


def _block_id(game: LeagueGame) -> str:
    return f"c{game.cycle}-b{game.block}"


def _names(game: LeagueGame) -> tuple[str, str, str, str]:
    names = tuple(entrant.name for entrant in game.entrants)
    if len(names) != 4:
        raise ValueError("a league game seats four Entrants")
    return (names[0], names[1], names[2], names[3])


def _observations(
    completed: Sequence[tuple[LeagueGame, CompletedGame]],
) -> tuple[GameObservation, ...]:
    return tuple(
        GameObservation(block_id=_block_id(game), entrants=_names(game), winner=result.winner)
        for game, result in completed
    )


def _ladder(entrants: Sequence[EntrantRating]) -> tuple[LadderRow, ...]:
    return tuple(
        LadderRow(
            name=entrant.name,
            rating=entrant.rating,
            display=entrant.display,
            interval=_display_interval(entrant.interval),
            expected_win_rate=entrant.expected_win_rate,
        )
        for entrant in entrants
    )


def _seats(effects: Sequence[SeatEffect]) -> tuple[SeatEffectRow, ...]:
    return tuple(
        SeatEffectRow(
            seat=effect.seat,
            effect=effect.effect,
            display=effect.effect * DISPLAY_SCALE,
            interval=_display_interval(effect.interval),
        )
        for effect in effects
    )


def _display_interval(interval: PercentileInterval) -> PercentileInterval:
    return PercentileInterval(interval.lower * DISPLAY_SCALE, interval.upper * DISPLAY_SCALE)


@dataclass(frozen=True, slots=True)
class _SeatBlocks:
    win_sum: NDArray[np.float64]
    win_count: NDArray[np.float64]
    win_turns: NDArray[np.float64]
    win_profiles: tuple[BehaviorProfile, ...]
    loss_sum: NDArray[np.float64]
    loss_count: NDArray[np.float64]
    loss_profiles: tuple[BehaviorProfile, ...]


def _behavior(
    completed: Sequence[tuple[LeagueGame, CompletedGame]],
    block_ids: Sequence[str],
    entrants: Sequence[EntrantRating],
    counts: NDArray[np.int64],
) -> tuple[EntrantBehavior, ...]:
    order = tuple(entrant.name for entrant in entrants)
    gathered = _gather(completed, block_ids, order)
    return tuple(_entrant_behavior(name, gathered[name], counts) for name in order)


def _gather(
    completed: Sequence[tuple[LeagueGame, CompletedGame]],
    block_ids: Sequence[str],
    names: Sequence[str],
) -> dict[str, _SeatBlocks]:
    block_index = {block_id: index for index, block_id in enumerate(block_ids)}
    width = len(_BEHAVIOR_FIELDS)
    n_blocks = len(block_ids)
    win_sum = {name: np.zeros((n_blocks, width), dtype=np.float64) for name in names}
    loss_sum = {name: np.zeros((n_blocks, width), dtype=np.float64) for name in names}
    win_count = {name: np.zeros(n_blocks, dtype=np.float64) for name in names}
    loss_count = {name: np.zeros(n_blocks, dtype=np.float64) for name in names}
    win_turns = {name: np.zeros(n_blocks, dtype=np.float64) for name in names}
    win_profiles: dict[str, list[BehaviorProfile]] = {name: [] for name in names}
    loss_profiles: dict[str, list[BehaviorProfile]] = {name: [] for name in names}
    for game, result in completed:
        block = block_index[_block_id(game)]
        for seat, entrant in enumerate(game.entrants):
            profile = result.seats[seat].profile
            vector = np.asarray(_behavior_vector(profile), dtype=np.float64)
            name = entrant.name
            if profile.won:
                win_sum[name][block] += vector
                win_count[name][block] += 1.0
                win_turns[name][block] += float(result.turns)
                win_profiles[name].append(profile)
            else:
                loss_sum[name][block] += vector
                loss_count[name][block] += 1.0
                loss_profiles[name].append(profile)
    return {
        name: _SeatBlocks(
            win_sum[name],
            win_count[name],
            win_turns[name],
            tuple(win_profiles[name]),
            loss_sum[name],
            loss_count[name],
            tuple(loss_profiles[name]),
        )
        for name in names
    }


def _entrant_behavior(name: str, blocks: _SeatBlocks, counts: NDArray[np.int64]) -> EntrantBehavior:
    return EntrantBehavior(
        name=name,
        wins=_split(blocks.win_profiles, blocks.win_sum, blocks.win_count, counts),
        losses=_split(blocks.loss_profiles, blocks.loss_sum, blocks.loss_count, counts),
        turns_in_won_games=_scalar_estimate(blocks.win_turns, blocks.win_count, counts),
    )


def _split(
    profiles: Sequence[BehaviorProfile],
    block_sum: NDArray[np.float64],
    block_count: NDArray[np.float64],
    counts: NDArray[np.int64],
) -> BehaviorSplit:
    games = len(profiles)
    n_replicates = int(counts.shape[0])
    if games == 0:
        empty = BehaviorEstimate(None, None, n_replicates)
        return BehaviorSplit(0, tuple((field, empty) for field in _BEHAVIOR_FIELDS))
    if int(block_count.sum()) != games:
        raise RuntimeError("behavior games do not match the block counts")
    point = _point_means(profiles)
    boot_sum = counts @ block_sum
    boot_n = counts @ block_count
    counted = boot_n > 0
    means: list[tuple[str, BehaviorEstimate]] = []
    for index, field in enumerate(_BEHAVIOR_FIELDS):
        samples = np.divide(
            boot_sum[:, index],
            boot_n,
            out=np.zeros(n_replicates, dtype=np.float64),
            where=counted,
        )
        interval, excluded = _interval_after_exclusions(samples, counted)
        means.append((field, BehaviorEstimate(point[field], interval, excluded)))
    return BehaviorSplit(games, tuple(means))


def _scalar_estimate(
    block_total: NDArray[np.float64],
    block_count: NDArray[np.float64],
    counts: NDArray[np.int64],
) -> BehaviorEstimate:
    games = int(block_count.sum())
    n_replicates = int(counts.shape[0])
    if games == 0:
        return BehaviorEstimate(None, None, n_replicates)
    mean = float(block_total.sum() / block_count.sum())
    boot_total = counts @ block_total
    boot_n = counts @ block_count
    counted = boot_n > 0
    samples = np.divide(
        boot_total,
        boot_n,
        out=np.zeros(n_replicates, dtype=np.float64),
        where=counted,
    )
    interval, excluded = _interval_after_exclusions(samples, counted)
    return BehaviorEstimate(mean, interval, excluded)


def _point_means(profiles: Sequence[BehaviorProfile]) -> dict[str, float]:
    aggregate = _aggregate(profiles)
    means = {
        field: _required_mean(aggregate, field)
        for field in _BEHAVIOR_FIELDS
        if not field.startswith("first_build_")
    }
    counts = dict(aggregate.first_build)
    for field in _BEHAVIOR_FIELDS:
        if not field.startswith("first_build_"):
            continue
        label = "none" if field == "first_build_none" else field.removeprefix("first_build_")
        means[field] = counts.get(label, 0) / aggregate.games
    return means


def _required_mean(aggregate: BehaviorAggregate, field: str) -> float:
    value = getattr(aggregate, field)
    if isinstance(value, bool) or not isinstance(value, float):
        raise RuntimeError(f"behavior aggregate is missing {field}")
    return value


def _head_to_head_table(report: LeagueReport) -> list[str]:
    names = [row.name for row in report.ladder]
    cells = {(cell.entrant, cell.opponent): cell for cell in report.head_to_head}
    header = "| Entrant | " + " | ".join(names) + " |"
    separator = "| --- | " + " | ".join("---" for _ in names) + " |"
    rows = [header, separator]
    for name in names:
        shown: list[str] = []
        for other in names:
            if name == other:
                shown.append("-")
            else:
                shown.append(_cell_text(cells[name, other]))
        rows.append("| " + " | ".join([name, *shown]) + " |")
    return rows


def _split_lines(split: BehaviorSplit) -> list[str]:
    if split.games == 0:
        return ["- no games"]
    return [f"- {field}: {_estimate_text(estimate)}" for field, estimate in split.means]


def _estimate_text(estimate: BehaviorEstimate) -> str:
    if estimate.mean is None:
        return "unavailable"
    if estimate.interval is None:
        return f"{estimate.mean:.2f} (interval unavailable)"
    return (
        f"{estimate.mean:.2f} (95% {estimate.interval.lower:.2f} to {estimate.interval.upper:.2f})"
    )


def _cell_text(cell: HeadToHead) -> str:
    if cell.share is None:
        return "unavailable"
    share = _percent(cell.share)
    if cell.interval is None:
        return f"{share} (interval unavailable)"
    return f"{share} ({_percent(cell.interval.lower)} to {_percent(cell.interval.upper)})"


def _percent(rate: float) -> str:
    return f"{rate * 100:.1f}%"
